# Security Migration Plan

## S1. Secrets Management (Critical)

**Goal:** Remove plaintext secrets from `.env`, use macOS Keychain locally with a pluggable interface for hosted secrets managers.

**Implementation:**
- Create `utils/secrets.py` with a `SecretsProvider` abstract base class and two implementations:
  - `KeychainProvider` — reads/writes secrets via `security` CLI (macOS Keychain)
  - `EnvProvider` — fallback that reads from environment variables (for CI, Docker, or migration period)
- Config in `config/database.yaml`:
  ```yaml
  secrets:
    provider: keychain  # or "env" or future "aws_secrets_manager"
    keychain_service: "chicago-sports-recap"
  ```
- Migration script `scripts/migrate_secrets.py` that reads current `.env` and stores each key in Keychain
- Update all `os.getenv()` calls to use `secrets.get("KEY_NAME")` instead
- After migration, `.env` only contains `SECRETS_PROVIDER=keychain` (non-sensitive)

**Files to create:**
- `utils/secrets.py` — provider interface + implementations
- `scripts/migrate_secrets.py` — one-time migration from `.env` to Keychain

**Files to modify:**
- `config/database.yaml` — add `secrets` section
- `agent/claude_client.py` — replace `os.environ.get("ANTHROPIC_API_KEY")`
- `tools/send_approval_email_tool.py` — replace all `os.getenv()` calls
- `tools/wordpress_publish_tool.py` — replace `os.getenv()`
- `server/approval_server.py` — replace `os.getenv()` for OAuth credentials
- `utils/article_collectors/api_collectors/api_collector.py` — replace `os.getenv()`
- `utils/article_collectors/api_collectors/serpapi_collector.py` — replace client init

**Tests:** Mock `SecretsProvider` in all existing tests, add unit tests for both providers.

**Status:** [ ] Not started

---

## S2. Encrypt OAuth Tokens at Rest (Critical)

**Goal:** Encrypt WordPress OAuth tokens before storing in SQLite.

**Implementation:**
- Use `cryptography.fernet` with a key derived from `APPROVAL_SECRET_KEY` (via PBKDF2)
- Add `utils/encryption.py` with `encrypt_token(plaintext)` and `decrypt_token(ciphertext)` functions
- Modify `memory.save_oauth_token()` to encrypt before storing
- Modify `memory.get_oauth_token()` to decrypt after reading
- Add migration: on first read of an unencrypted token, encrypt it in place

**Files to create:**
- `utils/encryption.py`

**Files to modify:**
- `memory/memory.py` — encrypt/decrypt in save/get OAuth token methods
- `requirements.txt` — add `cryptography>=42.0.0`

**Tests:** Verify round-trip encrypt/decrypt, verify encrypted value differs from plaintext, verify migration of unencrypted tokens.

**Status:** [ ] Not started

---

## S3. Bind to 127.0.0.1 by Default (High)

**Goal:** Server only accessible locally unless explicitly configured otherwise.

**Implementation:**
- Add `APPROVAL_BIND_HOST` env var, defaulting to `127.0.0.1`
- Update `approval_server.py` entry point

**Files to modify:**
- `server/approval_server.py` — `app.run(host=os.getenv('APPROVAL_BIND_HOST', '127.0.0.1'), ...)`

**Tests:** Verify default bind host in server test.

**Status:** [x] Complete

---

## S4. Auth0 Authentication with Role-Based Access (High)

**Goal:** Three roles — anonymous (read-only dashboard), editor (approve/reject), admin (OAuth settings, server config).

**Implementation:**
- Integrate Auth0 via `authlib` library
- Config in `config/auth.yaml`:
  ```yaml
  auth0:
    domain: "your-tenant.auth0.com"
    client_id: "..."  # stored in secrets provider
    client_secret: "..."  # stored in secrets provider
    audience: "https://chicago-sports-recap/api"
  roles:
    anonymous:
      - "GET /dashboard"
      - "GET /dashboard/iterations"
      - "GET /dashboard/api/*"
    editor:
      - "GET /approve/*"
      - "POST /reject/*"
      - "GET /status/*"
    admin:
      - "GET /oauth/*"
      - "GET /health"
  ```
- Create `server/auth.py` with:
  - `require_role(role)` decorator for route protection
  - Auth0 callback route (`/auth/login`, `/auth/callback`, `/auth/logout`)
  - Session-based user tracking after OAuth callback
  - Role resolution from Auth0 user metadata or a local config mapping
- Anonymous users: no login required, access to dashboard read-only routes
- Editor/Admin: must authenticate via Auth0

**Files to create:**
- `config/auth.yaml`
- `server/auth.py` — Auth0 integration, role decorator, session management

**Files to modify:**
- `server/approval_server.py` — add auth routes, protect approval endpoints with `@require_role('editor')`, protect OAuth routes with `@require_role('admin')`
- `server/dashboard.py` — dashboard routes remain accessible to anonymous
- `requirements.txt` — add `authlib>=1.3.0`

**Tests:** Mock Auth0 token validation, test each role's access to protected/unprotected routes.

**Status:** [ ] Not started

---

## S5. Fix XSS via `|safe` Filter (High)

**Goal:** Sanitize HTML before rendering with `|safe`.

**Implementation:**
- Use `bleach` library to sanitize `post_info` before passing to template
- Allow only safe tags: `<p>`, `<a>`, `<strong>`
- Strip all other HTML and attributes except `href` on `<a>`

**Files to modify:**
- `server/approval_server.py` — sanitize `post_info` with `bleach.clean()` before rendering
- `requirements.txt` — add `bleach>=6.0.0`

**Tests:** Verify malicious HTML is stripped, verify safe HTML passes through.

**Status:** [x] Complete

---

## S6. Validate Approval Token Signature and Expiry (Medium)

**Goal:** Cryptographically verify tokens before database lookup.

**Implementation:**
- In `/approve/<token>` and `/reject/<token>` routes, call `serializer.loads(token, salt='approval', max_age=expiry_hours * 3600)` before querying the database
- Return `INVALID_TOKEN_PAGE` if signature is invalid or expired
- Remove reliance on database `expires_at` as the sole expiry mechanism (keep it as a backup for the auto-archive job)

**Files to modify:**
- `server/approval_server.py` — add token validation in approve/reject routes

**Tests:** Test with valid token, expired token, tampered token.

**Status:** [ ] Not started

---

## S7. CSRF Protection on Reject Form (Medium)

**Goal:** Prevent cross-site form submission attacks.

**Implementation:**
- Add `flask-wtf` for CSRF protection
- Set `app.secret_key` from secrets provider
- Add `{{ csrf_token() }}` hidden field to the reject form template
- Validate CSRF on POST to `/reject/<token>`

**Files to modify:**
- `server/approval_server.py` — add Flask-WTF CSRF init, update reject form template
- `requirements.txt` — add `flask-wtf>=1.2.0`

**Tests:** Verify POST without CSRF token returns 400, POST with valid token succeeds.

**Status:** [ ] Not started

---

## S8. Rate Limiting (Medium)

**Goal:** Prevent brute-force and abuse at both application and proxy level.

**Implementation:**
- Add `flask-limiter` with configurable limits in `config/auth.yaml`:
  ```yaml
  rate_limiting:
    default: "60/minute"
    approval_endpoints: "10/minute"
    dashboard_api: "30/minute"
  ```
- Limits apply at the application level
- If behind Cloudflare/nginx, those limits apply first (no conflict — application limits are a second layer)
- `flask-limiter` uses `X-Forwarded-For` when behind a proxy

**Files to modify:**
- `server/approval_server.py` — init `Limiter`, apply decorators to routes
- `config/auth.yaml` — add rate_limiting section
- `requirements.txt` — add `flask-limiter>=3.5.0`

**Tests:** Verify rate limit headers are present, verify 429 response after exceeding limit.

**Status:** [ ] Not started

---

## S9. Fix Database File Permissions (Medium)

**Goal:** Restrict SQLite file to owner-only access.

**Implementation:**
- After `init_db()` creates the file, set permissions to `0o600`
- Also set permissions on backup files after creation

**Files to modify:**
- `memory/database.py` — `os.chmod(db_path, 0o600)` after `create_all()`
- `memory/memory.py` — `os.chmod(backup_file, 0o600)` after backup

**Tests:** Verify file permissions after creation (on non-Windows systems).

**Status:** [x] Complete

---

## S10. Security Headers and Error Sanitization (Low)

**Goal:** Add standard security headers and prevent internal path leakage.

**Implementation:**
- Add `@app.after_request` hook to set headers on all responses:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy: default-src 'self'`
  - `X-XSS-Protection: 1; mode=block`
- Wrap OAuth error rendering to show generic messages, log full details server-side

**Files to modify:**
- `server/approval_server.py` — add `after_request` hook, sanitize error messages in OAuth routes

**Tests:** Verify security headers present on responses, verify error pages don't contain file paths.

**Status:** [x] Complete

---

## Implementation Order

| Priority | Item | Effort | Dependency |
|----------|------|--------|------------|
| 1 | **S3** — Bind to 127.0.0.1 | 5 min | None |
| 2 | **S9** — File permissions | 10 min | None |
| 3 | **S10** — Security headers | 15 min | None |
| 4 | **S5** — XSS fix | 15 min | None |
| 5 | **S6** — Token validation | 20 min | None |
| 6 | **S7** — CSRF protection | 20 min | None |
| 7 | **S8** — Rate limiting | 30 min | None |
| 8 | **S1** — Secrets management | 1-2 hrs | None |
| 9 | **S2** — Token encryption | 30 min | S1 (uses secrets provider for key) |
| 10 | **S4** — Auth0 integration | 2-3 hrs | S1 (stores Auth0 credentials) |

**Total estimated effort:** 5-7 hours

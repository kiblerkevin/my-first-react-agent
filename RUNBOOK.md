# Chicago Sports Summarizer — Runbook

## Prerequisites

Before first run, ensure the following are installed:
- [ ] Python 3.14+
- [ ] Docker & Docker Compose
- [ ] pip dependencies: `pip install -r requirements.txt`
- [ ] Dev dependencies (for testing/linting): `pip install -r requirements-dev.txt`

## Environment Configuration

### Option 1: macOS Keychain (recommended)

- [ ] Run the migration script: `python scripts/migrate_secrets.py`
- [ ] Verify: `python scripts/migrate_secrets.py --verify`
- [ ] Confirm `config/database.yaml` has `secrets.provider: keychain`
- [ ] Reduce `.env` to non-sensitive values only (e.g. `SECRETS_PROVIDER=keychain`)

### Option 2: Environment variables (CI, Docker)

- [ ] Set `SECRETS_PROVIDER=env` in the environment
- [ ] Set all secrets as environment variables (see list below)

### Required secrets

| Key | Description |
|-----|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `NEWSAPI_KEY` | NewsAPI key |
| `SERPAPI_KEY` | SerpAPI key |
| `EMAIL_FROM` | Gmail address for sending emails |
| `EMAIL_PASSWORD` | Gmail App Password (not account password) |
| `EMAIL_TO` | Recipient for approval notifications |
| `ERROR_EMAIL_TO` | Recipient for failure/drift notifications |
| `EMAIL_SMTP_SERVER` | SMTP server (e.g. smtp.gmail.com) |
| `EMAIL_SMTP_PORT` | SMTP port (default: 587) |
| `APPROVAL_SECRET_KEY` | Random secret for signing approval tokens |
| `APPROVAL_BASE_URL` | Approval server URL (default: http://localhost:5000) |
| `WORDPRESS_CLIENT_ID` | From developer.wordpress.com/apps |
| `WORDPRESS_CLIENT_SECRET` | From developer.wordpress.com/apps |
| `WORDPRESS_URL` | Your WordPress.com site URL |
| `LANGFUSE_PUBLIC_KEY` | From Langfuse project settings |
| `LANGFUSE_SECRET_KEY` | From Langfuse project settings |
| `AUTH0_CLIENT_ID` | From Auth0 application settings |
| `AUTH0_CLIENT_SECRET` | From Auth0 application settings |

---

## Security Configuration

### Secrets management

Secrets are managed via a pluggable provider configured in `config/database.yaml`:

```yaml
secrets:
  provider: keychain  # "keychain" (macOS) or "env" (CI/Docker)
  keychain_service: "chicago-sports-recap"
```

- **macOS Keychain** (recommended for local): Run `python scripts/migrate_secrets.py` to migrate from `.env`
- **Environment variables** (CI/Docker): Set `SECRETS_PROVIDER=env` and inject secrets via the environment
- **Verify secrets**: `python scripts/migrate_secrets.py --verify`

### Auth0 authentication

Role-based access control is configured in `config/auth.yaml`:

```yaml
auth0:
  domain: "your-tenant.auth0.com"
  client_id_key: "AUTH0_CLIENT_ID"
  client_secret_key: "AUTH0_CLIENT_SECRET"

role_mappings:
  admin@example.com: admin
  editor@example.com: editor
```

| Role | Access |
|------|--------|
| anonymous | Dashboard (read-only), health endpoint |
| editor | Approve/reject blog posts, view status |
| admin | WordPress OAuth settings, all editor permissions |

First-time Auth0 setup:
1. Create an Auth0 application (Regular Web Application)
2. Set callback URL to `http://localhost:5000/auth/callback`
3. Store `AUTH0_CLIENT_ID` and `AUTH0_CLIENT_SECRET` in the secrets provider
4. Set `auth0.domain` in `config/auth.yaml`
5. Add email → role mappings in `config/auth.yaml`

If Auth0 is not configured, authentication is disabled and all routes are open.

### OAuth token encryption

WordPress OAuth tokens are encrypted at rest in the database using Fernet encryption derived from `APPROVAL_SECRET_KEY`. Existing plaintext tokens are auto-migrated on first read.

⚠️ **If `APPROVAL_SECRET_KEY` changes, encrypted tokens become unreadable.** Re-authorize WordPress at `/oauth/start` after rotating this key.

### Rate limiting

Configured in `config/auth.yaml`:

```yaml
rate_limiting:
  default: "60/minute"
  approval_endpoints: "10/minute"
  dashboard_api: "30/minute"
```

The health endpoint is exempt. Rate limits apply at the application level and do not conflict with Cloudflare/nginx proxy limits.

### Database security

- SQLite database file permissions are set to `0600` (owner-only)
- WAL mode is enabled for concurrent read/write safety
- Backup files also have `0600` permissions
- Daily backups after each workflow run, 30-day retention

---

## Option A: Automatic Startup (recommended for production)

### Install Services

```bash
./services/install.sh
```

This installs three macOS launchd services that start on login:
1. **Docker Compose** — starts Langfuse, Postgres, Redis, ClickHouse, MinIO
2. **Approval Server** — starts Flask server with scheduler (waits for Langfuse to be ready)
3. **Cloudflare Tunnel** — starts tunnel (skipped if placeholder values are detected)

After installation, services start automatically on login. No manual startup needed.

### First-time setup after install

- [ ] Log out and log back in (or run `launchctl start com.chicagosportsrecap.docker`)
- [ ] Wait ~60 seconds for Docker containers to start
- [ ] Visit http://localhost:3000 — create Langfuse account and project, store keys via `python scripts/migrate_secrets.py` or set in environment
- [ ] Run `launchctl start com.chicagosportsrecap.approval-server`
- [ ] Complete WordPress OAuth: log in as admin, then visit http://localhost:5000/oauth/start
- [ ] Configure Auth0 (see Security Configuration above)

### Cloudflare Tunnel setup

If using remote approval:
1. Edit `services/com.chicagosportsrecap.cloudflare-tunnel.plist`
2. Replace `PLACEHOLDER_TUNNEL_NAME` with your tunnel name
3. Replace the cloudflared path if needed
4. Re-run `./services/install.sh`
5. Update `APPROVAL_BASE_URL` in Keychain: `security add-generic-password -s chicago-sports-recap -a APPROVAL_BASE_URL -w "https://your-tunnel-url" -U`

### Uninstall Services

```bash
./services/uninstall.sh
```

### Check service status

```bash
launchctl list | grep chicagosportsrecap
```

---

## Option B: Manual Startup

### 1. Start Langfuse (observability)

```bash
docker compose up -d
```

- [ ] Verify Langfuse is running: visit http://localhost:3000
- [ ] On first run: create an account, create a project, copy public/secret keys to `.env`

### 2. Start the Approval Server

```bash
python server/approval_server.py
```

- [ ] Verify server is running: visit http://localhost:5000/health (should return `{"status": "ok"}`)
- [ ] Verify dashboard: visit http://localhost:5000/dashboard (accessible without login)
- [ ] This also starts the background scheduler:
  - Daily workflow cron at 6:00 AM CT
  - Expired approval checker every 60 minutes

### 3. WordPress OAuth (one-time setup)

- [ ] Log in as admin via Auth0 (if configured)
- [ ] Visit http://localhost:5000/oauth/start
- [ ] Authorize the application on WordPress.com
- [ ] Verify success page shows your blog URL
- [ ] This only needs to be done once — the token is encrypted and stored in the database

### 4. Cloudflare Tunnel (if using remote approval)

- [ ] Configure Cloudflare tunnel to forward to `localhost:5000`
- [ ] Update `APPROVAL_BASE_URL` in Keychain or environment to the tunnel URL
- [ ] Restart the approval server after changing the URL

---

## Running the Workflow

### Manual run (testing)

```bash
python main.py
```

### Resume a failed run

```bash
python main.py --resume <run_id>
```

### Scheduled run (production)

The approval server's scheduler automatically runs the workflow at 6:00 AM CT daily.
No manual action needed — just keep the approval server running (automatic with Option A).

---

## Verifying the System

| Check | How |
|-------|-----|
| Services running | `launchctl list \| grep chicagosportsrecap` |
| Langfuse traces | http://localhost:3000 — look for traces after a workflow run |
| Dashboard | http://localhost:5000/dashboard — workflow performance, API health, evaluation trends |
| Draft iterations | http://localhost:5000/dashboard/iterations — draft/evaluation history per run |
| Approval server | http://localhost:5000/health — should return `{"status": "ok"}` |
| Drift alerts | http://localhost:5000/dashboard/api/drift — active drift alerts |
| Secrets | `python scripts/migrate_secrets.py --verify` — all keys accessible |
| Database | `data/articles.db` — should exist after first run |
| Logs | `logs/app_YYYYMMDD.log` — check for errors |
| Service logs | `logs/approval_server_stdout.log`, `logs/docker_stdout.log` |
| WordPress OAuth | Run `python -c "from memory.memory import Memory; m=Memory(); print(m.get_oauth_token('wordpress') is not None)"` |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `No WordPress OAuth token found` | Log in as admin, visit http://localhost:5000/oauth/start to authorize |
| `OAuth token is invalid or revoked` | Re-authorize at http://localhost:5000/oauth/start (requires admin login) |
| `APPROVAL_SECRET_KEY` rotated | Re-authorize WordPress OAuth — encrypted tokens are invalidated on key change |
| `Email sent: False` | Check Gmail App Password — run `python scripts/migrate_secrets.py --verify` to confirm EMAIL_PASSWORD is set |
| `Login Required` on approval link | Log in via Auth0 with an editor or admin account |
| `Access Denied` on approval link | Your Auth0 account needs editor role — update `role_mappings` in `config/auth.yaml` |
| `Auth0 not configured` warning | Set `auth0.domain`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` — see Security Configuration |
| `429 Too Many Requests` | Rate limit exceeded — wait 1 minute or adjust limits in `config/auth.yaml` |
| `No new articles found` | Normal if workflow already ran today — articles are deduplicated across runs |
| Langfuse connection errors | Verify Docker is running: `docker compose ps` |
| `Workflow Skipped` | Check `skip_reason` — either no new articles or no relevant summaries |
| Database locked | Only one process should write to SQLite at a time — check for zombie processes |
| Service not starting | Check `logs/approval_server_stderr.log` or `logs/docker_stderr.log` |
| Approval button error | Ensure approval server is running before clicking approve/reject in email |
| Scheduled run missed | Check `logs/app_YYYYMMDD.log` for scheduler errors; restart server if needed |

---

## Shutdown

### If using services (Option A)

```bash
# Stop all services
launchctl stop com.chicagosportsrecap.approval-server
launchctl stop com.chicagosportsrecap.docker
launchctl stop com.chicagosportsrecap.cloudflare-tunnel

# Stop Docker containers
docker compose down
```

### If using manual startup (Option B)

```bash
# Stop the approval server
Ctrl+C

# Stop Langfuse
docker compose down
```

To preserve Langfuse data across restarts, the Postgres volume is persistent.
To reset Langfuse data: `docker compose down -v`

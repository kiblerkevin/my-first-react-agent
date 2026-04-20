# Chicago Sports Summarizer — Runbook

## Prerequisites

Before first run, ensure the following are installed:
- [ ] Python 3.14+
- [ ] Docker & Docker Compose
- [ ] pip dependencies: `pip install -r requirements.txt`

## Environment Configuration

- [ ] Copy `.env.example` to `.env` (or verify `.env` exists)
- [ ] Set `ANTHROPIC_API_KEY` — Anthropic API key
- [ ] Set `NEWSAPI_KEY` — NewsAPI key
- [ ] Set `SERPAPI_KEY` — SerpAPI key
- [ ] Set `EMAIL_FROM` and `EMAIL_PASSWORD` — Gmail address + App Password (not account password)
- [ ] Set `EMAIL_TO` — recipient email for approval notifications
- [ ] Set `ERROR_EMAIL_TO` — recipient email for failure notifications
- [ ] Set `APPROVAL_SECRET_KEY` — random secret for signing approval tokens
- [ ] Set `WORDPRESS_CLIENT_ID` and `WORDPRESS_CLIENT_SECRET` — from developer.wordpress.com/apps
- [ ] Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` — from Langfuse project settings (after step 2 below)

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
- [ ] Visit http://localhost:3000 — create Langfuse account and project, copy keys to `.env`
- [ ] Run `launchctl start com.chicagosportsrecap.approval-server`
- [ ] Complete WordPress OAuth: visit http://localhost:5000/oauth/start

### Cloudflare Tunnel setup

If using remote approval:
1. Edit `services/com.chicagosportsrecap.cloudflare-tunnel.plist`
2. Replace `PLACEHOLDER_TUNNEL_NAME` with your tunnel name
3. Replace the cloudflared path if needed
4. Re-run `./services/install.sh`
5. Update `APPROVAL_BASE_URL` in `.env` to the tunnel URL

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

- [ ] Verify server is running: visit http://localhost:5000/status/test (should return "Invalid Token" page)
- [ ] This also starts the background scheduler:
  - Daily workflow cron at 6:00 AM CT
  - Expired approval checker every 60 minutes

### 3. WordPress OAuth (one-time setup)

- [ ] Visit http://localhost:5000/oauth/start
- [ ] Authorize the application on WordPress.com
- [ ] Verify success page shows your blog URL
- [ ] This only needs to be done once — the token is stored in the database

### 4. Cloudflare Tunnel (if using remote approval)

- [ ] Configure Cloudflare tunnel to forward to `localhost:5000`
- [ ] Update `APPROVAL_BASE_URL` in `.env` to the tunnel URL
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
| Approval server | http://localhost:5000/status/test — should return 404 page |
| Database | `data/articles.db` — should exist after first run |
| Logs | `logs/app_YYYYMMDD.log` — check for errors |
| Service logs | `logs/approval_server_stdout.log`, `logs/docker_stdout.log` |
| WordPress OAuth | Run `python -c "from memory.memory import Memory; m=Memory(); print(m.get_oauth_token('wordpress') is not None)"` |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `No WordPress OAuth token found` | Visit http://localhost:5000/oauth/start to authorize |
| `OAuth token is invalid or revoked` | Re-authorize at http://localhost:5000/oauth/start |
| `Email sent: False` | Check Gmail App Password in `.env` — must be 16-char app password, not account password |
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

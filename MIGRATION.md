# Migration Plan: AWS Serverless

> **Goal**: Migrate the Chicago Sports Recap agent from a local macOS setup to a fully serverless AWS architecture, reducing operational overhead and cost while preserving all current functionality.

---

## Timeline Summary

| Phase | Work | Days (Aurora) | Days (DynamoDB) |
|---|---|---|---|
| 0 | Bootstrap (AWS account, OIDC, ACM certs, Langfuse Cloud, Auth0 SPA) | 1 | 1 |
| 1 | Infrastructure provisioning (OpenTofu) | 1–2 | 1–2 |
| 2 | Database migration + validation | 1 | 4–6 |
| 3 | Deploy Lambdas + Step Functions, test workflow end-to-end | 1–2 | 1–2 |
| 4 | Deploy SPA + API Gateway, test approval flow | 1–2 | 1–2 |
| 5 | DNS cutover, 7-day parallel monitoring, decommission local | 1 + 7 monitoring | 1 + 7 monitoring |
| | **Total active work** | **6–9 days** | **9–14 days** |
| | **Total calendar time (including monitoring)** | **13–16 days** | **16–21 days** |

The DynamoDB path adds 3–5 days due to the full rewrite of the memory layer (10 mixins, 13 dashboard query methods, 7 table schemas). The Aurora path requires only a connection string swap.

---

## Table of Contents

1. [Overview & Cost Comparison](#1-overview--cost-comparison)
2. [Target Architecture](#2-target-architecture)
3. [Database Migration](#3-database-migration)
4. [Step Functions Workflow](#4-step-functions-workflow)
5. [Lambda Functions](#5-lambda-functions)
6. [API Gateway + Lambda](#6-api-gateway--lambda)
7. [SPA Dashboard](#7-spa-dashboard)
8. [Secrets Management](#8-secrets-management)
9. [Langfuse Migration](#9-langfuse-migration)
10. [Data Migration Runbook](#10-data-migration-runbook)
11. [OpenTofu Module Structure](#11-opentofu-module-structure)
12. [GitHub Actions Pipeline](#12-github-actions-pipeline)
13. [Migration Phases](#13-migration-phases)

---

## 1. Overview & Cost Comparison

### Current Architecture (Local macOS)

| Component | Implementation |
|---|---|
| Compute | Python process on macOS (APScheduler cron) |
| Database | SQLite (`data/articles.db`, ~2.5 MB) |
| Web Server | Flask (approval routes, dashboard, OAuth) |
| Observability | Self-hosted Langfuse via Docker Compose (Postgres, Redis, ClickHouse, MinIO) |
| Tunnel | Cloudflare Tunnel → localhost:5000 |
| Secrets | macOS Keychain |
| Scheduling | APScheduler (in-process) |
| Process Mgmt | launchd plist services |

### Target Architecture (AWS Serverless)

| Component | AWS Service |
|---|---|
| Compute | Lambda (workflow steps + API handlers) |
| Orchestration | Step Functions (8-step state machine) |
| Database | Aurora Serverless v2 **or** DynamoDB (see [Section 3](#3-database-migration)) |
| Web Server | API Gateway HTTP API + Lambda |
| Dashboard | S3 + CloudFront (static SPA) |
| Observability | Langfuse Cloud (free tier) |
| Networking | Cloudflare DNS → CloudFront (dashboard) + API Gateway (API) |
| Secrets | Secrets Manager (single JSON blob) |
| Scheduling | EventBridge Scheduler |
| IaC | OpenTofu via GitHub Actions |

### Monthly Cost Comparison

| Component | Aurora Path | DynamoDB Path |
|---|---|---|
| Lambda (workflow + API) | ~$0.50 | ~$0.50 |
| Step Functions | ~$0.03 | ~$0.03 |
| EventBridge Scheduler | Free | Free |
| API Gateway HTTP API | ~$0.01 | ~$0.01 |
| Aurora Serverless v2 (0.5 ACU min) | ~$45–$65 | — |
| DynamoDB (on-demand) | — | ~$0.25 |
| S3 (SPA + backups) | ~$0.50 | ~$0.50 |
| CloudFront | ~$0.50 | ~$0.50 |
| Secrets Manager (1 secret) | ~$0.40 | ~$0.40 |
| CloudWatch Logs | ~$0.50 | ~$0.50 |
| SES (email) | ~$0.10 | ~$0.10 |
| Langfuse Cloud | Free | Free |
| **Total** | **~$48–$68/mo** | **~$3–$4/mo** |

### Trade-off Summary

| Factor | Aurora Serverless v2 | DynamoDB |
|---|---|---|
| Monthly cost | ~$48–$68 | ~$3–$4 |
| Code changes | Minimal (swap connection string) | Significant (rewrite memory layer) |
| Schema migration | None — keep SQLAlchemy as-is | Denormalize 7 FK relationships |
| Query flexibility | Full SQL (joins, aggregates, date ranges) | Limited — requires GSIs + denormalization |
| Dashboard queries | No changes to dashboard_queries.py | Rewrite all 13 dashboard query methods |
| Backup strategy | RDS automated snapshots (free) | On-demand backups or export to S3 |
| Migration effort | ~1 day | ~3–5 days |
| Operational complexity | Manage ACU scaling, VPC networking | Fully managed, zero config |

---

## 2. Target Architecture

### Architecture Diagram

```
                         ┌──────────────────────────────────────────────────┐
                         │                  Cloudflare                      │
                         │  DNS + WAF + DDoS Protection                    │
                         └──────┬──────────────────────┬───────────────────┘
                                │                      │
                    dashboard.* │              api.*   │
                    (DNS only)  │          (proxied)   │
                                ▼                      ▼
                    ┌───────────────────┐   ┌─────────────────────┐
                    │    CloudFront     │   │   API Gateway        │
                    │    (S3 Origin)    │   │   (HTTP API)         │
                    └───────┬───────────┘   └──────┬──────────────┘
                            │                      │
                            ▼                      ├──── Auth0 Lambda Authorizer
                    ┌───────────────────┐          │
                    │   S3 Bucket       │          ▼
                    │   (SPA Assets)    │   ┌─────────────────────┐
                    │   - index.html    │   │   API Lambda         │
                    │   - dashboard.js  │   │   - /health          │
                    │   - output.css    │   │   - /approve/{token} │
                    └───────────────────┘   │   - /reject/{token}  │
                                            │   - /status/{token}  │
                                            │   - /dashboard/api/* │
                                            └──────┬──────────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────┐
                    │                              │                  │
                    ▼                              ▼                  ▼
          ┌──────────────────┐          ┌──────────────┐   ┌──────────────┐
          │ Secrets Manager  │          │ Aurora / Dyn. │   │     SES      │
          │ (JSON blob)      │          │ (Database)    │   │   (Email)    │
          └──────────────────┘          └──────────────┘   └──────────────┘
                    ▲                          ▲
                    │                          │
          ┌────────┴──────────────────────────┴──────────────────────┐
          │                    Step Functions                         │
          │                  (Daily Workflow)                         │
          │                                                          │
          │  ┌─────────┐  ┌─────────┐  ┌───────────┐  ┌──────────┐ │
          │  │ Fetch    │→ │ Fetch   │→ │ Dedup.    │→ │Summarize │ │
          │  │ Scores   │  │Articles │  │ Articles  │  │(Map/team)│ │
          │  └─────────┘  └─────────┘  └───────────┘  └──────────┘ │
          │                                                │         │
          │  ┌─────────┐  ┌─────────┐  ┌───────────┐      ▼         │
          │  │Housekeep│← │ Send    │← │ Create    │← ┌──────────┐ │
          │  │ + Drift  │  │Approval │  │ Taxonomy  │  │Draft +   │ │
          │  └─────────┘  └─────────┘  └───────────┘  │Evaluate  │ │
          │                                            └──────────┘ │
          └──────────────────────────────────────────────────────────┘
                    ▲
                    │
          ┌────────┴──────────┐          ┌──────────────────┐
          │ EventBridge       │          │  Langfuse Cloud   │
          │ (6:00 AM CT cron) │          │  (Free Tier)      │
          └───────────────────┘          └──────────────────┘
```

### Domain Routing via Cloudflare

The domain is registered and managed in Cloudflare. Two subdomains route to different AWS services:

| Subdomain | Target | Cloudflare Proxy Mode | Notes |
|---|---|---|---|
| `dashboard.chicagosportsrecap.com` | CloudFront distribution | DNS only (gray cloud) | Avoids double-CDN; CloudFront handles caching + HTTPS |
| `api.chicagosportsrecap.com` | API Gateway custom domain | Proxied (orange cloud) | Cloudflare WAF + DDoS in front of API |

**Setup steps:**

1. Create ACM certificates in `us-east-1` for both subdomains (DNS validation via Cloudflare CNAME records)
2. Configure CloudFront alternate domain name with the dashboard cert
3. Configure API Gateway custom domain with the API cert
4. In Cloudflare DNS:
   - `dashboard` → CNAME to `d1234.cloudfront.net` (gray cloud)
   - `api` → CNAME to `d-abcd1234.execute-api.us-east-2.amazonaws.com` (orange cloud)
5. Cloudflare SSL mode: **Full (strict)** for both — AWS terminates TLS with valid ACM certs

**Alternative: Skip CloudFront entirely**

If you want all traffic routed through Cloudflare's CDN (keeping Cloudflare security features on the dashboard too):

- Point the dashboard subdomain directly to the S3 website endpoint via Cloudflare proxy (orange cloud)
- Enable Cloudflare's caching rules for static assets
- This eliminates CloudFront cost and keeps a single CDN layer
- Trade-off: S3 website endpoints don't support HTTPS natively, so Cloudflare handles TLS termination (SSL mode: **Flexible** or use a Cloudflare Worker to proxy to S3)

---

## 3. Database Migration

### Current Schema

14 SQLAlchemy models across 6 logical domains:

| Domain | Tables | Relationships |
|---|---|---|
| Articles | `articles`, `article_summaries` | Independent (deduplicated by URL) |
| Workflow | `workflow_runs`, `api_call_results`, `summary_stats` | `api_call_results.workflow_run_id` → `workflow_runs.id`, `summary_stats.workflow_run_id` → `workflow_runs.id` |
| Blog Drafts | `summaries`, `evaluations`, `improvement_suggestions`, `summary_categories`, `summary_tags` | All FK to `summaries.id`; `summary_categories` → `categories.id`, `summary_tags` → `tags.id` |
| Approvals | `pending_approvals` | Independent |
| Taxonomy | `categories`, `tags` | Referenced by `summary_categories`, `summary_tags` |
| Drift | `drift_alerts` | Independent |
| OAuth | `oauth_tokens` | Independent |

### Current Data Volume

- Database size: ~2.5 MB (growing ~250 KB/day with 30-day retention)
- ~114 new articles/day, ~12 summaries/day, 1 workflow run/day
- 10 daily backups retained (~2.7 MB each)

---

### Option A: Aurora Serverless v2

**Estimated cost: ~$45–$65/mo**

Aurora Serverless v2 preserves the existing relational schema and SQLAlchemy ORM. The migration is a connection string swap with minor cleanup.

#### Code Changes

**`memory/database.py`** — Replace SQLite engine with PostgreSQL:

```python
# Before
def get_engine(db_path: str = 'data/articles.db') -> Engine:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return create_engine(f'sqlite:///{db_path}')

# After
def get_engine() -> Engine:
    db_url = get_secret('DATABASE_URL')  # from Secrets Manager JSON blob
    return create_engine(db_url, pool_pre_ping=True, pool_size=5)
```

**`memory/database.py`** — Remove SQLite-specific logic:

```python
# Remove: WAL pragma event listener
# Remove: os.chmod(db_path, 0o600) file permissions
# Remove: os.makedirs() directory creation
```

**`memory/backup.py`** — Replace SQLite backup API with RDS-managed backups:

```python
# Remove: backup_database() — sqlite3.connect().backup()
# Remove: purge_old_backups() — file-based cleanup
# Replace with: RDS automated backups (configured in OpenTofu, 30-day retention)
# Optional: Add manual snapshot trigger via boto3 if needed
```

**`memory/memory.py`** — Update config loading:

```python
# Remove: db_path, self.db_path references
# Remove: backup_path, backup_retention_days (handled by RDS)
# Keep: retention_days (for article purge query)
# Keep: log_retention_days (for CloudWatch log retention)
```

**No changes needed to:**
- Any of the 10 memory mixins (articles, approvals, workflow, dashboard_queries, taxonomy, oauth, drift)
- Any tool, agent, or workflow code
- Any SQL queries or ORM relationships

#### Aurora Configuration

```hcl
# OpenTofu — Aurora Serverless v2 cluster
resource "aws_rds_cluster" "main" {
  cluster_identifier     = "chicago-sports-recap"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = "16.4"
  database_name          = "chicagosportsrecap"
  master_username        = "postgres"
  master_password        = var.db_password
  backup_retention_period = 30
  deletion_protection    = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 2.0
  }
}

resource "aws_rds_cluster_instance" "main" {
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version
}
```

#### VPC Considerations

Aurora requires a VPC. The workflow Lambdas and API Lambda must be in the same VPC to reach Aurora:

- Private subnets for Aurora + Lambda
- VPC endpoints for Secrets Manager, S3, SES, and Step Functions (avoids NAT Gateway cost)
- Security group: Lambda → Aurora on port 5432 only

**Cost impact of VPC endpoints vs NAT Gateway:**

| Approach | Monthly Cost |
|---|---|
| NAT Gateway | ~$32 + data transfer |
| VPC endpoints (4 endpoints) | ~$28 ($7/endpoint) |
| VPC endpoints (Interface) | ~$7/endpoint/AZ — use single AZ for non-prod to save |

For a single-AZ non-production setup, 4 VPC endpoints cost ~$28/mo. This is a hidden cost that pushes the Aurora path toward the higher end of the $48–$68 estimate.

---

### Option B: DynamoDB (Multi-Table)

**Estimated cost: ~$0.25/mo**

DynamoDB eliminates the Aurora cost entirely but requires a full rewrite of the memory layer. The schema is split into 7 tables based on logical domain boundaries.

#### Table Design

**Table 1: `Articles`**

Stores fetched articles and their cached summaries.

| Attribute | Type | Key |
|---|---|---|
| `url` | S | PK |
| `entity_type` | S | SK — `ARTICLE` or `SUMMARY` |
| `title` | S | |
| `content` | S | (article content) |
| `source` | S | |
| `team` | S | |
| `published_at` | S | ISO 8601 |
| `fetched_at` | S | ISO 8601 |
| `summary` | S | (summary text, on SUMMARY items) |
| `event_type` | S | (on SUMMARY items) |
| `players_mentioned` | L | (on SUMMARY items) |
| `is_relevant` | BOOL | (on SUMMARY items) |
| `ttl` | N | Unix epoch — 30-day auto-expiry |

GSI: `team-index` — PK: `team`, SK: `fetched_at` (for per-team queries)

**Table 2: `WorkflowRuns`**

Stores workflow runs and their child records (API call results, summary stats).

| Attribute | Type | Key |
|---|---|---|
| `run_id` | S | PK |
| `sk` | S | SK — `RUN`, `API#source_name`, `STATS#team` |
| `started_at` | S | ISO 8601 |
| `completed_at` | S | |
| `status` | S | |
| `skip_reason` | S | |
| `error` | S | |
| `steps_completed` | L | |
| `scores_fetched` | N | |
| `articles_fetched` | N | |
| `articles_new` | N | |
| `summaries_count` | N | |
| `overall_score` | N | |
| `email_sent` | BOOL | |
| `total_input_tokens` | N | |
| `total_output_tokens` | N | |
| `estimated_cost` | N | |
| `usage_by_tool` | M | |
| `checkpoint_data` | M | |
| `revision_tool_calls` | N | |
| `draft_attempts` | N | |
| `score_progression` | L | |
| `draft_iterations` | L | |
| `publish_post_id` | N | |
| `publish_post_url` | S | |
| `publish_success` | BOOL | |
| `source_name` | S | (on API# items) |
| `article_count` | N | (on API# and STATS# items) |
| `error_message` | S | (on API# items) |
| `team` | S | (on STATS# items) |
| `articles_summarized` | N | (on STATS# items) |
| `cache_hits` | N | (on STATS# items) |
| `cache_misses` | N | (on STATS# items) |

GSI: `status-date-index` — PK: `status`, SK: `started_at` (for dashboard queries, date range filters)

**Table 3: `BlogDrafts`**

Stores blog drafts with their evaluations and taxonomy links.

| Attribute | Type | Key |
|---|---|---|
| `summary_id` | S | PK — UUID |
| `sk` | S | SK — `DRAFT`, `EVAL#evaluation_id#criterion`, `SUGGESTION#index`, `CAT#name`, `TAG#name` |
| `created_at` | S | ISO 8601 |
| `title` | S | |
| `html_content` | S | |
| `excerpt` | S | |
| `teams_covered` | L | |
| `article_count` | N | |
| `overall_score` | N | |
| `evaluation_id` | S | (on EVAL# items) |
| `criterion` | S | (on EVAL# items) |
| `score` | N | (on EVAL# items) |
| `reasoning` | S | (on EVAL# items) |
| `suggestion` | S | (on SUGGESTION# items) |
| `category_name` | S | (on CAT# items) |
| `wordpress_id` | N | (on CAT# and TAG# items) |
| `tag_name` | S | (on TAG# items) |

**Table 4: `Approvals`**

Stores pending approval requests.

| Attribute | Type | Key |
|---|---|---|
| `token` | S | PK |
| `status` | S | |
| `created_at` | S | ISO 8601 |
| `expires_at` | S | ISO 8601 |
| `resolved_at` | S | |
| `blog_title` | S | |
| `blog_content` | S | |
| `blog_excerpt` | S | |
| `taxonomy_data` | S | JSON string |
| `evaluation_data` | S | JSON string |
| `summaries_data` | S | JSON string |
| `scores_data` | S | JSON string |
| `feedback` | S | |
| `ttl` | N | Unix epoch — auto-expire after 30 days |

GSI: `status-expires-index` — PK: `status`, SK: `expires_at` (for expired approval checker)

**Table 5: `Taxonomy`**

Stores WordPress categories and tags.

| Attribute | Type | Key |
|---|---|---|
| `pk` | S | PK — `CATEGORY#name` or `TAG#name` |
| `name` | S | |
| `entity_type` | S | `category` or `tag` |
| `description` | S | |
| `wordpress_id` | N | |

**Table 6: `DriftAlerts`**

Stores drift detection alerts.

| Attribute | Type | Key |
|---|---|---|
| `metric_name` | S | PK |
| `triggered_at` | S | SK — ISO 8601 |
| `status` | S | `active` or `resolved` |
| `resolved_at` | S | |
| `metric_value` | N | |
| `threshold` | N | |
| `run_id` | S | |

GSI: `status-index` — PK: `status` (for active alert queries)

**Table 7: `OAuthTokens`**

Stores encrypted OAuth tokens.

| Attribute | Type | Key |
|---|---|---|
| `service` | S | PK |
| `access_token` | S | Encrypted |
| `blog_id` | S | |
| `blog_url` | S | |
| `created_at` | S | ISO 8601 |

#### Memory Layer Rewrite

All 10 memory mixins must be rewritten to use boto3 DynamoDB instead of SQLAlchemy. The Memory facade class and its public API remain unchanged — only the internal implementation changes.

**Files requiring full rewrite:**

| File | Current (SQLAlchemy) | New (boto3) | Complexity |
|---|---|---|---|
| `memory/database.py` | Engine, Base, 14 ORM models, get_session | DynamoDB resource init, table references | Medium |
| `memory/articles.py` | Article/ArticleSummary queries | get_item/put_item on Articles table | Low |
| `memory/approvals.py` | PendingApproval queries | get_item/put_item/query on Approvals table | Low |
| `memory/workflow.py` | WorkflowRun + child record queries | put_item/update_item/query on WorkflowRuns table | Medium |
| `memory/dashboard_queries.py` | Complex joins (Evaluation↔Summary, SummaryStats↔WorkflowRun) | Query + client-side aggregation across WorkflowRuns and BlogDrafts tables | **High** |
| `memory/taxonomy.py` | Category/Tag queries | get_item/put_item on Taxonomy table | Low |
| `memory/oauth.py` | OAuthToken queries | get_item/put_item on OAuthTokens table | Low |
| `memory/backup.py` | SQLite backup API + file ops | Remove entirely — DynamoDB PITR or on-demand backups via OpenTofu | Low |
| `memory/drift.py` | DriftAlert queries | get_item/put_item/query on DriftAlerts table | Low |
| `memory/memory.py` | SQLAlchemy engine init | boto3 DynamoDB resource init | Low |

**Hardest migration: `dashboard_queries.py`**

The current dashboard queries rely on SQL joins that don't exist in DynamoDB:

| Query | Current SQL Approach | DynamoDB Approach |
|---|---|---|
| `get_evaluation_trends()` | JOIN `evaluations` ↔ `summaries` on `summary_id`, GROUP BY date | Query BlogDrafts table for EVAL# items, client-side group by `created_at` from parent DRAFT item (requires batch get) |
| `get_api_health()` | Query `api_call_results` with date filter | Query WorkflowRuns table with SK prefix `API#`, filter by date |
| `get_summary_cache_stats()` | JOIN `summary_stats` ↔ `workflow_runs`, aggregate | Query WorkflowRuns table with SK prefix `STATS#`, client-side aggregate |
| `get_run_iterations()` | JOIN `evaluations` ↔ `summaries`, match by `started_at` | Query BlogDrafts for EVAL# items + DRAFT item, assemble client-side |
| `get_llm_stats()` | Query `workflow_runs` with date filter, aggregate tokens | Query WorkflowRuns GSI `status-date-index`, client-side aggregate |

**DynamoDB TTL for automatic cleanup:**

Instead of the current `purge_old_articles()` and `purge_old_backups()` methods, DynamoDB TTL handles expiry automatically:

- `Articles` table: `ttl` attribute set to `fetched_at + 30 days`
- `Approvals` table: `ttl` attribute set to `created_at + 30 days`
- No Lambda or cron needed for cleanup

#### DynamoDB Configuration

```hcl
# OpenTofu — example for Articles table
resource "aws_dynamodb_table" "articles" {
  name         = "chicago-sports-recap-articles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "url"
  range_key    = "entity_type"

  attribute {
    name = "url"
    type = "S"
  }

  attribute {
    name = "entity_type"
    type = "S"
  }

  attribute {
    name = "team"
    type = "S"
  }

  attribute {
    name = "fetched_at"
    type = "S"
  }

  global_secondary_index {
    name            = "team-index"
    hash_key        = "team"
    range_key       = "fetched_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }
}
```

---

---

## 4. Step Functions Workflow

### Why Step Functions?

The current workflow (`daily_workflow.py`) is a linear 8-step pipeline with manual checkpoint/resume logic, retry with exponential backoff, and a `cp_data` dict passed between steps. Step Functions replaces all of this natively:

| Current Implementation | Step Functions Equivalent |
|---|---|
| `_checkpoint_step()` / `save_checkpoint()` | Automatic — state is persisted between steps |
| `_step_done()` check for resume | Automatic — failed executions resume from the failed state |
| `cp_data` dict passed between steps | Input/output JSON passed between states |
| `run_scheduled_workflow()` retry loop (5 retries, exponential backoff) | `Retry` field on each state with `BackoffRate` |
| `check_expired_approvals()` on interval | Separate EventBridge rule → dedicated Lambda |
| `max_articles_per_team` parameter | Passed as execution input |

### State Machine Definition

```
                    ┌──────────────────┐
                    │   EventBridge    │
                    │  (6:00 AM CT)    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  FetchScores     │
                    │  (Lambda)        │
                    └────────┬─────────┘
                             │ {scores, score_count}
                             ▼
                    ┌──────────────────┐
                    │  FetchArticles   │
                    │  (Lambda)        │
                    └────────┬─────────┘
                             │ {articles, new_article_count}
                             ▼
                    ┌──────────────────┐
                    │  CheckNewArticles│  ◄── Choice state
                    │  (new_count > 0?)│
                    └───┬──────────┬───┘
                   No   │          │ Yes
                        ▼          ▼
              ┌──────────────┐  ┌──────────────────┐
              │ SkipWorkflow │  │  Deduplicate     │
              │ (Succeed)    │  │  (Lambda)        │
              └──────────────┘  └────────┬─────────┘
                                         │ {unique_articles}
                                         ▼
                                ┌──────────────────┐
                                │  Summarize       │
                                │  (Map state)     │
                                │  ┌────────────┐  │
                                │  │ Per-team   │  │
                                │  │ Lambda     │  │
                                │  └────────────┘  │
                                └────────┬─────────┘
                                         │ {summaries, relevant}
                                         ▼
                                ┌──────────────────┐
                                │CheckRelevant     │  ◄── Choice state
                                │(relevant > 0?)   │
                                └───┬──────────┬───┘
                               No   │          │ Yes
                                    ▼          ▼
                          ┌──────────────┐  ┌──────────────────┐
                          │ SkipNoDrafts │  │  DraftAndEvaluate│
                          │ (Succeed)    │  │  (Lambda)        │
                          └──────────────┘  └────────┬─────────┘
                                                     │ {best_draft, best_evaluation}
                                                     ▼
                                            ┌──────────────────┐
                                            │  CreateTaxonomy  │
                                            │  (Lambda)        │
                                            └────────┬─────────┘
                                                     │ {categories, tags}
                                                     ▼
                                            ┌──────────────────┐
                                            │  SendApproval    │
                                            │  (Lambda)        │
                                            └────────┬─────────┘
                                                     │ {token, email_sent}
                                                     ▼
                                            ┌──────────────────┐
                                            │  Housekeeping    │
                                            │  (Lambda)        │
                                            │  - purge old data│
                                            │  - drift check   │
                                            │  - update run    │
                                            └──────────────────┘
```

### State Machine (Amazon States Language)

```json
{
  "Comment": "Chicago Sports Recap — Daily Workflow",
  "StartAt": "FetchScores",
  "States": {
    "FetchScores": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:csr-workflow-fetch-scores",
      "ResultPath": "$.scores_result",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 60,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Next": "FetchArticles"
    },
    "FetchArticles": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:csr-workflow-fetch-articles",
      "ResultPath": "$.articles_result",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 60,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Next": "CheckNewArticles"
    },
    "CheckNewArticles": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.articles_result.new_article_count",
          "NumericGreaterThan": 0,
          "Next": "Deduplicate"
        }
      ],
      "Default": "SkipNoArticles"
    },
    "SkipNoArticles": {
      "Type": "Succeed",
      "Comment": "No new articles — skip today's workflow."
    },
    "Deduplicate": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:csr-workflow-deduplicate",
      "ResultPath": "$.dedup_result",
      "Next": "Summarize"
    },
    "Summarize": {
      "Type": "Map",
      "ItemsPath": "$.dedup_result.articles_by_team",
      "MaxConcurrency": 3,
      "Iterator": {
        "StartAt": "SummarizeTeam",
        "States": {
          "SummarizeTeam": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:csr-workflow-summarize",
            "Retry": [
              {
                "ErrorEquals": ["States.TaskFailed"],
                "IntervalSeconds": 30,
                "MaxAttempts": 2,
                "BackoffRate": 2.0
              }
            ],
            "End": true
          }
        }
      },
      "ResultPath": "$.summarize_result",
      "Next": "CheckRelevant"
    },
    "CheckRelevant": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.summarize_result.relevant_count",
          "NumericGreaterThan": 0,
          "Next": "DraftAndEvaluate"
        }
      ],
      "Default": "SkipNoRelevant"
    },
    "SkipNoRelevant": {
      "Type": "Succeed",
      "Comment": "No relevant summaries — skip draft."
    },
    "DraftAndEvaluate": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:csr-workflow-draft-evaluate",
      "TimeoutSeconds": 600,
      "ResultPath": "$.draft_result",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 120,
          "MaxAttempts": 2,
          "BackoffRate": 2.0
        }
      ],
      "Next": "CreateTaxonomy"
    },
    "CreateTaxonomy": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:csr-workflow-taxonomy",
      "ResultPath": "$.taxonomy_result",
      "Next": "SendApproval"
    },
    "SendApproval": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:csr-workflow-send-approval",
      "ResultPath": "$.approval_result",
      "Next": "Housekeeping"
    },
    "Housekeeping": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:REGION:ACCOUNT:function:csr-workflow-housekeeping",
      "End": true
    }
  }
}
```

### Key Design Decisions

**Map state for summarization**: The current workflow loops over teams sequentially. The Map state parallelizes this — up to `MaxConcurrency: 3` teams summarized simultaneously. The Deduplicate Lambda must reshape its output to group articles by team:

```python
# Deduplicate Lambda output shape
{
    "unique_articles": [...],
    "duplicate_count": 1,
    "articles_by_team": [
        {"team": "Chicago Cubs", "articles": [...]},
        {"team": "Chicago Bears", "articles": [...]},
        ...
    ]
}
```

Each Map iteration receives one team object and invokes the Summarize Lambda, which summarizes up to `max_articles_per_team` articles for that team.

**DraftAndEvaluate timeout**: This state runs the RevisionAgent, which makes up to 6 LLM tool calls (draft → evaluate → revise cycles). Based on log data, this takes 3–5 minutes. The 600-second timeout provides headroom. The Retry config gives 2 additional attempts with 2-minute initial delay if the LLM provider has a transient failure.

**Failure notification**: Step Functions has a `Catch` field that can route failures to an error-handling state. Add a `Catch` block on each Task state that routes to a `NotifyFailure` Lambda (replaces the current `send_failure_email()` call in the `except` block of `run_daily_workflow`):

```json
"Catch": [
  {
    "ErrorEquals": ["States.ALL"],
    "ResultPath": "$.error_info",
    "Next": "NotifyFailure"
  }
]
```

**Expired approval checker**: Currently runs as an APScheduler interval job inside the Flask process. In the serverless architecture, this becomes a separate EventBridge rule triggering a dedicated Lambda every 60 minutes:

```
EventBridge Rule (rate: 60 minutes) → csr-check-expired-approvals Lambda
```

### Code Removed After Migration

The following code becomes unnecessary with Step Functions:

| File | Code to Remove | Reason |
|---|---|---|
| `workflow/daily_workflow.py` | `_step_done()`, `_checkpoint_step()` | Step Functions tracks state automatically |
| `workflow/daily_workflow.py` | `cp_data` dict, all checkpoint restore logic | Input/output JSON replaces this |
| `workflow/daily_workflow.py` | `resume_run_id` parameter and resume logic | Step Functions handles retries/resume natively |
| `memory/workflow.py` | `save_checkpoint()`, `get_checkpoint()` | No longer needed |
| `memory/database.py` | `checkpoint_data` column on `WorkflowRun` | Can be dropped from schema |
| `server/approval_server.py` | `run_scheduled_workflow()` retry loop | Step Functions Retry config replaces this |
| `server/approval_server.py` | `start_scheduler()`, APScheduler setup | EventBridge replaces scheduling |
| `server/approval_server.py` | `check_expired_approvals()` interval job | Separate EventBridge + Lambda replaces this |
| `main.py` | `--resume` CLI argument handling | Step Functions console provides this |
| `requirements.txt` | `apscheduler>=3.10.0` | No longer needed |

---

## 5. Lambda Functions

### Function Inventory

11 Lambda functions organized into three groups:

#### Workflow Lambdas (invoked by Step Functions)

| Function Name | Source Code | Memory | Timeout | Trigger |
|---|---|---|---|---|
| `csr-workflow-fetch-scores` | `lambdas/workflow/fetch_scores.py` | 256 MB | 120s | Step Functions |
| `csr-workflow-fetch-articles` | `lambdas/workflow/fetch_articles.py` | 256 MB | 120s | Step Functions |
| `csr-workflow-deduplicate` | `lambdas/workflow/deduplicate.py` | 256 MB | 60s | Step Functions |
| `csr-workflow-summarize` | `lambdas/workflow/summarize.py` | 512 MB | 300s | Step Functions (Map) |
| `csr-workflow-draft-evaluate` | `lambdas/workflow/draft_evaluate.py` | 512 MB | 600s | Step Functions |
| `csr-workflow-taxonomy` | `lambdas/workflow/taxonomy.py` | 256 MB | 30s | Step Functions |
| `csr-workflow-send-approval` | `lambdas/workflow/send_approval.py` | 256 MB | 60s | Step Functions |
| `csr-workflow-housekeeping` | `lambdas/workflow/housekeeping.py` | 256 MB | 120s | Step Functions |

#### API Lambdas (invoked by API Gateway)

| Function Name | Source Code | Memory | Timeout | Trigger |
|---|---|---|---|---|
| `csr-api-handler` | `lambdas/api/handler.py` | 256 MB | 30s | API Gateway |
| `csr-api-authorizer` | `lambdas/api/authorizer.py` | 128 MB | 10s | API Gateway |

#### Scheduled Lambdas (invoked by EventBridge)

| Function Name | Source Code | Memory | Timeout | Trigger |
|---|---|---|---|---|
| `csr-check-expired-approvals` | `lambdas/scheduled/check_expired.py` | 128 MB | 30s | EventBridge (every 60 min) |

### Shared Lambda Layer

All Lambdas share a common layer containing the application code and dependencies. This avoids duplicating the memory layer, tools, agent code, and config across every function.

```
layers/
└── csr-shared/
    └── python/
        ├── agent/              # base_agent, claude_client, revision_agent, etc.
        ├── config/             # all YAML config files
        ├── constants/          # enums.py
        ├── memory/             # all memory mixins + database.py
        ├── models/             # input/output Pydantic models
        ├── prompts/            # prompt templates
        ├── tools/              # all tool implementations
        ├── utils/              # collectors, logger, http, secrets, etc.
        └── requirements.txt    # pip install -t . into this directory
```

Layer size estimate: ~50 MB zipped (Python deps dominate — anthropic, sqlalchemy, google-genai, langfuse, pydantic, beautifulsoup4, cryptography, rapidfuzz).

Lambda layer limit is 250 MB unzipped. If the layer exceeds this, split into two layers:
- `csr-deps` — third-party packages only
- `csr-app` — application code only (agent/, memory/, tools/, etc.)

### Lambda Handler Patterns

Each workflow Lambda follows the same pattern — receive Step Functions input, call existing tool/logic, return output for the next state:

**Example: `lambdas/workflow/fetch_scores.py`**

```python
import json
from memory.memory import Memory
from models.inputs.fetch_scores_input import FetchScoresInput
from tools.fetch_scores_tool import FetchScoresTool

memory = Memory()       # initialized once at cold start
tool = FetchScoresTool() # initialized once at cold start

def handler(event, context):
    run_id = event.get("run_id")
    output = tool.execute(FetchScoresInput(run_id=run_id))
    return {
        "scores": output.scores,
        "score_count": output.score_count,
        "errors": output.errors,
    }
```

**Example: `lambdas/workflow/summarize.py`** (invoked per-team by Map state)

```python
import json
from memory.memory import Memory
from models.inputs.summarize_article_input import SummarizeArticleInput
from tools.summarize_article_tool import SummarizeArticleTool
from utils.consolidate import consolidate_summaries

memory = Memory()
tool = SummarizeArticleTool()

def handler(event, context):
    team = event["team"]
    articles = event["articles"]
    max_per_team = event.get("max_articles_per_team", 2)

    top_articles = sorted(
        articles,
        key=lambda a: a.get("relevance_score", 0),
        reverse=True,
    )[:max_per_team]

    summaries = []
    stats = {"team": team, "articles_fetched": len(articles),
             "articles_summarized": 0, "cache_hits": 0, "cache_misses": 0}

    for article in top_articles:
        summary = tool.execute(SummarizeArticleInput(
            url=article["url"],
            title=article["title"],
            team=team,
            published_at=article.get("publishedAt", ""),
        ))
        summaries.append(summary.model_dump())
        stats["articles_summarized"] += 1
        if tool.last_cache_hit:
            stats["cache_hits"] += 1
        else:
            stats["cache_misses"] += 1

    relevant = [s for s in summaries if s.get("is_relevant")]
    relevant = consolidate_summaries(relevant)

    return {
        "team": team,
        "summaries": summaries,
        "relevant": relevant,
        "stats": stats,
    }
```

**Example: `lambdas/workflow/draft_evaluate.py`** (longest-running Lambda)

```python
from agent.revision_agent import RevisionAgent
from memory.memory import Memory

memory = Memory()

def handler(event, context):
    # Flatten Map state output: list of per-team results → combined lists
    all_relevant = []
    all_summaries = []
    all_stats = []
    for team_result in event["summarize_result"]:
        all_relevant.extend(team_result["relevant"])
        all_summaries.extend(team_result["summaries"])
        all_stats.append(team_result["stats"])

    scores = event["scores_result"]["scores"]

    # Load rejection feedback
    rejection_feedback = None
    recent_rejection = memory.get_most_recent_rejection()
    if recent_rejection:
        rejection_feedback = recent_rejection["feedback"]

    agent = RevisionAgent()
    result = agent.run(
        summaries=all_relevant,
        scores=scores,
        rejection_feedback=rejection_feedback,
    )

    # Persist draft + evaluations
    summary_id = memory.save_blog_draft({
        "title": result["best_draft"]["title"],
        "content": result["best_draft"]["content"],
        "excerpt": result["best_draft"]["excerpt"],
        "teams_covered": result["best_draft"]["teams_covered"],
        "article_count": result["best_draft"]["article_count"],
        "overall_score": result["best_evaluation"]["overall_score"],
    })
    for eval_data in result["all_evaluations"]:
        memory.save_evaluation(summary_id, eval_data)

    return {
        "best_draft": result["best_draft"],
        "best_evaluation": result["best_evaluation"],
        "all_evaluations": result["all_evaluations"],
        "all_drafts": result.get("all_drafts", []),
        "all_summaries": all_summaries,
        "all_stats": all_stats,
        "relevant": all_relevant,
        "summary_id": summary_id,
    }
```

**Example: `lambdas/api/authorizer.py`** (Auth0 JWT validation)

```python
import json
import urllib.request
from jose import jwt, JWTError

# Cached at cold start
_jwks_cache = None
_auth0_domain = None

def _get_config():
    global _auth0_domain
    if not _auth0_domain:
        import yaml
        with open("config/auth.yaml", "r") as f:
            config = yaml.safe_load(f)
        _auth0_domain = config["auth0"]["domain"]
    return _auth0_domain

def _get_jwks(domain):
    global _jwks_cache
    if not _jwks_cache:
        url = f"https://{domain}/.well-known/jwks.json"
        response = urllib.request.urlopen(url)
        _jwks_cache = json.loads(response.read())
    return _jwks_cache

def handler(event, context):
    token = event.get("authorizationToken", "").replace("Bearer ", "")
    method_arn = event["methodArn"]

    try:
        domain = _get_config()
        jwks = _get_jwks(domain)
        header = jwt.get_unverified_header(token)

        key = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
        payload = jwt.decode(
            token, key,
            algorithms=["RS256"],
            audience=f"https://chicago-sports-recap/api",
            issuer=f"https://{domain}/",
        )

        return generate_policy(
            payload.get("email", "user"),
            "Allow",
            method_arn,
            context={"email": payload.get("email", ""), "role": payload.get("role", "anonymous")},
        )
    except (JWTError, StopIteration, Exception):
        return generate_policy("user", "Deny", method_arn)

def generate_policy(principal, effect, resource, context=None):
    policy = {
        "principalId": principal,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "execute-api:Invoke",
                "Effect": effect,
                "Resource": resource,
            }],
        },
    }
    if context:
        policy["context"] = context
    return policy
```

### Cold Start Considerations

| Lambda | Cold Start Impact | Mitigation |
|---|---|---|
| Workflow Lambdas | Irrelevant — runs once/day, cold start is expected | None needed |
| `csr-api-handler` | Noticeable on first request after idle (~2–5s) | Provisioned concurrency (1) if latency matters, or accept it since approval traffic is infrequent |
| `csr-api-authorizer` | Adds to first-request latency | Lightweight (128 MB, no heavy deps) — cold start ~500ms |
| `csr-check-expired-approvals` | Irrelevant — runs hourly | None needed |

For the API handler, the dashboard SPA can show a loading spinner on first load. Provisioned concurrency ($0.015/hr = ~$11/mo) is optional and only worth it if you find the cold start unacceptable.

### Email: SMTP → SES Migration

The current `send_approval_email_tool.py` uses direct SMTP with Gmail credentials. In the serverless architecture, replace SMTP with Amazon SES:

| Current | Serverless |
|---|---|
| `smtplib.SMTP` + Gmail App Password | `boto3.client('ses').send_email()` |
| `EMAIL_FROM`, `EMAIL_PASSWORD`, `EMAIL_SMTP_SERVER`, `EMAIL_SMTP_PORT` secrets | `EMAIL_FROM` only (SES handles auth via IAM role) |
| Gmail rate limits | SES sending limits (200/day in sandbox, request production for more) |

This removes 3 secrets from the Secrets Manager JSON blob and eliminates the Gmail App Password dependency. The Lambda execution role gets `ses:SendEmail` permission.

SES setup:
1. Verify the sender email address (or domain) in SES
2. Request production access if needed (sandbox limits to verified recipients only)
3. Update `send_approval_email_tool.py`, `send_failure_email()`, `send_drift_alert_email()`, and `send_drift_recovery_email()` to use boto3 SES client instead of smtplib

### Lambda Directory Structure

```
lambdas/
├── workflow/
│   ├── fetch_scores.py
│   ├── fetch_articles.py
│   ├── deduplicate.py
│   ├── summarize.py
│   ├── draft_evaluate.py
│   ├── taxonomy.py
│   ├── send_approval.py
│   └── housekeeping.py
├── api/
│   ├── handler.py
│   └── authorizer.py
└── scheduled/
    └── check_expired.py
```

Each file is a thin handler that imports from the shared layer. No business logic lives in the handler files — they delegate to the existing tools, agents, and memory layer.

### IAM Permissions (per Lambda group)

| Lambda Group | Required Permissions |
|---|---|
| Workflow Lambdas | `secretsmanager:GetSecretValue`, `ses:SendEmail`, DB access (Aurora VPC or DynamoDB tables), `logs:*` |
| API Handler | `secretsmanager:GetSecretValue`, DB access, `logs:*` |
| API Authorizer | `logs:*` (reads JWKS from Auth0 directly, no AWS resources) |
| Check Expired | `secretsmanager:GetSecretValue`, DB access, `logs:*` |

For Aurora: Lambdas need VPC access (ENI creation: `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface`).

For DynamoDB: Lambdas need `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Query`, `dynamodb:BatchWriteItem` on the 7 tables + their GSIs.

---

## 6. API Gateway + Lambda

### Why HTTP API (not REST API)?

API Gateway offers two products. HTTP API is the right choice here:

| Factor | HTTP API | REST API |
|---|---|---|
| Cost | $1.00/million requests | $3.50/million requests |
| Latency | Lower (~10ms routing) | Higher (~30ms routing) |
| Lambda authorizers | Supported (v2 payload) | Supported (v1 payload) |
| CORS | Built-in | Manual configuration |
| WebSocket | Not supported | Supported |
| Usage plans / API keys | Not supported | Supported |
| WAF integration | Not native (use Cloudflare) | Native |

At your traffic volume (~1–5 requests/day for approvals, ~50/day for dashboard), the cost difference is negligible. HTTP API wins on simplicity and latency. WAF is handled by Cloudflare in front of the API.

### Route Mapping

Every current Flask route maps to an API Gateway route backed by the single `csr-api-handler` Lambda:

#### Public Routes (no auth)

| Method | Route | Current Source | Notes |
|---|---|---|---|
| `GET` | `/health` | `approval_server.py` → `health()` | Returns `{"status": "ok"}` |
| `GET` | `/dashboard/api/runs` | `dashboard.py` → `api_runs()` | |
| `GET` | `/dashboard/api/runs/window` | `dashboard.py` → `api_runs_window()` | Query params: `offset`, `limit` |
| `GET` | `/dashboard/api/runs/range` | `dashboard.py` → `api_runs_range()` | Query params: `start`, `end` |
| `GET` | `/dashboard/api/iterations/{run_id}` | `dashboard.py` → `api_iterations()` | |
| `GET` | `/dashboard/api/evaluations` | `dashboard.py` → `api_evaluations()` | |
| `GET` | `/dashboard/api/health` | `dashboard.py` → `api_health()` | |
| `GET` | `/dashboard/api/approvals` | `dashboard.py` → `api_approvals()` | |
| `GET` | `/dashboard/api/teams` | `dashboard.py` → `api_teams()` | |
| `GET` | `/dashboard/api/sources` | `dashboard.py` → `api_sources()` | |
| `GET` | `/dashboard/api/llm` | `dashboard.py` → `api_llm()` | |
| `GET` | `/dashboard/api/cache` | `dashboard.py` → `api_cache()` | |
| `GET` | `/dashboard/api/drift` | `dashboard.py` → `api_drift()` | |

#### Protected Routes (Auth0 JWT required)

| Method | Route | Current Source | Required Role | Notes |
|---|---|---|---|---|
| `GET` | `/approve/{token}` | `approval_server.py` → `approve()` | editor | Approves + triggers WordPress publish |
| `GET` | `/reject/{token}` | `approval_server.py` → `reject()` GET | editor | Shows rejection form |
| `POST` | `/reject/{token}` | `approval_server.py` → `reject()` POST | editor | Submits rejection with feedback |
| `GET` | `/status/{token}` | `approval_server.py` → `status()` | editor | Shows approval status |

#### Removed Routes

| Route | Reason |
|---|---|
| `GET /oauth/start` | WordPress token is long-lived; stored directly in Secrets Manager |
| `GET /oauth/callback` | No OAuth flow needed — token managed out-of-band |
| `GET /auth/login` | Auth0 SPA SDK handles login client-side |
| `GET /auth/callback` | Auth0 SPA SDK handles callback client-side |
| `GET /auth/logout` | Auth0 SPA SDK handles logout client-side |
| `GET /` | Root redirect to WordPress — handled by Cloudflare redirect rule |
| `GET /dashboard` | Served by S3/CloudFront (SPA), not the API |
| `GET /dashboard/iterations` | Served by S3/CloudFront (SPA), not the API |

### API Lambda Handler

The `csr-api-handler` Lambda replaces the Flask app. It uses a lightweight router pattern instead of Flask to avoid the framework overhead:

```python
import json
from memory.memory import Memory
from tools.wordpress_publish_tool import WordPressPublishTool
from models.inputs.wordpress_publish_input import WordPressPublishInput
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

memory = Memory()  # cold start init

# Load config once
import yaml
with open("config/orchestration.yaml", "r") as f:
    _orch = yaml.safe_load(f)
_expiry_seconds = _orch["approval"]["expiry_hours"] * 3600

from utils.secrets import get_secret
_serializer = URLSafeTimedSerializer(get_secret("APPROVAL_SECRET_KEY"))


def handler(event, context):
    method = event["requestContext"]["http"]["method"]
    path = event["rawPath"]
    query = event.get("queryStringParameters") or {}
    body = event.get("body", "")
    auth_context = event.get("requestContext", {}).get("authorizer", {}).get("lambda", {})

    # --- Dashboard API (public) ---
    if path == "/health":
        return _json_response({"status": "ok"})

    if path == "/dashboard/api/runs":
        return _json_response(memory.get_recent_runs(30))

    if path == "/dashboard/api/runs/window":
        offset = int(query.get("offset", 0))
        limit = int(query.get("limit", 7))
        total = memory.get_total_run_count()
        runs = memory.get_runs_in_window(offset, limit)
        return _json_response({"runs": runs, "total": total, "offset": offset, "limit": limit})

    if path == "/dashboard/api/runs/range":
        start = query.get("start", "")
        end = query.get("end", "")
        if not start or not end:
            return _json_response({"error": "start and end parameters required"}, 400)
        return _json_response({"runs": memory.get_runs_in_range(start, end)})

    if path.startswith("/dashboard/api/iterations/"):
        run_id = path.split("/dashboard/api/iterations/", 1)[1]
        data = memory.get_run_iterations(run_id)
        if not data:
            return _json_response({"error": "Run not found"}, 404)
        return _json_response(data)

    if path == "/dashboard/api/evaluations":
        return _json_response(memory.get_evaluation_trends(30))

    if path == "/dashboard/api/health":
        return _json_response(memory.get_api_health(30))

    if path == "/dashboard/api/approvals":
        return _json_response(memory.get_approval_stats(30))

    if path == "/dashboard/api/teams":
        return _json_response(memory.get_team_coverage(30))

    if path == "/dashboard/api/sources":
        return _json_response(memory.get_source_distribution(30))

    if path == "/dashboard/api/llm":
        return _json_response(memory.get_llm_stats(30))

    if path == "/dashboard/api/cache":
        return _json_response(memory.get_summary_cache_stats(30))

    if path == "/dashboard/api/drift":
        alerts = memory.get_active_drift_alerts()
        return _json_response({"active_alerts": alerts, "count": len(alerts)})

    # --- Approval routes (protected — authorizer has already validated JWT) ---
    if path.startswith("/approve/"):
        return _handle_approve(path.split("/approve/", 1)[1], auth_context)

    if path.startswith("/reject/"):
        token = path.split("/reject/", 1)[1]
        if method == "POST":
            return _handle_reject_post(token, body, auth_context)
        return _handle_reject_form(token, auth_context)

    if path.startswith("/status/"):
        return _handle_status(path.split("/status/", 1)[1], auth_context)

    return _json_response({"error": "Not found"}, 404)


def _handle_approve(token, auth_context):
    role = auth_context.get("role", "anonymous")
    if role not in ("editor", "admin"):
        return _json_response({"error": "Forbidden"}, 403)

    try:
        _serializer.loads(token, salt="approval", max_age=_expiry_seconds)
    except (SignatureExpired, BadSignature):
        return _json_response({"error": "Invalid or expired token"}, 404)

    approval = memory.get_pending_approval(token)
    if not approval:
        return _json_response({"error": "Approval not found"}, 404)
    if approval["status"] != "pending":
        return _json_response({"error": "Already resolved", "status": approval["status"]})

    memory.update_approval_status(token, "approved")

    # Trigger WordPress publish
    publish_result = None
    try:
        taxonomy = json.loads(approval.get("taxonomy_data", "{}"))
        publish_tool = WordPressPublishTool()
        publish_result = publish_tool.execute(WordPressPublishInput(
            title=approval["blog_title"],
            content=approval["blog_content"],
            excerpt=approval.get("blog_excerpt", ""),
            categories=taxonomy.get("categories", []),
            tags=taxonomy.get("tags", []),
        ))
    except Exception as e:
        return _json_response({
            "approved": True,
            "publish_error": str(e),
        })

    return _json_response({
        "approved": True,
        "post_id": publish_result.post_id if publish_result else None,
        "post_url": publish_result.post_url if publish_result else None,
        "publish_error": publish_result.error if publish_result else None,
    })


def _handle_reject_form(token, auth_context):
    role = auth_context.get("role", "anonymous")
    if role not in ("editor", "admin"):
        return _json_response({"error": "Forbidden"}, 403)

    try:
        _serializer.loads(token, salt="approval", max_age=_expiry_seconds)
    except (SignatureExpired, BadSignature):
        return _json_response({"error": "Invalid or expired token"}, 404)

    approval = memory.get_pending_approval(token)
    if not approval:
        return _json_response({"error": "Approval not found"}, 404)
    if approval["status"] != "pending":
        return _json_response({"error": "Already resolved", "status": approval["status"]})

    return _json_response({
        "token": token,
        "blog_title": approval["blog_title"],
        "status": "pending",
    })


def _handle_reject_post(token, body, auth_context):
    role = auth_context.get("role", "anonymous")
    if role not in ("editor", "admin"):
        return _json_response({"error": "Forbidden"}, 403)

    try:
        _serializer.loads(token, salt="approval", max_age=_expiry_seconds)
    except (SignatureExpired, BadSignature):
        return _json_response({"error": "Invalid or expired token"}, 404)

    approval = memory.get_pending_approval(token)
    if not approval:
        return _json_response({"error": "Approval not found"}, 404)
    if approval["status"] != "pending":
        return _json_response({"error": "Already resolved", "status": approval["status"]})

    parsed_body = json.loads(body) if body else {}
    feedback = parsed_body.get("feedback", "").strip() or None
    memory.update_approval_status(token, "rejected", feedback=feedback)

    return _json_response({"rejected": True, "feedback": feedback})


def _handle_status(token, auth_context):
    role = auth_context.get("role", "anonymous")
    if role not in ("editor", "admin"):
        return _json_response({"error": "Forbidden"}, 403)

    approval = memory.get_pending_approval(token)
    if not approval:
        return _json_response({"error": "Approval not found"}, 404)

    return _json_response({
        "token": approval["token"],
        "status": approval["status"],
        "blog_title": approval["blog_title"],
        "created_at": approval["created_at"],
        "expires_at": approval["expires_at"],
        "resolved_at": approval["resolved_at"],
    })


def _json_response(body, status_code=200):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
        "body": json.dumps(body, default=str),
    }
```

### Auth Flow: Server-Side Sessions → JWT

The current Flask app uses Auth0 server-side sessions (`session['user']`). In the serverless architecture, authentication moves entirely to the client:

| Current (Flask) | Serverless |
|---|---|
| Auth0 server-side OAuth flow (`/auth/login` → `/auth/callback`) | Auth0 SPA SDK in the dashboard JavaScript |
| Flask `session['user']` cookie | JWT access token in `Authorization: Bearer` header |
| `require_role('editor')` decorator | API Gateway Lambda authorizer validates JWT + role |
| CSRF protection via Flask-WTF | Not needed — JWT + CORS replaces CSRF |
| Rate limiting via Flask-Limiter | Cloudflare rate limiting rules |

The Auth0 Lambda authorizer (Section 5) extracts the user's email and role from the JWT. The API handler reads these from `event.requestContext.authorizer.lambda` to enforce role checks.

### API Gateway Configuration (OpenTofu)

```hcl
resource "aws_apigatewayv2_api" "main" {
  name          = "chicago-sports-recap-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = [
      "https://dashboard.chicagosportsrecap.com",
      "http://localhost:3000",  # local SPA development
    ]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Authorization", "Content-Type"]
    max_age       = 86400
  }
}

resource "aws_apigatewayv2_authorizer" "auth0" {
  api_id                            = aws_apigatewayv2_api.main.id
  authorizer_type                   = "REQUEST"
  authorizer_uri                    = aws_lambda_function.authorizer.invoke_arn
  authorizer_payload_format_version = "2.0"
  identity_sources                  = ["$request.header.Authorization"]
  name                              = "auth0-jwt"
  authorizer_result_ttl_in_seconds  = 300  # cache auth result for 5 min
}

# Public routes — no authorizer
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.api_handler.id}"
}

resource "aws_apigatewayv2_route" "dashboard_api" {
  for_each  = toset([
    "GET /dashboard/api/runs",
    "GET /dashboard/api/runs/window",
    "GET /dashboard/api/runs/range",
    "GET /dashboard/api/iterations/{run_id}",
    "GET /dashboard/api/evaluations",
    "GET /dashboard/api/health",
    "GET /dashboard/api/approvals",
    "GET /dashboard/api/teams",
    "GET /dashboard/api/sources",
    "GET /dashboard/api/llm",
    "GET /dashboard/api/cache",
    "GET /dashboard/api/drift",
  ])
  api_id    = aws_apigatewayv2_api.main.id
  route_key = each.value
  target    = "integrations/${aws_apigatewayv2_integration.api_handler.id}"
}

# Protected routes — with authorizer
resource "aws_apigatewayv2_route" "approve" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /approve/{token}"
  target             = "integrations/${aws_apigatewayv2_integration.api_handler.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.auth0.id
  authorization_type = "CUSTOM"
}

resource "aws_apigatewayv2_route" "reject_get" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /reject/{token}"
  target             = "integrations/${aws_apigatewayv2_integration.api_handler.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.auth0.id
  authorization_type = "CUSTOM"
}

resource "aws_apigatewayv2_route" "reject_post" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /reject/{token}"
  target             = "integrations/${aws_apigatewayv2_integration.api_handler.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.auth0.id
  authorization_type = "CUSTOM"
}

resource "aws_apigatewayv2_route" "status" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /status/{token}"
  target             = "integrations/${aws_apigatewayv2_integration.api_handler.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.auth0.id
  authorization_type = "CUSTOM"
}

# Custom domain
resource "aws_apigatewayv2_domain_name" "api" {
  domain_name = "api.chicagosportsrecap.com"

  domain_name_configuration {
    certificate_arn = aws_acm_certificate.api.arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}

resource "aws_apigatewayv2_api_mapping" "api" {
  api_id      = aws_apigatewayv2_api.main.id
  domain_name = aws_apigatewayv2_domain_name.api.id
  stage       = aws_apigatewayv2_stage.default.id
}
```

### Security Headers

The current Flask `@app.after_request` handler sets security headers on every response. In the serverless architecture, these are set in two places:

1. **API responses**: The `_json_response()` helper in the Lambda handler sets `X-Content-Type-Options`, `X-Frame-Options`, and CORS headers on every response
2. **SPA responses**: CloudFront response headers policy (or Cloudflare Transform Rules) sets `Content-Security-Policy`, `X-Frame-Options`, and `X-XSS-Protection` on static asset responses

### Approval Email Link Changes

The approval email currently links to `{APPROVAL_BASE_URL}/approve/{token}`. After migration:

- Links point to the SPA: `https://dashboard.chicagosportsrecap.com/approve/{token}`
- The SPA reads the token from the URL, prompts Auth0 login if needed, then calls `https://api.chicagosportsrecap.com/approve/{token}` with the JWT
- This replaces the current server-rendered HTML approval/rejection pages with SPA-rendered equivalents

The `APPROVAL_BASE_URL` secret changes from the Cloudflare Tunnel URL to `https://dashboard.chicagosportsrecap.com`.

---

## 7. SPA Dashboard

### Current Frontend Stack

The existing dashboard is server-rendered Jinja2 templates with client-side interactivity:

| Component | Current Implementation |
|---|---|
| Templating | Jinja2 (`base.html`, `dashboard.html`, `iterations.html`, 5 approval pages) |
| CSS | Tailwind CSS (built via `tools/bin/tailwindcss` CLI) |
| Interactivity | Alpine.js (nav toggle, `x-cloak`) |
| Charts | Chart.js (line, pie, doughnut) |
| JS | Vanilla (`dashboard.js`, `iterations.js`) |
| Auth | Server-side session via Auth0 OAuth flow |
| Routing | Flask routes serve each page |

The JS files already fetch all data from JSON API endpoints and render client-side. The Jinja2 templates are thin wrappers — `dashboard.html` and `iterations.html` are mostly empty shells that load JS. This makes the SPA conversion straightforward.

### Target SPA Architecture

| Component | New Implementation |
|---|---|
| Framework | Alpine.js (keep existing, add router plugin) |
| CSS | Tailwind CSS (same build pipeline) |
| Charts | Chart.js (unchanged) |
| Auth | Auth0 SPA SDK (`@auth0/auth0-spa-js`) |
| Routing | `alpinejs-router` or hash-based routing |
| API | Fetch calls to `https://api.chicagosportsrecap.com/*` with JWT |
| Hosting | S3 bucket + CloudFront (or Cloudflare proxy) |
| Build | Tailwind CLI → `output.css`, no bundler needed |

Alpine.js is already loaded via CDN. Adding the router plugin keeps the stack minimal — no build step, no bundler, no node_modules.

### Page Structure

```
frontend/
├── index.html              # SPA shell + Alpine.js router
├── css/
│   ├── input.css           # Tailwind source
│   └── output.css          # Built CSS
├── js/
│   ├── app.js              # Alpine.js init, auth, API client, router
│   ├── pages/
│   │   ├── dashboard.js    # Dashboard page component (from current dashboard.js)
│   │   ├── iterations.js   # Iterations page component (from current iterations.js)
│   │   ├── approve.js      # Approval flow page (new)
│   │   ├── reject.js       # Rejection flow page (new)
│   │   ├── drift.js        # Drift alerts page (new)
│   │   └── settings.js     # Admin settings page (new, future)
│   └── lib/
│       ├── api.js          # API client with JWT injection
│       ├── auth.js         # Auth0 SPA SDK wrapper
│       └── charts.js       # Shared Chart.js helpers
└── assets/
    └── favicon.ico
```

### SPA Shell (`index.html`)

Replaces both `base.html`, `dashboard.html`, `iterations.html`, and all approval templates with a single HTML file:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chicago Sports Recap — Dashboard</title>
    <link rel="stylesheet" href="/css/output.css">
    <style>[x-cloak] { display: none !important; }</style>
</head>
<body class="bg-gray-100 text-gray-800 font-sans" x-data="app()" x-cloak>

    <!-- Header -->
    <header class="bg-[#1a1a2e] text-white px-8 py-5 flex justify-between items-center relative">
        <div class="flex items-center">
            <button @click="navOpen = !navOpen" class="mr-3 text-2xl leading-none px-2 py-1 hover:bg-white/10 rounded cursor-pointer">☰</button>
            <h1 class="text-xl font-semibold" x-text="pageTitle">🏈 Chicago Sports Recap</h1>
        </div>
        <nav x-show="navOpen" x-cloak @click.outside="navOpen = false" x-transition
             class="absolute top-full left-0 bg-[#1a1a2e] min-w-[220px] shadow-lg z-50 rounded-br-lg">
            <a href="#/" @click="navOpen = false" class="block px-5 py-3 text-gray-400 hover:bg-white/10 hover:text-white text-sm border-b border-white/5">📊 Dashboard</a>
            <a href="#/iterations" @click="navOpen = false" class="block px-5 py-3 text-gray-400 hover:bg-white/10 hover:text-white text-sm border-b border-white/5">📝 Draft Iterations</a>
            <a href="#/drift" @click="navOpen = false" class="block px-5 py-3 text-gray-400 hover:bg-white/10 hover:text-white text-sm border-b border-white/5">⚠️ Drift Alerts</a>
            <template x-if="isAuthenticated">
                <a href="#" @click.prevent="logout(); navOpen = false" class="block px-5 py-3 text-gray-400 hover:bg-white/10 hover:text-white text-sm">🚪 Logout</a>
            </template>
            <template x-if="!isAuthenticated">
                <a href="#" @click.prevent="login(); navOpen = false" class="block px-5 py-3 text-gray-400 hover:bg-white/10 hover:text-white text-sm">🔐 Login</a>
            </template>
        </nav>
        <div class="flex items-center gap-4">
            <template x-if="isAuthenticated">
                <span class="text-sm text-gray-400" x-text="userEmail"></span>
            </template>
            <div class="text-sm text-gray-400" x-show="currentPage === 'dashboard'">Auto-refreshes every 5 minutes | <span x-text="lastUpdated"></span></div>
        </div>
    </header>

    <!-- Page Content -->
    <main>
        <div x-show="currentPage === 'dashboard'" x-html="pages.dashboard"></div>
        <div x-show="currentPage === 'iterations'" x-html="pages.iterations"></div>
        <div x-show="currentPage === 'drift'" x-html="pages.drift"></div>
        <div x-show="currentPage === 'approve'" x-html="pages.approve"></div>
        <div x-show="currentPage === 'reject'" x-html="pages.reject"></div>
    </main>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@auth0/auth0-spa-js/dist/auth0-spa-js.production.js"></script>
    <script src="/js/lib/auth.js"></script>
    <script src="/js/lib/api.js"></script>
    <script src="/js/lib/charts.js"></script>
    <script src="/js/pages/dashboard.js"></script>
    <script src="/js/pages/iterations.js"></script>
    <script src="/js/pages/drift.js"></script>
    <script src="/js/pages/approve.js"></script>
    <script src="/js/pages/reject.js"></script>
    <script src="/js/app.js"></script>
</body>
</html>
```

### Auth0 SPA SDK Integration (`js/lib/auth.js`)

Replaces the server-side Auth0 OAuth flow with client-side JWT authentication:

```javascript
let auth0Client = null;

async function initAuth() {
    auth0Client = await auth0.createAuth0Client({
        domain: 'dev-xxh01tebrt5zvws4.us.auth0.com',
        clientId: '<AUTH0_SPA_CLIENT_ID>',  // separate SPA application in Auth0
        authorizationParams: {
            redirect_uri: window.location.origin,
            audience: 'https://chicago-sports-recap/api',
        },
        cacheLocation: 'localstorage',
    });

    // Handle redirect callback
    if (window.location.search.includes('code=')) {
        await auth0Client.handleRedirectCallback();
        window.history.replaceState({}, document.title, window.location.pathname + window.location.hash);
    }
}

async function getToken() {
    if (!auth0Client) return null;
    try {
        return await auth0Client.getTokenSilently();
    } catch {
        return null;
    }
}

async function isAuthenticated() {
    return auth0Client ? await auth0Client.isAuthenticated() : false;
}

async function getUser() {
    return auth0Client ? await auth0Client.getUser() : null;
}

async function login() {
    await auth0Client.loginWithRedirect();
}

async function logout() {
    await auth0Client.logout({ logoutParams: { returnTo: window.location.origin } });
}
```

**Auth0 setup change**: Create a new Auth0 Application of type "Single Page Application" (the current one is "Regular Web Application"). Configure:
- Allowed Callback URLs: `https://dashboard.chicagosportsrecap.com`
- Allowed Logout URLs: `https://dashboard.chicagosportsrecap.com`
- Allowed Web Origins: `https://dashboard.chicagosportsrecap.com`
- Create an Auth0 API with identifier `https://chicago-sports-recap/api` (matches the `audience` in `config/auth.yaml`)

### API Client with JWT (`js/lib/api.js`)

All API calls go through this client, which injects the JWT for protected routes:

```javascript
const API_BASE = 'https://api.chicagosportsrecap.com';

async function apiFetch(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };

    // Inject JWT for protected routes
    const protectedPrefixes = ['/approve/', '/reject/', '/status/'];
    if (protectedPrefixes.some(p => path.startsWith(p))) {
        const token = await getToken();
        if (!token) {
            await login();
            return;
        }
        headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (res.status === 401) {
        await login();
        return;
    }
    return res.json();
}
```

### New Pages

#### Drift Alerts Page (`js/pages/drift.js`)

The current dashboard has a `/dashboard/api/drift` endpoint but no dedicated UI — alerts are only sent via email. The SPA adds a dedicated page:

- Table of active drift alerts with metric name, value, threshold, triggered time
- Suggested actions pulled from `config/drift.yaml` (served as a static JSON endpoint or embedded in the API response)
- Historical alert timeline (requires a new API endpoint: `GET /dashboard/api/drift/history`)

#### Approval Page (`js/pages/approve.js`)

Replaces the server-rendered `approved.html`, `already_resolved.html`, and `invalid_token.html` templates:

- Reads token from URL hash: `#/approve/{token}`
- Prompts Auth0 login if not authenticated
- Calls `GET /approve/{token}` with JWT
- Shows result: approved + WordPress publish status, already resolved, or invalid token
- Displays the blog post preview (HTML content rendered in a sandboxed iframe, same as current iterations page)

#### Rejection Page (`js/pages/reject.js`)

Replaces `reject_form.html` and `rejected.html`:

- Reads token from URL hash: `#/reject/{token}`
- `GET /reject/{token}` loads the blog title and pending status
- Shows a feedback textarea + submit button
- `POST /reject/{token}` with `{"feedback": "..."}` body
- Shows confirmation after submission

#### Settings Page (`js/pages/settings.js`) — Future

Placeholder for admin functionality that may be added later:

- WordPress OAuth re-authorization (if token is ever revoked)
- Drift threshold configuration
- Source enable/disable toggles
- Role management

This page would require `admin` role and additional API endpoints.

### Migration from Current JS

The existing `dashboard.js` and `iterations.js` are largely reusable. Key changes:

| Current Code | SPA Change |
|---|---|
| `fetch('/dashboard/api/runs')` | `apiFetch('/dashboard/api/runs')` |
| `document.getElementById('runs-table')` | Same — DOM IDs preserved |
| `Chart.js` initialization | Same — no changes |
| `formatDate()`, `formatDuration()`, `badgeHtml()` | Move to shared `charts.js` |
| `setInterval(loadAll, 5 * 60 * 1000)` | Same — auto-refresh preserved |
| Page-specific `<script>` tags in Jinja2 | Loaded in `index.html`, activated by router |

The dashboard and iterations pages require minimal rewriting — primarily replacing relative fetch URLs with `apiFetch()` calls and extracting shared utilities.

### Hash-Based Routing

The SPA uses hash routing (`#/path`) to avoid requiring S3/CloudFront URL rewriting for HTML5 history mode:

```javascript
// In app.js
function app() {
    return {
        currentPage: 'dashboard',
        navOpen: false,
        isAuthenticated: false,
        userEmail: '',
        lastUpdated: '',
        pageTitle: '🏈 Chicago Sports Recap — Dashboard',

        async init() {
            await initAuth();
            this.isAuthenticated = await isAuthenticated();
            if (this.isAuthenticated) {
                const user = await getUser();
                this.userEmail = user?.email || '';
            }
            this.route();
            window.addEventListener('hashchange', () => this.route());
        },

        route() {
            const hash = window.location.hash.slice(1) || '/';

            if (hash === '/' || hash === '') {
                this.currentPage = 'dashboard';
                this.pageTitle = '🏈 Chicago Sports Recap — Dashboard';
                this.$nextTick(() => loadDashboard());
            } else if (hash === '/iterations') {
                this.currentPage = 'iterations';
                this.pageTitle = '📝 Draft Iterations';
                this.$nextTick(() => loadIterations());
            } else if (hash === '/drift') {
                this.currentPage = 'drift';
                this.pageTitle = '⚠️ Drift Alerts';
                this.$nextTick(() => loadDriftAlerts());
            } else if (hash.startsWith('/approve/')) {
                this.currentPage = 'approve';
                this.pageTitle = '✅ Approve Blog Post';
                const token = hash.split('/approve/')[1];
                this.$nextTick(() => handleApprove(token));
            } else if (hash.startsWith('/reject/')) {
                this.currentPage = 'reject';
                this.pageTitle = '❌ Reject Blog Post';
                const token = hash.split('/reject/')[1];
                this.$nextTick(() => handleReject(token));
            }
        },
    };
}
```

### S3 + CloudFront Hosting

```hcl
resource "aws_s3_bucket" "frontend" {
  bucket = "chicago-sports-recap-dashboard"
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"  # SPA fallback — all routes serve index.html
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  aliases             = ["dashboard.chicagosportsrecap.com"]

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    cache_policy_id            = aws_cloudfront_cache_policy.spa.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
  }

  # SPA fallback: serve index.html for all 404s (hash routing handles the rest)
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.dashboard.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "csr-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name = "csr-security-headers"

  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    xss_protection {
      mode_block = true
      protection = true
      override   = true
    }
    content_security_policy {
      content_security_policy = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://*.auth0.com; style-src 'self' 'unsafe-inline'; connect-src 'self' https://api.chicagosportsrecap.com https://*.auth0.com; frame-src https://*.auth0.com"
      override                = true
    }
  }
}
```

### Build & Deploy Pipeline

The SPA build is minimal — no bundler, no transpilation:

```bash
# Build CSS (same as current)
./tools/bin/tailwindcss -i frontend/css/input.css -o frontend/css/output.css --minify

# Deploy to S3
aws s3 sync frontend/ s3://chicago-sports-recap-dashboard/ \
    --delete \
    --cache-control "public, max-age=31536000" \
    --exclude "index.html" \
    --exclude "*.js"

# index.html and JS files: short cache for quick updates
aws s3 cp frontend/index.html s3://chicago-sports-recap-dashboard/index.html \
    --cache-control "public, max-age=60"
aws s3 sync frontend/js/ s3://chicago-sports-recap-dashboard/js/ \
    --cache-control "public, max-age=300"

# Invalidate CloudFront
aws cloudfront create-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/index.html" "/js/*"
```

### Files Removed After Migration

| File/Directory | Reason |
|---|---|
| `server/templates/*.html` (12 files) | Replaced by SPA `index.html` + JS pages |
| `server/static/css/` | Moved to `frontend/css/` |
| `server/static/js/` | Refactored into `frontend/js/pages/` |
| `server/__init__.py` | Flask app no longer exists |
| `server/approval_server.py` | Replaced by API Lambda handler |
| `server/dashboard.py` | Replaced by API Lambda handler |
| `server/auth.py` | Replaced by Auth0 SPA SDK + Lambda authorizer |
| `scripts/build-css.sh` | Updated to reference `frontend/` paths |
| `scripts/watch-css.sh` | Updated to reference `frontend/` paths |
| `scripts/install-tailwind.sh` | Tailwind binary moves to CI or stays local for dev |

---

## 8. Secrets Management

### Current Setup

Secrets are managed by a pluggable provider configured in `config/database.yaml`:

```yaml
secrets:
  provider: keychain  # "env" or "keychain"
  keychain_service: "chicago-sports-recap"
```

The `utils/secrets.py` module reads from macOS Keychain (production) or environment variables (CI/Docker). There are 18 individual secrets:

| Secret | Used By | Kept in Serverless? |
|---|---|---|
| `ANTHROPIC_API_KEY` | ClaudeClient | Yes |
| `NEWSAPI_KEY` | NewsAPI collector | Yes |
| `SERPAPI_KEY` | SerpAPI collector | Yes |
| `EMAIL_FROM` | Approval/failure/drift emails | Yes (SES sender address) |
| `EMAIL_PASSWORD` | SMTP auth | **No** — SES uses IAM role |
| `EMAIL_TO` | Approval email recipient | Yes |
| `ERROR_EMAIL_TO` | Failure/drift email recipient | Yes |
| `EMAIL_SMTP_SERVER` | SMTP connection | **No** — replaced by SES |
| `EMAIL_SMTP_PORT` | SMTP connection | **No** — replaced by SES |
| `APPROVAL_SECRET_KEY` | Token signing (itsdangerous) | Yes |
| `APPROVAL_BASE_URL` | Email approve/reject links | Yes (changes to SPA URL) |
| `WORDPRESS_CLIENT_ID` | OAuth flow | **No** — OAuth flow removed |
| `WORDPRESS_CLIENT_SECRET` | OAuth flow | **No** — OAuth flow removed |
| `WORDPRESS_URL` | WordPress API base URL | Yes |
| `WORDPRESS_ACCESS_TOKEN` | WordPress API auth | **New** — long-lived token moved from DB to Secrets Manager |
| `LANGFUSE_PUBLIC_KEY` | Langfuse SDK | Yes (new Langfuse Cloud key) |
| `LANGFUSE_SECRET_KEY` | Langfuse SDK | Yes (new Langfuse Cloud key) |
| `AUTH0_CLIENT_ID` | Auth0 OAuth | **No** — SPA client ID is public, embedded in frontend JS |
| `AUTH0_CLIENT_SECRET` | Auth0 OAuth | **No** — SPA flow uses PKCE, no client secret |
| `DATABASE_URL` | Aurora connection string | **New** (Aurora path only) |

### Target: Single JSON Blob in Secrets Manager

7 secrets removed (SMTP, WordPress OAuth, Auth0 server-side), 1–2 added (WordPress token, optionally DATABASE_URL). The remaining secrets are stored as a single JSON object:

```json
{
  "ANTHROPIC_API_KEY": "sk-ant-...",
  "NEWSAPI_KEY": "...",
  "SERPAPI_KEY": "...",
  "EMAIL_FROM": "contact.chicagosportsrecap@gmail.com",
  "EMAIL_TO": "<email>",
  "ERROR_EMAIL_TO": "<email>",
  "APPROVAL_SECRET_KEY": "...",
  "APPROVAL_BASE_URL": "https://dashboard.chicagosportsrecap.com",
  "WORDPRESS_URL": "chicagosportsrecap.wordpress.com",
  "WORDPRESS_ACCESS_TOKEN": "...",
  "LANGFUSE_PUBLIC_KEY": "pk-lf-...",
  "LANGFUSE_SECRET_KEY": "sk-lf-...",
  "DATABASE_URL": "postgresql://user:pass@aurora-host:5432/chicagosportsrecap"
}
```

DynamoDB path: omit `DATABASE_URL` (Lambdas use the table names from config or environment variables, auth is via IAM role).

**Cost**: 1 secret × $0.40/mo + ~30 API calls/day × $0.05/10K = **~$0.40/mo**

### Updated `utils/secrets.py`

Replace the current keychain/env provider with a Secrets Manager client that caches at cold start:

```python
"""Secrets provider for AWS Secrets Manager."""

import json
import boto3

_cache: dict[str, str] | None = None
_SECRET_ID = "chicago-sports-recap/config"


def _load_secrets() -> dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=_SECRET_ID)
    _cache = json.loads(response["SecretString"])
    return _cache


def get_secret(key: str) -> str | None:
    """Get a secret value by key.

    Args:
        key: Secret key name.

    Returns:
        Secret value, or None if not found.
    """
    secrets = _load_secrets()
    return secrets.get(key)
```

This is a drop-in replacement — every file that calls `get_secret('ANTHROPIC_API_KEY')` continues to work unchanged. The `_cache` global ensures Secrets Manager is called only once per Lambda cold start.

### WordPress Token Migration

The WordPress OAuth token is currently stored encrypted in the `oauth_tokens` SQLite table. Since the token is long-lived and the OAuth flow is being removed:

1. Decrypt the current token: `python -c "from memory.memory import Memory; print(Memory().get_oauth_token('wordpress'))"`
2. Add it to the Secrets Manager JSON blob as `WORDPRESS_ACCESS_TOKEN`
3. Update `wordpress_publish_tool.py` to read from secrets instead of the database:

```python
# Before
def _get_headers(self) -> dict[str, str]:
    token = self.memory.get_oauth_token('wordpress')
    if not token:
        raise RuntimeError('No WordPress OAuth token found...')
    return {'Authorization': f'Bearer {token}'}

# After
def _get_headers(self) -> dict[str, str]:
    token = get_secret('WORDPRESS_ACCESS_TOKEN')
    if not token:
        raise RuntimeError('No WordPress OAuth token found in Secrets Manager.')
    return {'Authorization': f'Bearer {token}'}
```

4. Remove `memory/oauth.py` mixin and `OAuthToken` model from `database.py`
5. Remove `OAuthTokens` DynamoDB table (if using DynamoDB path) or drop the `oauth_tokens` SQL table (Aurora path)

### OpenTofu Configuration

```hcl
resource "aws_secretsmanager_secret" "config" {
  name                    = "chicago-sports-recap/config"
  description             = "Application secrets for Chicago Sports Recap"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "config" {
  secret_id     = aws_secretsmanager_secret.config.id
  secret_string = jsonencode(var.app_secrets)
}

# IAM policy for Lambda access
data "aws_iam_policy_document" "secrets_read" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.config.arn]
  }
}

resource "aws_iam_policy" "secrets_read" {
  name   = "csr-secrets-read"
  policy = data.aws_iam_policy_document.secrets_read.json
}
```

The `var.app_secrets` variable is populated from a `.tfvars` file that is **not** committed to git. In the GitHub Actions pipeline, secret values are injected from GitHub Secrets:

```hcl
# variables.tf
variable "app_secrets" {
  type      = map(string)
  sensitive = true
}
```

### Secret Rotation

Secrets Manager supports automatic rotation, but for this application:

- `ANTHROPIC_API_KEY`, `NEWSAPI_KEY`, `SERPAPI_KEY` — rotated manually when providers issue new keys
- `APPROVAL_SECRET_KEY` — **do not rotate** without re-signing all pending approval tokens (or let them expire first)
- `WORDPRESS_ACCESS_TOKEN` — long-lived, rotate only if revoked (re-authorize manually at wordpress.com and update the secret)
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` — rotated via Langfuse Cloud dashboard
- `DATABASE_URL` — rotate by updating Aurora master password via RDS + updating the secret

Automatic rotation is not worth the complexity for this workload. Manual rotation via `aws secretsmanager update-secret` or the OpenTofu pipeline is sufficient.

### Files Removed After Migration

| File | Reason |
|---|---|
| `scripts/migrate_secrets.py` | macOS Keychain migration script no longer needed |
| `memory/oauth.py` | WordPress token moved to Secrets Manager |
| `utils/encryption.py` | Token encryption/decryption no longer needed (Secrets Manager encrypts at rest) |
| `memory/database.py` → `OAuthToken` model | Table removed |
| `config/database.yaml` → `secrets` section | Provider config no longer needed |

---

## 9. Langfuse Migration

### Current Setup

Langfuse runs self-hosted via Docker Compose with 5 containers:

| Container | Image | Purpose | Port |
|---|---|---|---|
| `langfuse-web` | `langfuse/langfuse:3` | Web UI + API | 3000 |
| `langfuse-worker` | `langfuse/langfuse-worker:3` | Background processing | 3030 |
| `postgres` | `postgres:17` | Langfuse metadata store | 5432 |
| `redis` | `redis:7` | Queue + caching | 6379 |
| `clickhouse` | `clickhouse/clickhouse-server` | Analytics/trace storage | 8123, 9000 |
| `minio` | `chainguard/minio` | S3-compatible object storage | 9000, 9001 |

This stack consumes significant local resources and is the primary reason for the Docker Compose setup. The application integrates with Langfuse via two touchpoints:

1. **`@observe()` decorator** on `run_daily_workflow()` and `_execute_workflow()` in `workflow/daily_workflow.py`
2. **`@observe(as_type='generation')` decorator** on `send_messages_with_tools()` and `send_message()` in `agent/claude_client.py`

The Langfuse SDK reads connection config from environment variables.

### Target: Langfuse Cloud Free Tier

| Feature | Free Tier Limit | Current Usage |
|---|---|---|
| Observations/month | 50,000 | ~180/day × 30 = ~5,400/mo |
| Traces | Unlimited | ~1/day |
| Retention | 30 days | Matches current `database.retention_days` |
| Team members | 2 | Sufficient |
| Projects | 2 | 1 needed |

Current usage is ~11% of the free tier limit. Even with growth (more teams, more articles, revision loop expansion), there is significant headroom before hitting the 50K observation cap.

### Migration Steps

#### 1. Create Langfuse Cloud Account

1. Sign up at [cloud.langfuse.com](https://cloud.langfuse.com)
2. Create a project named `chicago-sports-recap`
3. Copy the new public key and secret key from project settings

#### 2. Update Secrets

Replace the self-hosted keys with Langfuse Cloud keys in the Secrets Manager JSON blob:

```json
{
  "LANGFUSE_PUBLIC_KEY": "pk-lf-<new-cloud-key>",
  "LANGFUSE_SECRET_KEY": "sk-lf-<new-cloud-key>"
}
```

#### 3. Set Langfuse Host

The Langfuse SDK defaults to `https://cloud.langfuse.com` when `LANGFUSE_HOST` is not set. The current self-hosted setup likely sets `LANGFUSE_HOST=http://localhost:3000` in the environment.

In the Lambda environment, either:
- **Do nothing** — the SDK defaults to Langfuse Cloud when no host is set
- **Explicitly set** `LANGFUSE_HOST=https://cloud.langfuse.com` as a Lambda environment variable for clarity

The Langfuse SDK initializes automatically from environment variables (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`). These can be set as Lambda environment variables sourced from Secrets Manager at deploy time, or the SDK can read them via the updated `get_secret()` function if Langfuse supports programmatic init.

Since the `@observe()` decorator uses automatic SDK initialization, the simplest approach is Lambda environment variables:

```hcl
# In each Lambda's environment block
environment {
  variables = {
    LANGFUSE_PUBLIC_KEY = data.aws_secretsmanager_secret_version.config.secret_string["LANGFUSE_PUBLIC_KEY"]
    LANGFUSE_SECRET_KEY = data.aws_secretsmanager_secret_version.config.secret_string["LANGFUSE_SECRET_KEY"]
    LANGFUSE_HOST       = "https://cloud.langfuse.com"
  }
}
```

Note: Only the workflow Lambdas that use `@observe()` need these variables — specifically `csr-workflow-draft-evaluate` (runs RevisionAgent → ClaudeClient) and `csr-workflow-summarize` (runs SummarizeArticleTool → ClaudeClient). The API handler and scheduled Lambdas do not make LLM calls and don't need Langfuse config.

#### 4. Verify Traces

After the first workflow run on AWS:

1. Open [cloud.langfuse.com](https://cloud.langfuse.com) → project → Traces
2. Confirm a trace appears for the daily workflow with nested generations for each LLM call
3. Verify token counts and latency metrics are populated

#### 5. Migrate Historical Data (Optional)

Langfuse Cloud does not support importing traces from a self-hosted instance. Historical trace data in the local Postgres/ClickHouse volumes will be lost when Docker Compose is shut down.

Options:
- **Accept the loss** — the application's own database (Aurora/DynamoDB) already stores workflow metrics, evaluation scores, and draft iterations. Langfuse traces are supplementary debugging data.
- **Export before shutdown** — use the Langfuse API to export traces as JSON for archival: `GET /api/public/traces?limit=100` from `http://localhost:3000`. Store the export in S3.
- **Keep Docker running temporarily** — run the self-hosted stack in parallel for 30 days (matching retention) while new traces flow to Langfuse Cloud. Shut down after the retention window passes.

### Code Changes

**No application code changes required.** The `@observe()` decorators and Langfuse SDK calls in `claude_client.py` and `daily_workflow.py` work identically with Langfuse Cloud — only the connection target changes via environment variables.

### Infrastructure Removed

| File/Resource | Reason |
|---|---|
| `docker-compose.yaml` | Entire Langfuse stack (6 services, 5 volumes) |
| `services/com.chicagosportsrecap.docker.plist` | launchd service for Docker Compose |
| `logs/docker_stdout.log`, `logs/docker_stderr.log` | Docker service logs |
| Local Docker volumes (`langfuse_postgres_data`, `langfuse_clickhouse_data`, `langfuse_clickhouse_logs`, `langfuse_minio_data`, `langfuse_redis_data`) | Persistent data for self-hosted Langfuse |

### Cost Impact

| Component | Before (Self-Hosted) | After (Cloud Free Tier) |
|---|---|---|
| Compute | Docker containers on macOS (CPU/RAM) | $0 |
| Storage | ~500 MB in Docker volumes | $0 |
| Maintenance | Docker Compose updates, Postgres backups | $0 |
| **Total** | Local resource cost + operational overhead | **$0** |

If usage eventually exceeds the free tier (50K observations/mo), Langfuse Cloud's paid tier starts at $59/mo. At that point, evaluate whether the self-hosted option on ECS (~$70/mo from the original estimate) is more cost-effective.

---

## 10. Data Migration Runbook

### 10.1 Pre-Migration Inventory

Current SQLite database: `data/articles.db` (~2.5 MB)

| Table | Estimated Rows | Size | Retention |
|---|---|---|---|
| `articles` | ~1,500 | ~400 KB | 30 days |
| `article_summaries` | ~300 | ~200 KB | 30 days |
| `workflow_runs` | ~30 | ~500 KB (checkpoint_data is large) | 30 days |
| `api_call_results` | ~90 | ~20 KB | Linked to workflow_runs |
| `summary_stats` | ~180 | ~15 KB | Linked to workflow_runs |
| `summaries` (blog drafts) | ~15 | ~800 KB (html_content) | 30 days |
| `evaluations` | ~60 | ~50 KB | Linked to summaries |
| `improvement_suggestions` | ~30 | ~10 KB | Linked to summaries |
| `categories` | ~10 | ~1 KB | Permanent |
| `tags` | ~50 | ~3 KB | Permanent |
| `summary_categories` | ~30 | ~1 KB | Linked to summaries |
| `summary_tags` | ~60 | ~2 KB | Linked to summaries |
| `pending_approvals` | ~15 | ~400 KB (blog_content) | 30 days |
| `drift_alerts` | ~5 | ~1 KB | Permanent |
| `oauth_tokens` | 1 | ~1 KB | **Not migrated** (moved to Secrets Manager) |

---

### 10.2 Option A: SQLite → Aurora Serverless v2

#### Step 1: Export from SQLite

```bash
# Dump SQLite to SQL (on local machine)
sqlite3 data/articles.db .dump > data/sqlite_dump.sql
```

#### Step 2: Transform to PostgreSQL-compatible SQL

SQLite and PostgreSQL have syntax differences. Create a transform script:

```bash
#!/bin/bash
# scripts/transform_sqlite_to_pg.sh

cp data/sqlite_dump.sql data/pg_import.sql

# Remove SQLite-specific statements
sed -i '' '/^BEGIN TRANSACTION/d' data/pg_import.sql
sed -i '' '/^COMMIT/d' data/pg_import.sql
sed -i '' '/^PRAGMA/d' data/pg_import.sql
sed -i '' '/^CREATE INDEX/d' data/pg_import.sql  # SQLAlchemy will recreate

# Fix data types
sed -i '' 's/INTEGER PRIMARY KEY/SERIAL PRIMARY KEY/g' data/pg_import.sql
sed -i '' 's/AUTOINCREMENT//g' data/pg_import.sql

# Fix boolean values
sed -i '' "s/,1,/,true,/g" data/pg_import.sql
sed -i '' "s/,0,/,false,/g" data/pg_import.sql

# Remove oauth_tokens table (moved to Secrets Manager)
sed -i '' '/INSERT INTO "oauth_tokens"/d' data/pg_import.sql
```

#### Step 3: Create Aurora Schema

Let SQLAlchemy create the schema (ensures indexes and constraints match the ORM):

```bash
# Run from a machine with VPC access (or via bastion/SSM)
python -c "
from memory.database import Base, get_engine
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:<password>@<aurora-endpoint>:5432/chicagosportsrecap'
engine = get_engine()
Base.metadata.create_all(engine)
print('Schema created.')
"
```

#### Step 4: Load Data

```bash
# Connect to Aurora and load data (INSERT statements only)
grep '^INSERT' data/pg_import.sql > data/pg_inserts.sql

psql "postgresql://postgres:<password>@<aurora-endpoint>:5432/chicagosportsrecap" \
    -f data/pg_inserts.sql
```

#### Step 5: Validate

```bash
# Compare row counts
sqlite3 data/articles.db "SELECT 'articles', COUNT(*) FROM articles UNION ALL SELECT 'workflow_runs', COUNT(*) FROM workflow_runs UNION ALL SELECT 'summaries', COUNT(*) FROM summaries UNION ALL SELECT 'pending_approvals', COUNT(*) FROM pending_approvals;"

psql "postgresql://postgres:<password>@<aurora-endpoint>:5432/chicagosportsrecap" \
    -c "SELECT 'articles', COUNT(*) FROM articles UNION ALL SELECT 'workflow_runs', COUNT(*) FROM workflow_runs UNION ALL SELECT 'summaries', COUNT(*) FROM summaries UNION ALL SELECT 'pending_approvals', COUNT(*) FROM pending_approvals;"
```

Row counts must match (minus `oauth_tokens` which is intentionally excluded).

#### Step 6: Drop Unnecessary Columns

After confirming Step Functions handles checkpointing:

```sql
ALTER TABLE workflow_runs DROP COLUMN checkpoint_data;
```

---

### 10.3 Option B: SQLite → DynamoDB (Multi-Table)

#### Step 1: Export SQLite to JSON

```python
"""scripts/export_sqlite_to_json.py"""

import json
from memory.database import (
    Article, ArticleSummary, WorkflowRun, ApiCallResult, SummaryStats,
    Summary, Evaluation, ImprovementSuggestion, Category, Tag,
    SummaryCategory, SummaryTag, PendingApproval, DriftAlert,
    get_engine, get_session,
)

engine = get_engine('data/articles.db')
session = get_session(engine)

def serialize(obj):
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, 'isoformat'):
            d[k] = v.isoformat()
    return d

export = {
    'articles': [serialize(r) for r in session.query(Article).all()],
    'article_summaries': [serialize(r) for r in session.query(ArticleSummary).all()],
    'workflow_runs': [serialize(r) for r in session.query(WorkflowRun).all()],
    'api_call_results': [serialize(r) for r in session.query(ApiCallResult).all()],
    'summary_stats': [serialize(r) for r in session.query(SummaryStats).all()],
    'summaries': [serialize(r) for r in session.query(Summary).all()],
    'evaluations': [serialize(r) for r in session.query(Evaluation).all()],
    'improvement_suggestions': [serialize(r) for r in session.query(ImprovementSuggestion).all()],
    'categories': [serialize(r) for r in session.query(Category).all()],
    'tags': [serialize(r) for r in session.query(Tag).all()],
    'summary_categories': [serialize(r) for r in session.query(SummaryCategory).all()],
    'summary_tags': [serialize(r) for r in session.query(SummaryTag).all()],
    'pending_approvals': [serialize(r) for r in session.query(PendingApproval).all()],
    'drift_alerts': [serialize(r) for r in session.query(DriftAlert).all()],
}

session.close()

with open('data/export.json', 'w') as f:
    json.dump(export, f, indent=2)

for table, rows in export.items():
    print(f'{table}: {len(rows)} rows')
```

#### Step 2: Transform and Load to DynamoDB

```python
"""scripts/load_dynamodb.py"""

import json
import time
from datetime import datetime, timedelta
import boto3

with open('data/export.json', 'r') as f:
    data = json.load(f)

dynamodb = boto3.resource('dynamodb')

RETENTION_DAYS = 30

def ttl_epoch(iso_date: str | None, days: int = RETENTION_DAYS) -> int | None:
    if not iso_date:
        return None
    dt = datetime.fromisoformat(iso_date)
    return int((dt + timedelta(days=days)).timestamp())


# --- Table 1: Articles ---
table = dynamodb.Table('chicago-sports-recap-articles')
with table.batch_writer() as batch:
    for row in data['articles']:
        batch.put_item(Item={
            'url': row['url'],
            'entity_type': 'ARTICLE',
            'title': row['title'],
            'content': row.get('content') or '',
            'source': row.get('source') or '',
            'team': row.get('team') or '',
            'published_at': row.get('published_at') or '',
            'fetched_at': row.get('fetched_at') or '',
            'ttl': ttl_epoch(row.get('fetched_at')),
        })
    for row in data['article_summaries']:
        batch.put_item(Item={
            'url': row['url'],
            'entity_type': 'SUMMARY',
            'team': row.get('team') or '',
            'summary': row['summary'],
            'event_type': row.get('event_type') or '',
            'players_mentioned': row.get('players_mentioned') or '[]',
            'is_relevant': row.get('is_relevant', True),
            'created_at': row.get('created_at') or '',
            'ttl': ttl_epoch(row.get('created_at')),
        })
print(f"Articles table: {len(data['articles'])} articles + {len(data['article_summaries'])} summaries")


# --- Table 2: WorkflowRuns ---
# Build lookup: workflow_run.id -> run_id
run_id_map = {row['id']: row['run_id'] for row in data['workflow_runs']}

table = dynamodb.Table('chicago-sports-recap-workflow-runs')
with table.batch_writer() as batch:
    for row in data['workflow_runs']:
        item = {
            'run_id': row['run_id'],
            'sk': 'RUN',
            'started_at': row.get('started_at') or '',
            'completed_at': row.get('completed_at') or '',
            'status': row.get('status') or 'unknown',
        }
        # Add all optional fields if present
        for field in ['skip_reason', 'error', 'steps_completed', 'scores_fetched',
                      'articles_fetched', 'articles_new', 'summaries_count',
                      'overall_score', 'email_sent', 'total_input_tokens',
                      'total_output_tokens', 'estimated_cost', 'usage_by_tool',
                      'revision_tool_calls', 'draft_attempts', 'score_progression',
                      'publish_post_id', 'publish_post_url', 'publish_success',
                      'draft_iterations']:
            if row.get(field) is not None:
                item[field] = row[field]
        batch.put_item(Item=item)

    for row in data['api_call_results']:
        run_id = run_id_map.get(row['workflow_run_id'])
        if not run_id:
            continue
        batch.put_item(Item={
            'run_id': run_id,
            'sk': f"API#{row['source_name']}",
            'source_name': row['source_name'],
            'status': row['status'],
            'article_count': row.get('article_count') or 0,
            'error_message': row.get('error_message') or '',
            'created_at': row.get('created_at') or '',
        })

    for row in data['summary_stats']:
        run_id = run_id_map.get(row['workflow_run_id'])
        if not run_id:
            continue
        batch.put_item(Item={
            'run_id': run_id,
            'sk': f"STATS#{row['team']}",
            'team': row['team'],
            'articles_fetched': row.get('articles_fetched', 0),
            'articles_summarized': row.get('articles_summarized', 0),
            'cache_hits': row.get('cache_hits', 0),
            'cache_misses': row.get('cache_misses', 0),
        })
print(f"WorkflowRuns table: {len(data['workflow_runs'])} runs + {len(data['api_call_results'])} api results + {len(data['summary_stats'])} stats")


# --- Table 3: BlogDrafts ---
# Build lookups
summary_id_map = {row['id']: str(row['id']) for row in data['summaries']}
category_name_map = {row['id']: row['name'] for row in data['categories']}
tag_name_map = {row['id']: row['name'] for row in data['tags']}

table = dynamodb.Table('chicago-sports-recap-blog-drafts')
with table.batch_writer() as batch:
    for row in data['summaries']:
        batch.put_item(Item={
            'summary_id': str(row['id']),
            'sk': 'DRAFT',
            'created_at': row.get('created_at') or '',
            'title': row.get('title') or '',
            'html_content': row.get('html_content') or '',
            'excerpt': row.get('summary') or '',
            'teams_covered': row.get('teams_covered') or '[]',
            'article_count': row.get('article_count') or 0,
            'overall_score': row.get('overall_score') or 0,
        })

    for row in data['evaluations']:
        sid = str(row['summary_id'])
        batch.put_item(Item={
            'summary_id': sid,
            'sk': f"EVAL#{row['evaluation_id']}#{row['criterion']}",
            'evaluation_id': row['evaluation_id'],
            'criterion': row['criterion'],
            'score': row['score'],
            'reasoning': row.get('reasoning') or '',
        })

    for i, row in enumerate(data['improvement_suggestions']):
        sid = str(row['summary_id'])
        batch.put_item(Item={
            'summary_id': sid,
            'sk': f"SUGGESTION#{i}",
            'suggestion': row['suggestion'],
        })

    for row in data['summary_categories']:
        sid = str(row['summary_id'])
        cat_name = category_name_map.get(row['category_id'], 'Unknown')
        cat = next((c for c in data['categories'] if c['id'] == row['category_id']), {})
        batch.put_item(Item={
            'summary_id': sid,
            'sk': f"CAT#{cat_name}",
            'category_name': cat_name,
            'wordpress_id': cat.get('wordpress_id') or 0,
        })

    for row in data['summary_tags']:
        sid = str(row['summary_id'])
        tag_name = tag_name_map.get(row['tag_id'], 'Unknown')
        tag = next((t for t in data['tags'] if t['id'] == row['tag_id']), {})
        batch.put_item(Item={
            'summary_id': sid,
            'sk': f"TAG#{tag_name}",
            'tag_name': tag_name,
            'wordpress_id': tag.get('wordpress_id') or 0,
        })
print(f"BlogDrafts table: {len(data['summaries'])} drafts + {len(data['evaluations'])} evals + {len(data['summary_categories'])} cats + {len(data['summary_tags'])} tags")


# --- Table 4: Approvals ---
table = dynamodb.Table('chicago-sports-recap-approvals')
with table.batch_writer() as batch:
    for row in data['pending_approvals']:
        batch.put_item(Item={
            'token': row['token'],
            'status': row['status'],
            'created_at': row.get('created_at') or '',
            'expires_at': row.get('expires_at') or '',
            'resolved_at': row.get('resolved_at') or '',
            'blog_title': row['blog_title'],
            'blog_content': row['blog_content'],
            'blog_excerpt': row.get('blog_excerpt') or '',
            'taxonomy_data': row.get('taxonomy_data') or '{}',
            'evaluation_data': row.get('evaluation_data') or '{}',
            'summaries_data': row.get('summaries_data') or '[]',
            'scores_data': row.get('scores_data') or '[]',
            'feedback': row.get('feedback') or '',
            'ttl': ttl_epoch(row.get('created_at')),
        })
print(f"Approvals table: {len(data['pending_approvals'])} approvals")


# --- Table 5: Taxonomy ---
table = dynamodb.Table('chicago-sports-recap-taxonomy')
with table.batch_writer() as batch:
    for row in data['categories']:
        batch.put_item(Item={
            'pk': f"CATEGORY#{row['name']}",
            'name': row['name'],
            'entity_type': 'category',
            'description': row.get('description') or '',
            'wordpress_id': row.get('wordpress_id') or 0,
        })
    for row in data['tags']:
        batch.put_item(Item={
            'pk': f"TAG#{row['name']}",
            'name': row['name'],
            'entity_type': 'tag',
            'description': row.get('description') or '',
            'wordpress_id': row.get('wordpress_id') or 0,
        })
print(f"Taxonomy table: {len(data['categories'])} categories + {len(data['tags'])} tags")


# --- Table 6: DriftAlerts ---
table = dynamodb.Table('chicago-sports-recap-drift-alerts')
with table.batch_writer() as batch:
    for row in data['drift_alerts']:
        batch.put_item(Item={
            'metric_name': row['metric_name'],
            'triggered_at': row.get('triggered_at') or '',
            'status': row.get('status') or 'active',
            'resolved_at': row.get('resolved_at') or '',
            'metric_value': row.get('metric_value') or 0,
            'threshold': row.get('threshold') or 0,
            'run_id': row.get('run_id') or '',
        })
print(f"DriftAlerts table: {len(data['drift_alerts'])} alerts")

print("\nMigration complete.")
```

#### Step 3: Validate

```python
"""scripts/validate_dynamodb.py"""

import json
import boto3

with open('data/export.json', 'r') as f:
    data = json.load(f)

dynamodb = boto3.resource('dynamodb')

expected = {
    'chicago-sports-recap-articles': len(data['articles']) + len(data['article_summaries']),
    'chicago-sports-recap-workflow-runs': len(data['workflow_runs']) + len(data['api_call_results']) + len(data['summary_stats']),
    'chicago-sports-recap-blog-drafts': len(data['summaries']) + len(data['evaluations']) + len(data['improvement_suggestions']) + len(data['summary_categories']) + len(data['summary_tags']),
    'chicago-sports-recap-approvals': len(data['pending_approvals']),
    'chicago-sports-recap-taxonomy': len(data['categories']) + len(data['tags']),
    'chicago-sports-recap-drift-alerts': len(data['drift_alerts']),
}

for table_name, expected_count in expected.items():
    table = dynamodb.Table(table_name)
    actual = table.item_count  # Note: may be delayed up to 6 hours
    # For immediate accuracy, use scan with Select='COUNT'
    response = table.scan(Select='COUNT')
    actual = response['Count']
    status = '✅' if actual == expected_count else '❌'
    print(f'{status} {table_name}: expected={expected_count}, actual={actual}')
```

---

### 10.4 Rollback Plan

| Phase | Rollback Action |
|---|---|
| Before DNS cutover | Local system is still running — no action needed |
| After DNS cutover, data issue found | Point Cloudflare DNS back to local (Cloudflare Tunnel or direct IP). Local SQLite is still intact. |
| Aurora data corruption | Restore from RDS automated snapshot (point-in-time recovery, up to 5 minutes granularity) |
| DynamoDB data corruption | Restore from PITR (point-in-time recovery, enabled in OpenTofu config) |
| Complete migration failure | Keep local system running in parallel for 7 days post-cutover. Only decommission after confirming 7 consecutive successful workflow runs on AWS. |

### 10.5 Migration Timing

Run the data migration **after** the daily workflow completes (after 6:15 AM CT) and **before** the next day's run. This ensures:

- No writes are in progress during export
- The migrated data includes the most recent workflow run
- The first AWS workflow run the next morning starts with a complete dataset

Recommended sequence:

1. 6:15 AM CT — local workflow completes
2. 6:30 AM CT — run export script
3. 6:35 AM CT — run load script (Aurora or DynamoDB)
4. 6:40 AM CT — run validation script
5. 6:45 AM CT — switch DNS to AWS
6. Next day 6:00 AM CT — first workflow run on AWS (EventBridge triggers Step Functions)

---

## 11. OpenTofu Module Structure

### Directory Layout

```
infra/
├── modules/
│   ├── api-gateway/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── aurora/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── dynamodb/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── cloudfront/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── lambdas/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── iam.tf
│   ├── step-functions/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── secrets/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── s3/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── eventbridge/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── ses/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── vpc/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── environments/
│   ├── prod/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── terraform.tfvars      # non-sensitive defaults
│   │   └── backend.tf
│   └── staging/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── terraform.tfvars
│       └── backend.tf
└── shared/
    ├── providers.tf
    └── versions.tf
```

### Module Responsibilities

| Module | Resources Created | Depends On |
|---|---|---|
| `vpc` | VPC, subnets, security groups, VPC endpoints (Aurora path only) | — |
| `secrets` | Secrets Manager secret + version, IAM read policy | — |
| `s3` | Frontend bucket, Lambda artifact bucket, Tofu state bucket | — |
| `aurora` | RDS cluster, instance, subnet group, security group rule | `vpc`, `secrets` |
| `dynamodb` | 7 tables with GSIs, PITR, TTL config | — |
| `lambdas` | 11 Lambda functions, shared layer, IAM roles/policies | `secrets`, `aurora` or `dynamodb`, `vpc` (Aurora path) |
| `step-functions` | State machine definition, IAM execution role | `lambdas` |
| `eventbridge` | Scheduler rule (daily workflow), interval rule (expired approvals) | `step-functions`, `lambdas` |
| `api-gateway` | HTTP API, routes, integrations, authorizer, custom domain, stage | `lambdas` |
| `cloudfront` | Distribution, OAC, cache policy, response headers policy | `s3` |
| `ses` | Email identity verification, sending authorization | — |

### Environment Composition (`environments/prod/main.tf`)

```hcl
terraform {
  required_version = ">= 1.6.0"
}

module "secrets" {
  source      = "../../modules/secrets"
  app_secrets = var.app_secrets
}

module "s3" {
  source      = "../../modules/s3"
  environment = "prod"
}

# --- Choose ONE database module ---

# Option A: Aurora
module "vpc" {
  source      = "../../modules/vpc"
  environment = "prod"
}

module "aurora" {
  source            = "../../modules/aurora"
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnet_ids
  security_group_id = module.vpc.lambda_security_group_id
  db_password       = var.app_secrets["DATABASE_URL"]  # extract password
}

# Option B: DynamoDB
# module "dynamodb" {
#   source      = "../../modules/dynamodb"
#   environment = "prod"
# }

module "lambdas" {
  source             = "../../modules/lambdas"
  secrets_arn        = module.secrets.secret_arn
  secrets_policy_arn = module.secrets.read_policy_arn
  artifact_bucket    = module.s3.artifact_bucket_name
  environment        = "prod"

  # Aurora path
  vpc_subnet_ids         = module.vpc.private_subnet_ids
  vpc_security_group_ids = [module.vpc.lambda_security_group_id]

  # DynamoDB path (uncomment if using DynamoDB)
  # dynamodb_table_arns = module.dynamodb.table_arns
}

module "step_functions" {
  source      = "../../modules/step-functions"
  lambda_arns = module.lambdas.workflow_lambda_arns
}

module "eventbridge" {
  source                   = "../../modules/eventbridge"
  state_machine_arn        = module.step_functions.state_machine_arn
  expired_approvals_lambda = module.lambdas.check_expired_arn
}

module "api_gateway" {
  source          = "../../modules/api-gateway"
  handler_arn     = module.lambdas.api_handler_arn
  authorizer_arn  = module.lambdas.api_authorizer_arn
  certificate_arn = var.api_certificate_arn
  domain_name     = "api.chicagosportsrecap.com"
}

module "cloudfront" {
  source          = "../../modules/cloudfront"
  bucket_domain   = module.s3.frontend_bucket_domain
  bucket_id       = module.s3.frontend_bucket_id
  certificate_arn = var.dashboard_certificate_arn
  domain_name     = "dashboard.chicagosportsrecap.com"
}

module "ses" {
  source       = "../../modules/ses"
  sender_email = "contact.chicagosportsrecap@gmail.com"
}
```

### State Management (`environments/prod/backend.tf`)

```hcl
terraform {
  backend "s3" {
    bucket         = "chicago-sports-recap-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "chicago-sports-recap-tflock"
    encrypt        = true
  }
}
```

The state bucket and lock table are created manually (or via a bootstrap script) before the first `tofu apply`:

```bash
aws s3 mb s3://chicago-sports-recap-tfstate --region us-east-2
aws dynamodb create-table \
    --table-name chicago-sports-recap-tflock \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-2
```

### Database Module Toggle

The environment config uses one of two database modules. To switch between Aurora and DynamoDB:

1. Comment/uncomment the relevant module block in `environments/prod/main.tf`
2. Update the `lambdas` module inputs (VPC config for Aurora, table ARNs for DynamoDB)
3. Run `tofu plan` to verify the change

Both modules can coexist in the `modules/` directory — only the one referenced in the environment is instantiated.

---

## 12. GitHub Actions Pipeline

### Workflow Files

```
.github/workflows/
├── tofu-plan.yml       # Runs on PR — shows plan diff
├── tofu-apply.yml      # Runs on merge to main — applies infrastructure
├── deploy-lambdas.yml  # Runs on changes to lambdas/ or shared code
├── deploy-spa.yml      # Runs on changes to frontend/
└── tests.yml           # Existing — runs on PR (unchanged)
```

### Infrastructure Plan (`tofu-plan.yml`)

```yaml
name: OpenTofu Plan

on:
  pull_request:
    paths:
      - 'infra/**'

jobs:
  plan:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - uses: opentofu/setup-opentofu@v1
        with:
          tofu_version: '1.7.0'

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-2

      - name: Tofu Init
        working-directory: infra/environments/prod
        run: tofu init

      - name: Tofu Plan
        working-directory: infra/environments/prod
        run: tofu plan -no-color -out=plan.tfplan
        env:
          TF_VAR_app_secrets: ${{ secrets.APP_SECRETS_JSON }}
          TF_VAR_api_certificate_arn: ${{ secrets.API_CERT_ARN }}
          TF_VAR_dashboard_certificate_arn: ${{ secrets.DASHBOARD_CERT_ARN }}

      - name: Post Plan to PR
        uses: borchero/terraform-plan-comment@v2
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          planfile: infra/environments/prod/plan.tfplan
```

### Infrastructure Apply (`tofu-apply.yml`)

```yaml
name: OpenTofu Apply

on:
  push:
    branches: [main]
    paths:
      - 'infra/**'

jobs:
  apply:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    environment: production

    steps:
      - uses: actions/checkout@v4

      - uses: opentofu/setup-opentofu@v1
        with:
          tofu_version: '1.7.0'

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-2

      - name: Tofu Init
        working-directory: infra/environments/prod
        run: tofu init

      - name: Tofu Apply
        working-directory: infra/environments/prod
        run: tofu apply -auto-approve
        env:
          TF_VAR_app_secrets: ${{ secrets.APP_SECRETS_JSON }}
          TF_VAR_api_certificate_arn: ${{ secrets.API_CERT_ARN }}
          TF_VAR_dashboard_certificate_arn: ${{ secrets.DASHBOARD_CERT_ARN }}
```

### Lambda Deployment (`deploy-lambdas.yml`)

```yaml
name: Deploy Lambdas

on:
  push:
    branches: [main]
    paths:
      - 'lambdas/**'
      - 'agent/**'
      - 'memory/**'
      - 'tools/**'
      - 'utils/**'
      - 'models/**'
      - 'prompts/**'
      - 'config/**'
      - 'constants/**'
      - 'requirements.txt'

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-2

      - name: Build Lambda Layer
        run: |
          mkdir -p build/layer/python
          pip install -r requirements.txt -t build/layer/python/ --quiet
          cp -r agent/ memory/ tools/ utils/ models/ prompts/ config/ constants/ build/layer/python/
          cd build/layer && zip -r ../layer.zip python/ -x '*.pyc' '__pycache__/*'

      - name: Upload Layer to S3
        run: |
          HASH=$(sha256sum build/layer.zip | cut -d' ' -f1 | head -c 8)
          aws s3 cp build/layer.zip s3://chicago-sports-recap-artifacts/layers/csr-shared-${HASH}.zip
          echo "LAYER_KEY=layers/csr-shared-${HASH}.zip" >> $GITHUB_ENV

      - name: Publish Lambda Layer
        run: |
          LAYER_ARN=$(aws lambda publish-layer-version \
            --layer-name csr-shared \
            --content S3Bucket=chicago-sports-recap-artifacts,S3Key=${{ env.LAYER_KEY }} \
            --compatible-runtimes python3.12 \
            --query 'LayerVersionArn' --output text)
          echo "LAYER_ARN=$LAYER_ARN" >> $GITHUB_ENV

      - name: Package and Deploy Lambda Functions
        run: |
          for dir in lambdas/workflow lambdas/api lambdas/scheduled; do
            for file in $dir/*.py; do
              FUNC_NAME="csr-$(basename $dir)-$(basename $file .py | tr '_' '-')"
              zip -j "build/${FUNC_NAME}.zip" "$file"
              aws lambda update-function-code \
                --function-name "$FUNC_NAME" \
                --zip-file "fileb://build/${FUNC_NAME}.zip" \
                --no-cli-pager
              aws lambda update-function-configuration \
                --function-name "$FUNC_NAME" \
                --layers "${{ env.LAYER_ARN }}" \
                --no-cli-pager
            done
          done

      - name: Wait for Updates
        run: |
          for dir in lambdas/workflow lambdas/api lambdas/scheduled; do
            for file in $dir/*.py; do
              FUNC_NAME="csr-$(basename $dir)-$(basename $file .py | tr '_' '-')"
              aws lambda wait function-updated --function-name "$FUNC_NAME"
            done
          done
          echo "All Lambda functions updated."
```

### SPA Deployment (`deploy-spa.yml`)

```yaml
name: Deploy SPA

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-2

      - name: Build CSS
        run: |
          chmod +x tools/bin/tailwindcss
          ./tools/bin/tailwindcss -i frontend/css/input.css -o frontend/css/output.css --minify

      - name: Deploy to S3
        run: |
          # Static assets — long cache
          aws s3 sync frontend/ s3://chicago-sports-recap-dashboard/ \
            --delete \
            --cache-control "public, max-age=31536000" \
            --exclude "index.html" \
            --exclude "*.js"

          # JS files — short cache
          aws s3 sync frontend/js/ s3://chicago-sports-recap-dashboard/js/ \
            --cache-control "public, max-age=300"

          # index.html — minimal cache
          aws s3 cp frontend/index.html s3://chicago-sports-recap-dashboard/index.html \
            --cache-control "public, max-age=60"

      - name: Invalidate CloudFront
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.CLOUDFRONT_DISTRIBUTION_ID }} \
            --paths "/index.html" "/js/*"
```

### GitHub Secrets Required

| Secret | Purpose |
|---|---|
| `AWS_ROLE_ARN` | IAM role for GitHub Actions OIDC (no long-lived keys) |
| `APP_SECRETS_JSON` | JSON string of all app secrets (passed as `TF_VAR_app_secrets`) |
| `API_CERT_ARN` | ACM certificate ARN for `api.chicagosportsrecap.com` |
| `DASHBOARD_CERT_ARN` | ACM certificate ARN for `dashboard.chicagosportsrecap.com` |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID for cache invalidation |

### OIDC Authentication (No Long-Lived Keys)

GitHub Actions authenticates to AWS via OIDC federation — no `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` stored:

```hcl
# Bootstrap: create OIDC provider + role (run once manually)
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_actions" {
  name = "csr-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:<owner>/my-first-react-agent:*"
        }
      }
    }]
  })
}

# Attach permissions: full access to the resources this pipeline manages
resource "aws_iam_role_policy_attachment" "github_actions" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"  # scope down for production
}
```

---

## 13. Migration Phases

### Phase Overview

| Phase | Duration | Description | Rollback |
|---|---|---|---|
| 0 | 1 day | Bootstrap (state bucket, OIDC, ACM certs) | Delete resources manually |
| 1 | 1–2 days | Infrastructure provisioning via OpenTofu | `tofu destroy` |
| 2 | 1 day | Database migration + validation | Restore from SQLite backup |
| 3 | 1–2 days | Deploy Lambdas + Step Functions, test workflow | Disable EventBridge rule |
| 4 | 1–2 days | Deploy SPA + API Gateway, test approval flow | Revert DNS to local |
| 5 | 1 day | DNS cutover + decommission local | Revert DNS (Cloudflare, instant) |

**Total estimated timeline: 6–9 days**

---

### Phase 0: Bootstrap

Manual one-time setup before OpenTofu can run:

- [ ] Create AWS account (or use existing)
- [ ] Create S3 bucket for Tofu state: `chicago-sports-recap-tfstate`
- [ ] Create DynamoDB table for Tofu lock: `chicago-sports-recap-tflock`
- [ ] Create GitHub OIDC provider + IAM role (see Section 12)
- [ ] Store `AWS_ROLE_ARN` in GitHub Secrets
- [ ] Request ACM certificates in `us-east-1` for:
  - `dashboard.chicagosportsrecap.com`
  - `api.chicagosportsrecap.com`
- [ ] Add DNS validation CNAME records in Cloudflare
- [ ] Wait for certificate validation (usually < 30 minutes)
- [ ] Store certificate ARNs in GitHub Secrets
- [ ] Create Langfuse Cloud account + project, copy keys
- [ ] Assemble `APP_SECRETS_JSON` and store in GitHub Secrets
- [ ] Create Auth0 SPA Application (see Section 7), note the client ID

---

### Phase 1: Infrastructure Provisioning

Run via GitHub Actions (`tofu-apply.yml`) or locally for first run:

- [ ] `tofu init` + `tofu apply` in `infra/environments/prod/`
- [ ] Verify resources created:
  - Secrets Manager secret exists
  - S3 buckets created (frontend + artifacts)
  - Database provisioned (Aurora cluster healthy OR DynamoDB tables active)
  - Lambda functions created (all 11)
  - Lambda layer published
  - Step Functions state machine created
  - EventBridge rules created (disabled initially)
  - API Gateway deployed with custom domain
  - CloudFront distribution deployed
  - SES email identity verified
- [ ] If Aurora path: verify Lambda can connect to database (test invoke `csr-workflow-fetch-scores` with empty event)
- [ ] If DynamoDB path: verify Lambda can read/write tables

---

### Phase 2: Database Migration

Follow Section 10 runbook:

- [ ] Wait for daily workflow to complete on local system
- [ ] Run export script (`export_sqlite_to_json.py` or `sqlite3 .dump`)
- [ ] Run load script (Aurora `psql` import or DynamoDB `load_dynamodb.py`)
- [ ] Run validation script — all row counts must match
- [ ] Spot-check specific records:
  - Most recent workflow run has correct `overall_score`
  - Most recent pending approval has correct `blog_title`
  - Article count matches `SELECT COUNT(*) FROM articles`
- [ ] If validation fails: fix and re-run (SQLite source is unchanged)

---

### Phase 3: Workflow Testing

Test the Step Functions workflow end-to-end without affecting production:

- [ ] Manually start the state machine with test input:
  ```json
  {"run_id": "test-migration-001", "max_articles_per_team": 1}
  ```
- [ ] Monitor execution in Step Functions console
- [ ] Verify each state completes:
  - FetchScores: returns scores from ESPN
  - FetchArticles: returns articles from NewsAPI/SerpAPI
  - Deduplicate: reduces duplicates
  - Summarize (Map): LLM calls succeed, summaries saved to DB
  - DraftAndEvaluate: RevisionAgent produces draft with score
  - CreateTaxonomy: categories/tags created
  - SendApproval: email received via SES
  - Housekeeping: drift check runs, old data purged
- [ ] Check Langfuse Cloud for traces
- [ ] Check database for new workflow run record
- [ ] If any state fails: check CloudWatch logs, fix, re-run
- [ ] Enable EventBridge daily rule (but keep local system running in parallel)
- [ ] Next morning: confirm scheduled execution succeeds

---

### Phase 4: SPA + API Testing

Test the dashboard and approval flow:

- [ ] Deploy SPA to S3 (`deploy-spa.yml` or manual `aws s3 sync`)
- [ ] Access CloudFront URL directly (before DNS cutover): `https://d1234.cloudfront.net`
- [ ] Verify dashboard loads, charts render, data populates from API
- [ ] Test Auth0 login flow:
  - Click Login → Auth0 redirect → callback → JWT stored
  - Protected routes accessible after login
- [ ] Test approval flow:
  - Open approval link from test email
  - Login prompted → approve → WordPress publish triggered
- [ ] Test rejection flow:
  - Open reject link → feedback form → submit → confirmation
- [ ] Verify API rate limiting via Cloudflare (if configured)
- [ ] Verify security headers in browser DevTools (CSP, X-Frame-Options, etc.)

---

### Phase 5: DNS Cutover & Decommission

- [ ] In Cloudflare DNS:
  - Add/update `dashboard` CNAME → CloudFront distribution domain (gray cloud)
  - Add/update `api` CNAME → API Gateway custom domain (orange cloud)
- [ ] Verify both subdomains resolve correctly: `dig dashboard.chicagosportsrecap.com`
- [ ] Access `https://dashboard.chicagosportsrecap.com` — confirm SPA loads
- [ ] Access `https://api.chicagosportsrecap.com/health` — confirm `{"status": "ok"}`
- [ ] Send a test approval email and verify the link works with the new domain
- [ ] **Keep local system running for 7 days** as fallback
- [ ] Monitor: 7 consecutive successful daily workflow runs on AWS
- [ ] After 7 successful runs, decommission local:
  - [ ] `launchctl stop com.chicagosportsrecap.approval-server`
  - [ ] `launchctl stop com.chicagosportsrecap.docker`
  - [ ] `launchctl stop com.chicagosportsrecap.cloudflare-tunnel`
  - [ ] `./services/uninstall.sh`
  - [ ] `docker compose down -v` (removes Langfuse volumes)
  - [ ] Remove Cloudflare Tunnel configuration
  - [ ] Archive `data/articles.db` to S3 for reference
  - [ ] Remove local `.env` file

---

### Post-Migration Checklist

- [ ] All daily workflow runs succeeding on AWS
- [ ] Approval emails received with correct links
- [ ] Dashboard accessible at `https://dashboard.chicagosportsrecap.com`
- [ ] Auth0 login/logout working
- [ ] WordPress publish working on approval
- [ ] Drift alerts sending via SES
- [ ] Failure notifications sending via SES
- [ ] Langfuse Cloud traces appearing
- [ ] CloudWatch logs collecting (set retention to 14 days to match current config)
- [ ] No local services running
- [ ] GitHub Actions pipeline tested (push to `infra/`, `lambdas/`, `frontend/` triggers correct workflow)
- [ ] Cost monitoring: set up AWS Budgets alert at $75/mo (Aurora path) or $10/mo (DynamoDB path)

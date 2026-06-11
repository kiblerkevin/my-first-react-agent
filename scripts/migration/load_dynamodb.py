"""Load exported JSON files into DynamoDB tables.

Idempotent: PutItem overwrites by primary key, so re-running is safe.

Usage:
    python scripts/migration/load_dynamodb.py --export-dir data/export --region us-east-2
    python scripts/migration/load_dynamodb.py --export-dir data/export --dev
    python scripts/migration/load_dynamodb.py --export-dir data/export --tables articles workflow_runs
    python scripts/migration/load_dynamodb.py --export-dir data/export --dry-run
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

import boto3

PREFIX_PROD = "chicago-sports-recap-prod"
PREFIX_DEV = "chicago-sports-recap-dev"

# Maps JSON filename (without .json) to DynamoDB table name suffix and primary key field(s).
TABLE_CONFIG = {
    "articles": {"suffix": "articles", "pk": "url"},
    "article_summaries": {"suffix": "article-summaries", "pk": "url"},
    "summaries": {"suffix": "summaries", "pk": "id"},
    "pending_approvals": {"suffix": "pending-approvals", "pk": "token"},
    "workflow_runs": {"suffix": "workflow-runs", "pk": "run_id"},
    "drift_alerts": {"suffix": "drift-alerts", "pk": "id"},
    "oauth_tokens": {"suffix": "oauth-tokens", "pk": "service"},
    "evaluations": {"suffix": "evaluations", "pk": "id"},
    "summary_stats": {"suffix": "summary-stats", "pk": "id"},
    "api_call_results": {"suffix": "api-call-results", "pk": "id"},
    "categories": {"suffix": "categories", "pk": "id"},
    "tags": {"suffix": "tags", "pk": "id"},
    "summary_tags": {"suffix": "summary-tags", "pk": "id"},
    "improvement_suggestions": {"suffix": "improvement-suggestions", "pk": "id"},
}

# Fields that are integer PKs/FKs in SQLite and must become strings in DynamoDB.
STRING_COERCE_FIELDS = {
    "id", "summary_id", "workflow_run_id", "category_id", "tag_id",
}


def convert_value(value, key: str | None = None):
    """Recursively convert a value to DynamoDB-compatible types."""
    if value is None:
        return None
    if key and key in STRING_COERCE_FIELDS:
        return str(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, int):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: v for k, v in ((k, convert_value(v)) for k, v in value.items()) if v is not None}
    if isinstance(value, list):
        return [convert_value(item) for item in value]
    return value


def convert_item(item: dict) -> dict:
    """Convert a JSON record to DynamoDB-compatible types."""
    return {k: v for k, v in ((k, convert_value(v, k)) for k, v in item.items()) if v is not None}


def load_table(
    dynamodb_resource,
    table_name: str,
    items: list[dict],
    pk_field: str,
    dry_run: bool = False,
) -> int:
    """Batch write items to a DynamoDB table. Returns count written."""
    if dry_run:
        missing_pk = [i for i, item in enumerate(items) if not item.get(pk_field)]
        if missing_pk:
            print(f"  ERROR: {len(missing_pk)} items missing PK '{pk_field}' at indices: {missing_pk[:5]}")
            return 0
        print(f"  [DRY RUN] {len(items)} items validated, all have PK '{pk_field}'")
        return len(items)

    table = dynamodb_resource.Table(table_name)
    written = 0

    with table.batch_writer() as batch:
        for item in items:
            converted = convert_item(item)
            if not converted.get(pk_field):
                print(f"  SKIP: item missing PK '{pk_field}': {converted}")
                continue
            batch.put_item(Item=converted)
            written += 1
            if written % 100 == 0:
                print(f"  {written}/{len(items)}...")

    return written


def main():
    parser = argparse.ArgumentParser(description="Load JSON exports into DynamoDB")
    parser.add_argument("--export-dir", required=True, help="Path to directory containing JSON export files")
    parser.add_argument("--dev", action="store_true", help="Load into dev tables (chicago-sports-recap-dev-*)")
    parser.add_argument("--region", default="us-east-2", help="AWS region (default: us-east-2)")
    parser.add_argument("--tables", nargs="*", help="Only load specific tables (space-separated)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    args = parser.parse_args()

    prefix = PREFIX_DEV if args.dev else PREFIX_PROD
    export_dir = Path(args.export_dir)
    if not export_dir.is_dir():
        print(f"ERROR: Export directory not found: {export_dir}")
        sys.exit(1)

    print(f"Target: {prefix}-* tables in {args.region}")
    dynamodb = boto3.resource("dynamodb", region_name=args.region)

    tables_to_load = args.tables if args.tables else list(TABLE_CONFIG.keys())
    results = {}

    for table_key in tables_to_load:
        if table_key not in TABLE_CONFIG:
            print(f"WARNING: Unknown table '{table_key}', skipping")
            continue

        config = TABLE_CONFIG[table_key]
        json_file = export_dir / f"{table_key}.json"

        if not json_file.exists():
            print(f"SKIP: {json_file} not found")
            continue

        table_name = f"{prefix}-{config['suffix']}"
        print(f"\nLoading {table_key} -> {table_name}")

        with open(json_file) as f:
            items = json.load(f)

        print(f"  Records in file: {len(items)}")

        if not items:
            results[table_key] = 0
            continue

        try:
            written = load_table(dynamodb, table_name, items, config["pk"], args.dry_run)
            results[table_key] = written
            print(f"  Done: {written}/{len(items)}")
        except Exception as e:
            print(f"  FAILED: {e}")
            print(f"\n  Re-run with: --tables {table_key}")
            sys.exit(1)

    print("\n--- Summary ---")
    for table_key, count in results.items():
        print(f"  {table_key}: {count} records")
    print(f"  Total: {sum(results.values())} records")


if __name__ == "__main__":
    main()

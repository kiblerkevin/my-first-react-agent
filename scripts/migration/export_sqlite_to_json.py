"""Export SQLite tables to JSON files for DynamoDB migration.

Produces one JSON file per table in the export directory.
Fields containing JSON strings are parsed into native objects.

Usage:
    python scripts/migration/export_sqlite_to_json.py
    python scripts/migration/export_sqlite_to_json.py --db data/articles.db --output data/export
    python scripts/migration/export_sqlite_to_json.py --tables articles workflow_runs

After export, load into DynamoDB with:
    python scripts/migration/load_dynamodb.py --export-dir data/export
    python scripts/migration/load_dynamodb.py --export-dir data/export --dev
"""

import argparse
import json
import sqlite3
from pathlib import Path

# Fields known to contain JSON-encoded strings in SQLite.
JSON_FIELDS = {
    'steps_completed',
    'usage_by_tool',
    'checkpoint_data',
    'draft_iterations',
    'score_progression',
    'players_mentioned',
    'teams_covered',
    'taxonomy_data',
    'evaluation_data',
    'summaries_data',
    'scores_data',
}

TABLES = [
    'articles',
    'article_summaries',
    'summaries',
    'pending_approvals',
    'workflow_runs',
    'drift_alerts',
    'oauth_tokens',
    'evaluations',
    'summary_stats',
    'api_call_results',
    'categories',
    'tags',
    'summary_tags',
    'improvement_suggestions',
]


def parse_json_field(value: str | None) -> str | list | dict | None:
    """Attempt to parse a string as JSON. Return original if it fails."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def export_table(conn: sqlite3.Connection, table: str, output_dir: Path) -> int:
    """Export a single table to JSON. Returns record count."""
    cursor = conn.execute(f'SELECT * FROM {table}')  # noqa: S608
    columns = [desc[0] for desc in cursor.description]
    rows = []

    for row in cursor.fetchall():
        record = {}
        for col, val in zip(columns, row, strict=True):
            if col in JSON_FIELDS:
                record[col] = parse_json_field(val)
            else:
                record[col] = val
        rows.append(record)

    output_file = output_dir / f'{table}.json'
    with open(output_file, 'w') as f:
        json.dump(rows, f, indent=2, ensure_ascii=False, default=str)

    return len(rows)


def main():
    """Export SQLite tables to individual JSON files."""
    parser = argparse.ArgumentParser(description='Export SQLite tables to JSON')
    parser.add_argument(
        '--db', default='data/articles.db', help='Path to SQLite database'
    )
    parser.add_argument(
        '--output', default='data/export', help='Output directory for JSON files'
    )
    parser.add_argument('--tables', nargs='*', help='Only export specific tables')
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f'ERROR: Database not found: {db_path}')
        raise SystemExit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    tables_to_export = args.tables if args.tables else TABLES
    results = {}

    for table in tables_to_export:
        if table not in TABLES:
            print(f"WARNING: Unknown table '{table}', skipping")
            continue
        count = export_table(conn, table, output_dir)
        results[table] = count
        print(f'  {table}: {count} records -> {output_dir / f"{table}.json"}')

    conn.close()

    print('\n--- Export Complete ---')
    print(f'  Total: {sum(results.values())} records across {len(results)} tables')
    print(f'  Output: {output_dir.resolve()}')


if __name__ == '__main__':
    main()

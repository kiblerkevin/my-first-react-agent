"""Custom agent compliance checker.

Checks for patterns that ruff/mypy might miss, specifically targeting
the agent code standards defined in docs/agent-code-standards.md.

This script scans Python files for common violations:
- Functions without type hints
- Classes without docstrings
- Magic numbers
- Untracked comment markers
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class ComplianceViolation:
    """Represents a single compliance violation."""

    file_path: str
    line_number: int
    rule: str
    message: str
    severity: str  # error, warning, info


@dataclass
class ComplianceReport:
    """Report for compliance check."""

    timestamp: str
    files_scanned: int
    violations: list[ComplianceViolation] = field(default_factory=list)
    passed: bool = True
    summary: dict[str, int] = field(default_factory=dict)


# ============================================================================
# Rule Checkers
# ============================================================================


def check_functions_without_type_hints(
    content: str, file_path: str
) -> list[ComplianceViolation]:
    """Check for functions without type hints on parameters or return type."""
    violations = []

    # Pattern to match function definitions
    # Handles: def func_name(...): and async def func_name(...):
    func_pattern = re.compile(
        r'^(async\s+)?def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*[^:]+)?\s*:',
        re.MULTILINE,
    )

    for line_num, line in enumerate(content.split('\n'), 1):
        # Skip comments and strings
        if (
            line.strip().startswith('#')
            or line.strip().startswith('"""')
            or line.strip().startswith("'''")
        ):
            continue

        match = func_pattern.search(line)
        if match:
            func_name = match.group(2)
            params = match.group(3)

            # Skip private methods and dunder methods (except __init__)
            if func_name.startswith('_') and func_name != '__init__':
                continue

            # Check if there are parameters without type hints
            # Simple heuristic: if there's a colon in params, it has type hints
            has_type_hints = ':' in params or '->' in line

            if not has_type_hints and params.strip():
                violations.append(
                    ComplianceViolation(
                        file_path=file_path,
                        line_number=line_num,
                        rule='type-hint',
                        message=f"Function '{func_name}' lacks type hints on parameters or return type",
                        severity='error',
                    )
                )

    return violations


def check_classes_without_docstrings(
    content: str, file_path: str
) -> list[ComplianceViolation]:
    """Check for classes without docstrings."""
    violations = []

    # Pattern to match class definitions
    class_pattern = re.compile(
        r'^class\s+(\w+)\s*(?:\([^)]*\))?\s*:',
        re.MULTILINE,
    )

    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        match = class_pattern.search(line)
        if match:
            class_name = match.group(1)

            # Skip private classes
            if class_name.startswith('_'):
                continue

            # Check if next non-empty line is a docstring
            next_line_idx = line_num  # 0-indexed
            found_docstring = False

            for i in range(next_line_idx, min(next_line_idx + 5, len(lines))):
                next_line = lines[i].strip()
                if not next_line:
                    continue
                if next_line.startswith('#'):
                    continue
                if '"""' in next_line or "'''" in next_line:
                    found_docstring = True
                    break
                # If we hit code (not a comment or docstring), no docstring
                break

            if not found_docstring:
                violations.append(
                    ComplianceViolation(
                        file_path=file_path,
                        line_number=line_num,
                        rule='docstring',
                        message=f"Class '{class_name}' lacks a docstring",
                        severity='error',
                    )
                )

    return violations


def check_magic_numbers(content: str, file_path: str) -> list[ComplianceViolation]:
    """Check for magic numbers in code (not in comments or strings)."""
    violations = []

    lines = content.split('\n')

    # Patterns that indicate magic numbers
    magic_pattern = re.compile(
        r'(?<![.\w])([0-9]{4,})(?![.\w])',  # 4+ digit numbers not in identifiers
    )

    # Known acceptable patterns (constants, dates, etc.)
    acceptable_patterns = [
        r'^\s*#',  # Comments
        r'^\s*"""',  # Docstring start
        r"^\s*'''",  # Docstring start
        r'DEFAULT_\w+',  # DEFAULT_ constants
        r'MAX_\w+',  # MAX_ constants
        r'MIN_\w+',  # MIN_ constants
        r'TIMEOUT',  # TIMEOUT constants
        r'PORT',  # PORT constants
        r'YEAR',  # YEAR in dates
    ]

    # Skip patterns - lines that are valid uses of numbers
    skip_patterns = [
        r'default=',  # dataclass field default
        r'default_factory=',  # dataclass field factory
        r'field\(',  # dataclass field
    ]

    for line_num, line in enumerate(lines, 1):
        # Skip comments, docstrings, strings
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        if '"""' in line or "'''" in line:
            # Simple check - if odd number of triple quotes, likely in string
            if line.count('"""') % 2 == 1 or line.count("'''") % 2 == 1:
                continue

        # Skip lines that match skip patterns
        if any(pattern in line for pattern in skip_patterns):
            continue

        # Check for magic numbers
        for match in magic_pattern.finditer(line):
            num = match.group(1)

            # Skip if it matches acceptable patterns
            is_acceptable = False
            for pattern in acceptable_patterns:
                if re.search(pattern, line):
                    is_acceptable = True
                    break

            # Skip common acceptable numbers
            if num in ('3600', '86400', '1000', '100', '50', '10', '5', '3', '2', '1'):
                continue
            elif not is_acceptable and int(num) > 100:
                violations.append(
                    ComplianceViolation(
                        file_path=file_path,
                        line_number=line_num,
                        rule='magic-number',
                        message=f"Magic number '{num}' found - use named constants instead",
                        severity='warning',
                    )
                )

    return violations


def check_todo_fixme_comments(
    content: str, file_path: str
) -> list[ComplianceViolation]:
    """Check for TODO/FIXME comments left behind."""
    violations = []

    lines = content.split('\n')

    # Pattern to match TODO/FIXME/HACK comments
    todo_pattern = re.compile(
        r'^\s*#\s*(TODO|FIXME|HACK|XXX|BUG):?\s*(.*)',
        re.IGNORECASE,
    )

    for line_num, line in enumerate(lines, 1):
        match = todo_pattern.search(line)
        if match:
            comment_type = match.group(1).upper()
            comment_text = match.group(2)

            # Skip if it's tracking a known issue (has issue number)
            if re.search(r'[A-Z]+-\d+', comment_text):  # e.g., JIRA-123
                continue

            violations.append(
                ComplianceViolation(
                    file_path=file_path,
                    line_number=line_num,
                    rule='todo-fixme',
                    message=f'{comment_type} comment found: {comment_text[:50]}',
                    severity='warning',
                )
            )

    return violations


def check_wildcard_imports(content: str, file_path: str) -> list[ComplianceViolation]:
    """Check for wildcard imports (from module import *)."""
    violations = []

    lines = content.split('\n')

    wildcard_pattern = re.compile(r'^\s*from\s+[\w.]+\s+import\s+\*')

    for line_num, line in enumerate(lines, 1):
        if wildcard_pattern.search(line):
            violations.append(
                ComplianceViolation(
                    file_path=file_path,
                    line_number=line_num,
                    rule='wildcard-import',
                    message='Wildcard import found - use explicit imports instead',
                    severity='warning',
                )
            )

    return violations


# ============================================================================
# File Scanning
# ============================================================================


def get_session_files() -> list[Path]:
    """Get files modified in the current session (today or git changes)."""
    files = []

    # Try git first
    try:
        import subprocess

        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.strip():
                    # Get file path (skip status characters)
                    file_path = line[3:].strip()
                    if file_path.endswith('.py'):
                        files.append(Path(file_path))
            return files
    except Exception:
        pass

    # Fallback: files modified today
    today = datetime.now().date()
    for root, dirs, filenames in os.walk('.'):
        # Skip hidden directories and common non-source dirs
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith('.')
            and d not in ('venv', 'node_modules', '__pycache__')
        ]

        for filename in filenames:
            if filename.endswith('.py'):
                file_path = Path(root) / filename
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime).date()
                    if mtime == today:
                        files.append(file_path)
                except Exception:
                    continue

    return files


def scan_file(file_path: Path) -> list[ComplianceViolation]:
    """Scan a single file for compliance violations."""
    violations = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f'Error reading {file_path}: {e}', file=sys.stderr)
        return violations

    # Run all checkers
    violations.extend(check_functions_without_type_hints(content, str(file_path)))
    violations.extend(check_classes_without_docstrings(content, str(file_path)))
    violations.extend(check_magic_numbers(content, str(file_path)))
    violations.extend(check_todo_fixme_comments(content, str(file_path)))
    violations.extend(check_wildcard_imports(content, str(file_path)))

    return violations


def scan_files(file_paths: list[Path]) -> list[ComplianceViolation]:
    """Scan multiple files for compliance violations."""
    all_violations = []

    for file_path in file_paths:
        violations = scan_file(file_path)
        all_violations.extend(violations)

    return all_violations


# ============================================================================
# Report Generation
# ============================================================================


def generate_summary(violations: list[ComplianceViolation]) -> dict[str, int]:
    """Generate summary statistics from violations."""
    summary: dict[str, int] = {
        'total_violations': len(violations),
        'files_with_violations': len(set(v.file_path for v in violations)),
    }

    # Count by rule
    for v in violations:
        summary[f'{v.rule}_count'] = summary.get(f'{v.rule}_count', 0) + 1

    # Count by severity
    summary['errors'] = sum(1 for v in violations if v.severity == 'error')
    summary['warnings'] = sum(1 for v in violations if v.severity == 'warning')

    return summary


def format_report(report: ComplianceReport) -> str:
    """Format the report as a human-readable string."""
    lines = [
        '=' * 70,
        'AGENT COMPLIANCE CHECK REPORT',
        '=' * 70,
        f'Timestamp: {report.timestamp}',
        f'Files Scanned: {report.files_scanned}',
        '',
        '-' * 70,
        'SUMMARY',
        '-' * 70,
    ]

    summary = report.summary
    lines.extend(
        [
            f'  Total Violations: {summary.get("total_violations", 0)}',
            f'    - Errors: {summary.get("errors", 0)}',
            f'    - Warnings: {summary.get("warnings", 0)}',
            f'  Files with Violations: {summary.get("files_with_violations", 0)}',
            '',
        ]
    )

    # Rule breakdown
    if any(
        f'{k}_count' in summary
        for k in (
            'type-hint',
            'docstring',
            'magic-number',
            'todo-fixme',
            'wildcard-import',
        )
    ):
        lines.extend(['-' * 70, 'VIOLATIONS BY RULE', '-' * 70])
        for rule in (
            'type-hint',
            'docstring',
            'magic-number',
            'todo-fixme',
            'wildcard-import',
        ):
            count = summary.get(f'{rule}_count', 0)
            if count > 0:
                rule_display = rule.replace('-', ' ').title()
                lines.append(f'  {rule_display}: {count}')
        lines.append('')

    # Top violations
    if report.violations:
        lines.extend(['-' * 70, 'VIOLATIONS DETAIL', '-' * 70])
        for v in report.violations[:20]:
            lines.append(f'  {v.file_path}:{v.line_number} [{v.rule}] {v.message}')
        lines.append('')

    # Recommendations
    lines.extend(['-' * 70, 'RECOMMENDATIONS', '-' * 70])

    recommendations = get_recommendations(report)
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            lines.append(f'  {i}. {rec}')
    else:
        lines.append('  ✅ No violations found - great job!')

    lines.append('')
    lines.append('=' * 70)

    return '\n'.join(lines)


def get_recommendations(report: ComplianceReport) -> list[str]:
    """Generate recommendations based on violations."""
    recommendations = []
    summary = report.summary

    # Type hints
    type_hint_count = summary.get('type-hint_count', 0)
    if type_hint_count > 0:
        recommendations.append(
            f'Add type hints to {type_hint_count} functions '
            '(see docs/agent-code-standards.md)'
        )

    # Docstrings
    docstring_count = summary.get('docstring_count', 0)
    if docstring_count > 0:
        recommendations.append(
            f'Add docstrings to {docstring_count} classes '
            '(see docs/agent-code-standards.md)'
        )

    # Magic numbers
    magic_count = summary.get('magic-number_count', 0)
    if magic_count > 0:
        recommendations.append(
            f'Replace {magic_count} magic numbers with named constants '
            '(see docs/agent-code-standards.md)'
        )

    # Untracked comment markers
    todo_count = summary.get('todo-fixme_count', 0)
    if todo_count > 0:
        recommendations.append(
            f'Remove or track {todo_count} untracked comment markers '
            '(add issue numbers or remove)'
        )

    # Wildcard imports
    wildcard_count = summary.get('wildcard-import_count', 0)
    if wildcard_count > 0:
        recommendations.append(
            f'Replace {wildcard_count} wildcard imports with explicit imports'
        )

    return recommendations


def save_report_json(report: ComplianceReport, output_path: Path) -> None:
    """Save report as JSON for programmatic access."""
    data = {
        'timestamp': report.timestamp,
        'files_scanned': report.files_scanned,
        'passed': report.passed,
        'summary': report.summary,
        'violations': [
            {
                'file': v.file_path,
                'line': v.line_number,
                'rule': v.rule,
                'message': v.message,
                'severity': v.severity,
            }
            for v in report.violations
        ],
    }

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)


# ============================================================================
# Main
# ============================================================================


def main() -> int:
    """Run compliance check."""
    parser = argparse.ArgumentParser(
        description='Check agent code compliance against custom rules'
    )
    parser.add_argument(
        '--files',
        nargs='*',
        default=[],
        help='Specific files to check (default: session files)',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('logs/agent_sessions'),
        help='Directory to save reports',
    )
    parser.add_argument(
        '--json-only',
        action='store_true',
        help='Only output JSON, no human-readable report',
    )
    parser.add_argument(
        '--skip-session-detection',
        action='store_true',
        help="Don't auto-detect session files, require --files",
    )
    parser.add_argument(
        '--rules',
        nargs='*',
        default=[
            'type-hint',
            'docstring',
            'magic-number',
            'todo-fixme',
            'wildcard-import',
        ],
        help='Rules to check (default: all)',
    )

    args = parser.parse_args()

    # Determine files to scan
    if args.files:
        file_paths = [Path(f) for f in args.files]
    elif args.skip_session_detection:
        print('No files specified and session detection disabled.', file=sys.stderr)
        print('Use --files to specify files to check.', file=sys.stderr)
        return 1
    else:
        file_paths = get_session_files()
        if not file_paths:
            print(
                'No session files found. Use --files to specify files.', file=sys.stderr
            )
            return 1

    print(f'Scanning {len(file_paths)} files...')

    # Scan files
    violations = scan_files(file_paths)

    # Generate summary
    summary = generate_summary(violations)

    # Create report
    report = ComplianceReport(
        timestamp=datetime.now().isoformat(),
        files_scanned=len(file_paths),
        violations=violations,
        passed=len(violations) == 0,
        summary=summary,
    )

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON report
    timestamp_short = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = args.output_dir / f'compliance_{timestamp_short}.json'
    save_report_json(report, json_path)
    print(f'JSON report saved to: {json_path}')

    # Print human-readable report
    if not args.json_only:
        print('')
        print(format_report(report))

    # Exit with appropriate code
    return 0 if report.passed else 1


if __name__ == '__main__':
    sys.exit(main())

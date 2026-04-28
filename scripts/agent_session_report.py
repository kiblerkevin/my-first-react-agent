"""Agent session post-commit report generator.

Generates a report after agent runs to provide feedback on code quality.
Parses ruff and mypy output, categorizes violations, and provides recommendations.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class Violation:
    """Represents a single code quality violation."""

    file_path: str
    line_number: int
    code: str
    message: str
    severity: str  # error, warning, info
    category: str  # type-hint, docstring, magic-number, etc.


@dataclass
class AgentSessionReport:
    """Report for an agent session."""

    timestamp: str
    duration_seconds: float
    files_changed: list[str]
    ruff_violations: list[Violation] = field(default_factory=list)
    mypy_errors: list[Violation] = field(default_factory=list)
    passed: bool = True
    summary: dict[str, int] = field(default_factory=dict)


# ============================================================================
# Violation Categorization
# ============================================================================


# Map ruff/mypy codes to categories
VIOLATION_CATEGORIES: dict[str, str] = {
    # Type hints
    "ANN": "type-hint",
    "ANN001": "type-hint",
    "ANN002": "type-hint",
    "ANN003": "type-hint",
    "ANN100": "type-hint",
    "ANN101": "type-hint",
    "ANN102": "type-hint",
    "ANN201": "type-hint",
    "ANN401": "type-hint",
    # Docstrings
    "D": "docstring",
    "D100": "docstring",
    "D101": "docstring",
    "D102": "docstring",
    "D103": "docstring",
    "D104": "docstring",
    "D105": "docstring",
    "D106": "docstring",
    "D107": "docstring",
    "D200": "docstring",
    "D205": "docstring",
    "D400": "docstring",
    "D401": "docstring",
    "D404": "docstring",
    # Magic numbers
    "SIM": "magic-number",
    "SIM109": "magic-number",
    # Imports
    "I": "import",
    "F401": "import",
    "F403": "import",
    "F405": "import",
    # Code style
    "E": "code-style",
    "W": "code-style",
    "B": "code-style",
    # Bugbear
    "B006": "bugbear",
    "B007": "bugbear",
    "B008": "bugbear",
    "B009": "bugbear",
    "B010": "bugbear",
}

# Mypy error codes to categories
MYPY_CATEGORIES: dict[str, str] = {
    "return": "return-type",
    "arg-type": "argument-type",
    "return-value": "return-type",
    "typed-dict": "typed-dict",
    "misc": "misc",
    "attr-defined": "attribute",
    "has-type": "has-type",
    "valid-type": "valid-type",
    "name-defined": "name-defined",
    "import": "import",
}


def categorize_violation(code: str, message: str) -> str:
    """Categorize a violation based on its code or message."""
    # Check code mapping
    code_prefix = code.split(".")[0] if "." in code else code[:3]
    if code_prefix in VIOLATION_CATEGORIES:
        return VIOLATION_CATEGORIES[code_prefix]

    # Check message patterns
    message_lower = message.lower()
    if "type" in message_lower and "hint" in message_lower:
        return "type-hint"
    if "docstring" in message_lower or "missing docstring" in message_lower:
        return "docstring"
    if "magic number" in message_lower or "literal" in message_lower:
        return "magic-number"
    if "import" in message_lower:
        return "import"

    return "other"


# ============================================================================
# Ruff Parser
# ============================================================================


def parse_ruff_output(output: str) -> list[Violation]:
    """Parse ruff linter output into Violation objects."""
    violations = []

    # Pattern: file:line:col: CODE message
    pattern = re.compile(
        r"^(.+?):(\d+):(\d+):\s*([A-Z]\d+)\s+(.+)$",
        re.MULTILINE,
    )

    for match in pattern.finditer(output):
        file_path, line, col, code, message = match.groups()
        severity = "error" if code.startswith(("E", "F")) else "warning"

        violations.append(
            Violation(
                file_path=file_path,
                line_number=int(line),
                code=code,
                message=message.strip(),
                severity=severity,
                category=categorize_violation(code, message),
            )
        )

    return violations


# ============================================================================
# MyPy Parser
# ============================================================================


def parse_mypy_output(output: str) -> list[Violation]:
    """Parse mypy type checker output into Violation objects."""
    violations = []

    # Pattern: file:line: error code: message
    pattern = re.compile(
        r"^(.+?):(\d+):\s*error:\s*(.+)$",
        re.MULTILINE,
    )

    for match in pattern.finditer(output):
        file_path, line, message = match.groups()

        # Extract code from message (e.g., "return-value" from "Incompatible return type...")
        code = "mypy"
        for key in MYPY_CATEGORIES:
            if key in message.lower():
                code = key
                break

        violations.append(
            Violation(
                file_path=file_path,
                line_number=int(line),
                code=code,
                message=message.strip(),
                severity="error",
                category=MYPY_CATEGORIES.get(code, "other"),
            )
        )

    return violations


# ============================================================================
# Report Generation
# ============================================================================


def run_ruff() -> tuple[str, int]:
    """Run ruff linter and return output and exit code."""
    try:
        result = subprocess.run(
            ["ruff", "check", ".", "--output-format=concise"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout + result.stderr, result.returncode
    except FileNotFoundError:
        # Try with venv
        try:
            result = subprocess.run(
                ["bash", "-c", "source venv/bin/activate && ruff check ."],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.stdout + result.stderr, result.returncode
        except Exception as e:
            return f"Error running ruff: {e}", 1
    except Exception as e:
        return f"Error running ruff: {e}", 1


def run_mypy() -> tuple[str, int]:
    """Run mypy type checker and return output and exit code."""
    try:
        result = subprocess.run(
            ["mypy", "."],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout + result.stderr, result.returncode
    except FileNotFoundError:
        # Try with venv
        try:
            result = subprocess.run(
                ["bash", "-c", "source venv/bin/activate && mypy ."],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.stdout + result.stderr, result.returncode
        except Exception as e:
            return f"Error running mypy: {e}", 1
    except Exception as e:
        return f"Error running mypy: {e}", 1


def generate_summary(
    ruff_violations: list[Violation],
    mypy_errors: list[Violation],
) -> dict[str, int]:
    """Generate summary statistics from violations."""
    summary: dict[str, int] = {
        "total_ruff_violations": len(ruff_violations),
        "total_mypy_errors": len(mypy_errors),
        "files_affected": len(set(v.file_path for v in ruff_violations + mypy_errors)),
    }

    # Count by category
    for v in ruff_violations:
        summary[f"ruff_{v.category}"] = summary.get(f"ruff_{v.category}", 0) + 1

    for v in mypy_errors:
        summary[f"mypy_{v.category}"] = summary.get(f"mypy_{v.category}", 0) + 1

    # Count by severity
    summary["ruff_errors"] = sum(1 for v in ruff_violations if v.severity == "error")
    summary["ruff_warnings"] = sum(
        1 for v in ruff_violations if v.severity == "warning"
    )
    summary["mypy_errors"] = len(mypy_errors)

    return summary


def format_report(report: AgentSessionReport) -> str:
    """Format the report as a human-readable string."""
    lines = [
        "=" * 70,
        "AGENT SESSION REPORT",
        "=" * 70,
        f"Timestamp: {report.timestamp}",
        f"Duration: {report.duration_seconds:.2f}s",
        f"Files Changed: {len(report.files_changed)}",
        "",
        "-" * 70,
        "SUMMARY",
        "-" * 70,
    ]

    summary = report.summary
    lines.extend(
        [
            f"  Ruff Violations: {summary.get('total_ruff_violations', 0)}",
            f"    - Errors: {summary.get('ruff_errors', 0)}",
            f"    - Warnings: {summary.get('ruff_warnings', 0)}",
            f"  MyPy Errors: {summary.get('total_mypy_errors', 0)}",
            f"  Files Affected: {summary.get('files_affected', 0)}",
            "",
        ]
    )

    # Category breakdown
    if any(k.startswith("ruff_") for k in summary):
        lines.extend(["-" * 70, "RUFF VIOLATIONS BY CATEGORY", "-" * 70])
        for key, value in sorted(summary.items()):
            if key.startswith("ruff_") and value > 0:
                category = key.replace("ruff_", "").replace("_", " ").title()
                lines.append(f"  {category}: {value}")
        lines.append("")

    if any(k.startswith("mypy_") for k in summary):
        lines.extend(["-" * 70, "MYPY ERRORS BY CATEGORY", "-" * 70])
        for key, value in sorted(summary.items()):
            if key.startswith("mypy_") and value > 0:
                category = key.replace("mypy_", "").replace("_", " ").title()
                lines.append(f"  {category}: {value}")
        lines.append("")

    # Top violations
    if report.ruff_violations:
        lines.extend(["-" * 70, "TOP RUFF VIOLATIONS", "-" * 70])
        for v in report.ruff_violations[:10]:
            lines.append(f"  {v.file_path}:{v.line_number} [{v.code}] {v.message}")
        lines.append("")

    if report.mypy_errors:
        lines.extend(["-" * 70, "TOP MYPY ERRORS", "-" * 70])
        for v in report.mypy_errors[:10]:
            lines.append(f"  {v.file_path}:{v.line_number} {v.message}")
        lines.append("")

    # Recommendations
    lines.extend(["-" * 70, "RECOMMENDATIONS", "-" * 70])

    recommendations = get_recommendations(report)
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"  {i}. {rec}")
    else:
        lines.append("  ✅ No violations found - great job!")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def get_recommendations(report: AgentSessionReport) -> list[str]:
    """Generate recommendations based on violations."""
    recommendations = []
    summary = report.summary

    # Type hints
    type_hint_count = summary.get("ruff_type-hint", 0)
    if type_hint_count > 0:
        recommendations.append(
            f"Add type hints to {type_hint_count} functions/methods "
            "(see docs/agent-code-standards.md)"
        )

    # Docstrings
    docstring_count = summary.get("ruff_docstring", 0)
    if docstring_count > 0:
        recommendations.append(
            f"Add docstrings to {docstring_count} classes/functions "
            "(see docs/agent-code-standards.md)"
        )

    # Magic numbers
    magic_count = summary.get("ruff_magic-number", 0)
    if magic_count > 0:
        recommendations.append(
            f"Replace {magic_count} magic numbers with named constants "
            "(see docs/agent-code-standards.md)"
        )

    # Imports
    import_count = summary.get("ruff_import", 0)
    if import_count > 0:
        recommendations.append(
            f"Clean up {import_count} import issues "
            "(remove unused, fix wildcard imports)"
        )

    # MyPy
    mypy_count = summary.get("total_mypy_errors", 0)
    if mypy_count > 0:
        recommendations.append(
            f"Fix {mypy_count} type errors reported by mypy"
        )

    return recommendations


def save_report_json(report: AgentSessionReport, output_path: Path) -> None:
    """Save report as JSON for programmatic access."""
    data = {
        "timestamp": report.timestamp,
        "duration_seconds": report.duration_seconds,
        "files_changed": report.files_changed,
        "passed": report.passed,
        "summary": report.summary,
        "ruff_violations": [
            {
                "file": v.file_path,
                "line": v.line_number,
                "code": v.code,
                "message": v.message,
                "severity": v.severity,
                "category": v.category,
            }
            for v in report.ruff_violations
        ],
        "mypy_errors": [
            {
                "file": v.file_path,
                "line": v.line_number,
                "code": v.code,
                "message": v.message,
                "severity": v.severity,
                "category": v.category,
            }
            for v in report.mypy_errors
        ],
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)


# ============================================================================
# Main
# ============================================================================


def main() -> int:
    """Generate agent session report."""
    parser = argparse.ArgumentParser(
        description="Generate post-commit code quality report for agent sessions"
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=[],
        help="Files changed in this session",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Session duration in seconds",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("logs/agent_sessions"),
        help="Directory to save reports",
    )
    parser.add_argument(
        "--skip-ruff",
        action="store_true",
        help="Skip ruff check",
    )
    parser.add_argument(
        "--skip-mypy",
        action="store_true",
        help="Skip mypy check",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only output JSON, no human-readable report",
    )

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamp
    timestamp = datetime.now().isoformat()
    timestamp_short = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Run ruff
    ruff_violations = []
    if not args.skip_ruff:
        print("Running ruff...")
        ruff_output, ruff_code = run_ruff()
        ruff_violations = parse_ruff_output(ruff_output)
        print(f"  Found {len(ruff_violations)} violations")

    # Run mypy
    mypy_errors = []
    if not args.skip_mypy:
        print("Running mypy...")
        mypy_output, mypy_code = run_mypy()
        mypy_errors = parse_mypy_output(mypy_output)
        print(f"  Found {len(mypy_errors)} errors")

    # Generate summary
    summary = generate_summary(ruff_violations, mypy_errors)

    # Create report
    report = AgentSessionReport(
        timestamp=timestamp,
        duration_seconds=args.duration,
        files_changed=args.files,
        ruff_violations=ruff_violations,
        mypy_errors=mypy_errors,
        passed=len(ruff_violations) == 0 and len(mypy_errors) == 0,
        summary=summary,
    )

    # Save JSON report
    json_path = args.output_dir / f"report_{timestamp_short}.json"
    save_report_json(report, json_path)
    print(f"JSON report saved to: {json_path}")

    # Print human-readable report
    if not args.json_only:
        print("")
        print(format_report(report))

    # Exit with appropriate code
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())

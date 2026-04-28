"""Agent activity logger.

Tracks file reads, terminal commands, and tool executions during agent sessions.
Logs to JSON files in logs/agent_sessions/ for later analysis.

Usage:
    from scripts.agent_activity_logger import AgentActivityLogger

    logger = AgentActivityLogger()
    logger.log_file_read("src/tool.py")
    logger.log_command("git status")
    logger.log_tool_execution("fetch_articles", {"sport": "nba"})

    # At end of session
    logger.save_session()
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class FileRead:
    """Represents a file read event."""

    file_path: str
    timestamp: str
    line_count: int | None = None
    success: bool = True
    error: str | None = None


@dataclass
class CommandExecution:
    """Represents a terminal command execution."""

    command: str
    timestamp: str
    working_directory: str
    exit_code: int | None = None
    duration_seconds: float | None = None


@dataclass
class ToolExecution:
    """Represents a tool execution by the agent."""

    tool_name: str
    timestamp: str
    input_data: dict[str, Any] = field(default_factory=dict)
    output_summary: str | None = None
    success: bool = True
    error: str | None = None


@dataclass
class AgentSession:
    """Represents a complete agent session."""

    session_id: str
    start_time: str
    end_time: str | None = None
    files_read: list[FileRead] = field(default_factory=list)
    commands_executed: list[CommandExecution] = field(default_factory=list)
    tools_executed: list[ToolExecution] = field(default_factory=list)
    compliance_status: str | None = None
    rule_violations: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Activity Logger
# ============================================================================


class AgentActivityLogger:
    """Logger for tracking agent activity during sessions."""

    def __init__(self, session_id: str | None = None) -> None:
        """Initialize the activity logger.

        Args:
            session_id: Optional session ID. Generated if not provided.
        """
        self.session_id = session_id or datetime.now().strftime('%Y%m%d_%H%M%S')
        self.start_time = datetime.now().isoformat()
        self.files_read: list[FileRead] = []
        self.commands_executed: list[CommandExecution] = []
        self.tools_executed: list[ToolExecution] = []
        self.metadata: dict[str, Any] = {}
        self._current_working_dir = os.getcwd()

    def log_file_read(
        self,
        file_path: str,
        line_count: int | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Log a file read event.

        Args:
            file_path: Path to the file that was read.
            line_count: Number of lines in the file (optional).
            success: Whether the read was successful.
            error: Error message if the read failed.
        """
        self.files_read.append(
            FileRead(
                file_path=file_path,
                timestamp=datetime.now().isoformat(),
                line_count=line_count,
                success=success,
                error=error,
            )
        )

    def log_command(
        self,
        command: str,
        exit_code: int | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        """Log a terminal command execution.

        Args:
            command: The command that was executed.
            exit_code: Exit code of the command (if known).
            duration_seconds: How long the command took to execute.
        """
        self.commands_executed.append(
            CommandExecution(
                command=command,
                timestamp=datetime.now().isoformat(),
                working_directory=os.getcwd(),
                exit_code=exit_code,
                duration_seconds=duration_seconds,
            )
        )

    def log_tool_execution(
        self,
        tool_name: str,
        input_data: dict[str, Any] | None = None,
        output_summary: str | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Log a tool execution by the agent.

        Args:
            tool_name: Name of the tool that was executed.
            input_data: Input data passed to the tool.
            output_summary: Summary of the tool output.
            success: Whether the tool execution was successful.
            error: Error message if the tool failed.
        """
        self.tools_executed.append(
            ToolExecution(
                tool_name=tool_name,
                timestamp=datetime.now().isoformat(),
                input_data=input_data or {},
                output_summary=output_summary,
                success=success,
                error=error,
            )
        )

    def set_compliance_status(
        self,
        status: str,
        rule_violations: int = 0,
    ) -> None:
        """Set the compliance status for the session.

        Args:
            status: Compliance status (passed, failed, warnings).
            rule_violations: Number of rule violations found.
        """
        self.compliance_status = status
        self.rule_violations = rule_violations

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the session.

        Args:
            key: Metadata key.
            value: Metadata value.
        """
        self.metadata[key] = value

    def get_session(self) -> AgentSession:
        """Get the current session data."""
        return AgentSession(
            session_id=self.session_id,
            start_time=self.start_time,
            end_time=datetime.now().isoformat(),
            files_read=self.files_read,
            commands_executed=self.commands_executed,
            tools_executed=self.tools_executed,
            compliance_status=self.compliance_status,
            rule_violations=self.rule_violations,
            metadata=self.metadata,
        )

    def save_session(self, output_dir: Path | None = None) -> Path:
        """Save the session data to a JSON file.

        Args:
            output_dir: Directory to save the session file.

        Returns:
            Path to the saved session file.
        """
        output_dir = output_dir or Path('logs/agent_sessions')
        output_dir.mkdir(parents=True, exist_ok=True)

        session = self.get_session()
        output_path = output_dir / f'session_{self.session_id}.json'

        with open(output_path, 'w') as f:
            json.dump(
                {
                    'session_id': session.session_id,
                    'start_time': session.start_time,
                    'end_time': session.end_time,
                    'compliance_status': session.compliance_status,
                    'rule_violations': session.rule_violations,
                    'metadata': session.metadata,
                    'files_read': [
                        {
                            'file_path': fr.file_path,
                            'timestamp': fr.timestamp,
                            'line_count': fr.line_count,
                            'success': fr.success,
                            'error': fr.error,
                        }
                        for fr in session.files_read
                    ],
                    'commands_executed': [
                        {
                            'command': ce.command,
                            'timestamp': ce.timestamp,
                            'working_directory': ce.working_directory,
                            'exit_code': ce.exit_code,
                            'duration_seconds': ce.duration_seconds,
                        }
                        for ce in session.commands_executed
                    ],
                    'tools_executed': [
                        {
                            'tool_name': te.tool_name,
                            'timestamp': te.timestamp,
                            'input_data': te.input_data,
                            'output_summary': te.output_summary,
                            'success': te.success,
                            'error': te.error,
                        }
                        for te in session.tools_executed
                    ],
                },
                f,
                indent=2,
            )

        return output_path


# ============================================================================
# Session Summary Generator
# ============================================================================


def generate_session_summary(session_path: Path) -> str:
    """Generate a human-readable summary from a session file.

    Args:
        session_path: Path to the session JSON file.

    Returns:
        Formatted summary string.
    """
    with open(session_path) as f:
        session = json.load(f)

    lines = [
        '=' * 70,
        'AGENT SESSION SUMMARY',
        '=' * 70,
        f'Session ID: {session.get("session_id", "unknown")}',
        f'Start Time: {session.get("start_time", "unknown")}',
        f'End Time: {session.get("end_time", "unknown")}',
        '',
    ]

    # Files read
    files_read = session.get('files_read', [])
    if files_read:
        lines.extend(
            [
                '-' * 70,
                f'FILES READ ({len(files_read)})',
                '-' * 70,
            ]
        )
        for fr in files_read:
            status = '✅' if fr['success'] else '❌'
            lines.append(f'  {status} {fr["file_path"]}')
        lines.append('')

    # Commands executed
    commands = session.get('commands_executed', [])
    if commands:
        lines.extend(
            [
                '-' * 70,
                f'COMMANDS EXECUTED ({len(commands)})',
                '-' * 70,
            ]
        )
        for ce in commands:
            exit_str = (
                f' [exit: {ce["exit_code"]}]' if ce.get('exit_code') is not None else ''
            )
            lines.append(f'  $ {ce["command"]}{exit_str}')
        lines.append('')

    # Tools executed
    tools = session.get('tools_executed', [])
    if tools:
        lines.extend(
            [
                '-' * 70,
                f'TOOLS EXECUTED ({len(tools)})',
                '-' * 70,
            ]
        )
        for te in tools:
            status = '✅' if te['success'] else '❌'
            lines.append(f'  {status} {te["tool_name"]}')
        lines.append('')

    # Compliance status
    compliance = session.get('compliance_status')
    if compliance:
        status_icon = '✅' if compliance == 'passed' else '❌'
        violations = session.get('rule_violations', 0)
        lines.extend(
            [
                '-' * 70,
                'COMPLIANCE STATUS',
                '-' * 70,
                f'  {status_icon} {compliance} ({violations} violations)',
                '',
            ]
        )

    lines.append('=' * 70)
    return '\n'.join(lines)


def list_sessions(output_dir: Path | None = None) -> list[Path]:
    """List all session files in the output directory.

    Args:
        output_dir: Directory containing session files.

    Returns:
        List of session file paths sorted by modification time.
    """
    output_dir = output_dir or Path('logs/agent_sessions')
    if not output_dir.exists():
        return []

    sessions = list(output_dir.glob('session_*.json'))
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions


# ============================================================================
# Main
# ============================================================================


def main() -> int:
    """Generate summary from agent session logs."""
    parser = argparse.ArgumentParser(
        description='Generate summary from agent session logs'
    )
    parser.add_argument(
        '--session',
        type=Path,
        help='Path to a specific session JSON file',
    )
    parser.add_argument(
        '--latest',
        action='store_true',
        help='Show the latest session',
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all sessions',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('logs/agent_sessions'),
        help='Directory containing session files',
    )

    args = parser.parse_args()

    if args.list:
        sessions = list_sessions(args.output_dir)
        if not sessions:
            print('No sessions found.')
            return 0

        print('Available sessions:')
        for s in sessions:
            print(f'  {s.name}')
        return 0

    if args.latest:
        sessions = list_sessions(args.output_dir)
        if not sessions:
            print('No sessions found.')
            return 1
        args.session = sessions[0]

    if args.session:
        print(generate_session_summary(args.session))
        return 0

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONSOLE = PROJECT_ROOT / "wardmap"
UPDATER = PROJECT_ROOT / "ops" / "update-wardmap"


def run_console(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CONSOLE), *arguments],
        cwd="/tmp",
        check=False,
        capture_output=True,
        text=True,
    )


def test_help_works_outside_project_directory():
    result = run_console("help")

    assert result.returncode == 0
    assert "Wardmap backend console" in result.stdout
    assert "db restore <FILE> [--yes]" in result.stdout
    assert result.stderr == ""


def test_unknown_command_is_rejected_with_help():
    result = run_console("not-a-command")

    assert result.returncode == 2
    assert "unknown command: not-a-command" in result.stderr
    assert "Usage: ./wardmap <command>" in result.stderr


def test_production_updater_help_is_available_without_server_tools():
    result = subprocess.run(
        [str(UPDATER), "--help"],
        cwd="/tmp",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "update-wardmap [all|backend|frontend]" in result.stdout

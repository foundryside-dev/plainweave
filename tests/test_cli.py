from __future__ import annotations

import runpy
import subprocess
import sys

import pytest


def test_cli_main_version_outputs_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    from charter.cli import main

    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "charter 0.1.0"


def test_cli_main_help_mentions_local_core_commands(capsys: pytest.CaptureFixture[str]) -> None:
    from charter.cli import main

    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "Charter requirements and verification authority" in output
    assert "Local-core commands are available for requirements, criteria, trace, init, and" in output
    assert "diagnostics." in output
    for command in ("init", "doctor", "req", "criterion", "trace"):
        assert command in output


def test_cli_main_without_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    from charter.cli import main

    assert main([]) == 0
    output = capsys.readouterr().out
    assert "usage: charter" in output


def test_module_entrypoint_exits_with_main_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["charter", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("charter", run_name="__main__")

    assert exc_info.value.code == 0


def test_module_version_outputs_package_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "charter", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "charter 0.1.0"


def test_console_script_version_outputs_package_version() -> None:
    result = subprocess.run(
        ["charter", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "charter 0.1.0"

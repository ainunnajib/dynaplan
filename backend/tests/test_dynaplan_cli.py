import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_ROOT = REPO_ROOT / "cli"
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from dynaplan_cli.cli import main  # noqa: E402
from dynaplan_cli.client import DynaplanApiError, DynaplanClient  # noqa: E402


def test_cli_import_module_command(monkeypatch: pytest.MonkeyPatch):
    def fake_request_json(self, method, path, **kwargs):  # noqa: ANN001
        del self
        assert method == "POST"
        assert path == "/api/v1/modules/module-1/import"
        assert "files" in kwargs
        return {"rows_imported": 2, "rows_skipped": 0, "errors": []}

    monkeypatch.setattr(DynaplanClient, "request_json", fake_request_json)

    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("input.csv").write_text("row,Revenue\nR1,100\n", encoding="utf-8")
        result = runner.invoke(
            main,
            [
                "--api-key",
                "test-key",
                "import",
                "--module-id",
                "module-1",
                "--no-progress",
                "input.csv",
            ],
        )

    assert result.exit_code == 0
    assert "Import complete" in result.output
    assert "\"rows_imported\": 2" in result.output


def test_cli_export_command_writes_file(monkeypatch: pytest.MonkeyPatch):
    def fake_request_bytes(self, method, path, **kwargs):  # noqa: ANN001
        del self
        assert method == "GET"
        assert path == "/api/v1/modules/module-2/export"
        assert kwargs["params"]["format"] == "csv"
        return b"line_item,dimension_key,value\nRevenue,key,123\n"

    monkeypatch.setattr(DynaplanClient, "request_bytes", fake_request_bytes)

    runner = CliRunner()
    with runner.isolated_filesystem():
        output = Path("module.csv")
        result = runner.invoke(
            main,
            [
                "--api-key",
                "test-key",
                "export",
                "--module-id",
                "module-2",
                "--output",
                str(output),
                "--no-progress",
            ],
        )

        assert output.exists()
        assert "Revenue" in output.read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert "Export complete" in result.output


def test_cli_run_pipeline_wait_flow(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fake_request_json(self, method, path, **kwargs):  # noqa: ANN001
        del self
        del kwargs
        calls.append((method, path))
        if path.endswith("/trigger"):
            return {
                "id": "run-1",
                "pipeline_id": "pipeline-1",
                "status": "pending",
                "completed_steps": 0,
                "total_steps": 1,
            }
        if path.endswith("/execute"):
            return {
                "id": "run-1",
                "pipeline_id": "pipeline-1",
                "status": "completed",
                "completed_steps": 1,
                "total_steps": 1,
            }
        raise AssertionError("Unexpected path: %s" % path)

    monkeypatch.setattr(DynaplanClient, "request_json", fake_request_json)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--api-key",
            "test-key",
            "run-pipeline",
            "--pipeline-id",
            "pipeline-1",
            "--wait",
            "--no-progress",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        ("POST", "/api/v1/pipelines/pipeline-1/trigger"),
        ("POST", "/api/v1/pipeline-runs/run-1/execute"),
    ]
    assert "\"status\": \"completed\"" in result.output


def test_cli_batch_continue_on_error(monkeypatch: pytest.MonkeyPatch):
    def fake_request_json(self, method, path, **kwargs):  # noqa: ANN001
        del self
        del method
        del kwargs
        if path.startswith("/api/v1/modules/") and path.endswith("/import"):
            return {"rows_imported": 1, "rows_skipped": 0, "errors": []}
        if path.startswith("/api/v1/processes/"):
            raise DynaplanApiError(400, "process failed")
        raise AssertionError("Unexpected path: %s" % path)

    def fake_request_bytes(self, method, path, **kwargs):  # noqa: ANN001
        del self
        del method
        assert path.startswith("/api/v1/modules/")
        assert kwargs["params"]["format"] == "csv"
        return b"line_item,dimension_key,value\n"

    monkeypatch.setattr(DynaplanClient, "request_json", fake_request_json)
    monkeypatch.setattr(DynaplanClient, "request_bytes", fake_request_bytes)

    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("input.csv").write_text("row,Revenue\nR1,100\n", encoding="utf-8")
        Path("ops.yaml").write_text(
            "\n".join(
                [
                    "operations:",
                    "  - command: import",
                    "    module_id: module-1",
                    "    file: input.csv",
                    "  - command: run-process",
                    "    process_id: process-1",
                    "  - command: export",
                    "    module_id: module-1",
                    "    output: output.csv",
                ]
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            [
                "--api-key",
                "test-key",
                "batch",
                "--continue-on-error",
                "ops.yaml",
            ],
        )

        assert Path("output.csv").exists()

    assert result.exit_code == 0
    assert "\"status\": \"error\"" in result.output
    assert "\"command\": \"run-process\"" in result.output

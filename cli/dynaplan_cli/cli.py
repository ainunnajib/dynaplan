import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import yaml

from dynaplan_cli.client import DynaplanApiError, DynaplanClient


class _NoopProgress:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        del exc_type
        del exc
        del tb
        return False

    def update(self, steps: int = 1) -> None:
        del steps


def _progress(enabled: bool, label: str, length: int):
    if enabled:
        return click.progressbar(length=length, label=label)
    return _NoopProgress()


def _echo_json(payload: Any) -> None:
    click.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _resolve_export_format(fmt: Optional[str], output_path: Path) -> str:
    if fmt is not None:
        return fmt
    if output_path.suffix.lower() == ".xlsx":
        return "xlsx"
    return "csv"


def _content_type(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "text/csv"


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _get_client(ctx: click.Context) -> DynaplanClient:
    return ctx.obj["client"]


def _run_import_operation(
    client: DynaplanClient,
    file_path: Path,
    module_id: Optional[str],
    dimension_id: Optional[str],
    name_column: str,
    parent_column: Optional[str],
    progress: bool,
) -> Dict[str, Any]:
    if (module_id is None and dimension_id is None) or (
        module_id is not None and dimension_id is not None
    ):
        raise click.ClickException("Provide exactly one of --module-id or --dimension-id")

    if not file_path.exists():
        raise click.ClickException("File not found: %s" % file_path)

    with file_path.open("rb") as handle:
        files = {
            "file": (file_path.name, handle, _content_type(file_path)),
        }
        with _progress(progress, "Importing data", 2) as bar:
            bar.update(1)
            if module_id is not None:
                result = client.request_json(
                    "POST",
                    "/api/v1/modules/%s/import" % module_id,
                    files=files,
                )
            else:
                params = {"name_column": name_column}
                if parent_column is not None:
                    params["parent_column"] = parent_column
                result = client.request_json(
                    "POST",
                    "/api/v1/dimensions/%s/import" % dimension_id,
                    files=files,
                    params=params,
                )
            bar.update(1)
    return result


def _run_export_operation(
    client: DynaplanClient,
    module_id: str,
    output: Path,
    fmt: Optional[str],
    progress: bool,
) -> Dict[str, Any]:
    export_format = _resolve_export_format(fmt, output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with _progress(progress, "Exporting data", 2) as bar:
        payload = client.request_bytes(
            "GET",
            "/api/v1/modules/%s/export" % module_id,
            params={"format": export_format},
        )
        bar.update(1)
        output.write_bytes(payload)
        bar.update(1)

    return {
        "module_id": module_id,
        "format": export_format,
        "bytes_written": len(payload),
        "output": str(output),
    }


def _run_process_operation(
    client: DynaplanClient,
    process_id: str,
    progress: bool,
) -> Dict[str, Any]:
    with _progress(progress, "Running process", 1) as bar:
        payload = client.request_json(
            "POST",
            "/api/v1/processes/%s/run" % process_id,
        )
        bar.update(1)
    return payload


def _run_pipeline_operation(
    client: DynaplanClient,
    pipeline_id: str,
    wait: bool,
    progress: bool,
) -> Dict[str, Any]:
    if not wait:
        with _progress(progress, "Triggering pipeline", 1) as bar:
            payload = client.request_json(
                "POST",
                "/api/v1/pipelines/%s/trigger" % pipeline_id,
            )
            bar.update(1)
        return payload

    with _progress(progress, "Running pipeline", 2) as bar:
        trigger_payload = client.request_json(
            "POST",
            "/api/v1/pipelines/%s/trigger" % pipeline_id,
        )
        bar.update(1)
        run_id = trigger_payload["id"]
        payload = client.request_json(
            "POST",
            "/api/v1/pipeline-runs/%s/execute" % run_id,
        )
        bar.update(1)
    return payload


def _load_batch_operations(batch_file: Path) -> List[Dict[str, Any]]:
    suffix = batch_file.suffix.lower()
    if suffix == ".json":
        loaded = json.loads(batch_file.read_text(encoding="utf-8"))
    elif suffix in {".yaml", ".yml"}:
        loaded = yaml.safe_load(batch_file.read_text(encoding="utf-8"))
    else:
        raise click.ClickException("Batch file must be .json, .yaml, or .yml")

    operations: Any = loaded
    if isinstance(loaded, dict):
        operations = loaded.get("operations")

    if not isinstance(operations, list):
        raise click.ClickException("Batch file must contain an operation list")

    normalized: List[Dict[str, Any]] = []
    for index, raw_item in enumerate(operations):
        if not isinstance(raw_item, dict):
            raise click.ClickException("Operation %s must be an object" % (index + 1))
        normalized.append(raw_item)
    return normalized


def _resolve_batch_path(base_dir: Path, candidate: Any) -> Path:
    if not isinstance(candidate, str) or len(candidate.strip()) == 0:
        raise click.ClickException("Operation is missing a valid file path")
    path = Path(candidate)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _execute_batch_operation(
    client: DynaplanClient,
    operation: Dict[str, Any],
    batch_dir: Path,
) -> Dict[str, Any]:
    command = operation.get("command")
    if not isinstance(command, str) or len(command.strip()) == 0:
        command = operation.get("operation")
    if not isinstance(command, str) or len(command.strip()) == 0:
        command = operation.get("type")
    if not isinstance(command, str) or len(command.strip()) == 0:
        raise click.ClickException("Batch operation is missing 'command'")
    command = command.strip()

    if command == "import":
        source_file = _resolve_batch_path(batch_dir, operation.get("file"))
        return _run_import_operation(
            client=client,
            file_path=source_file,
            module_id=operation.get("module_id"),
            dimension_id=operation.get("dimension_id"),
            name_column=str(operation.get("name_column", "name")),
            parent_column=operation.get("parent_column"),
            progress=False,
        )

    if command == "export":
        module_id = operation.get("module_id")
        if not isinstance(module_id, str) or len(module_id.strip()) == 0:
            raise click.ClickException("Export operation requires 'module_id'")
        output_path = _resolve_batch_path(batch_dir, operation.get("output"))
        format_value = operation.get("format")
        if format_value is not None:
            format_value = str(format_value)
        return _run_export_operation(
            client=client,
            module_id=module_id,
            output=output_path,
            fmt=format_value,
            progress=False,
        )

    if command == "run-process":
        process_id = operation.get("process_id")
        if not isinstance(process_id, str) or len(process_id.strip()) == 0:
            raise click.ClickException("run-process operation requires 'process_id'")
        return _run_process_operation(
            client=client,
            process_id=process_id,
            progress=False,
        )

    if command == "run-pipeline":
        pipeline_id = operation.get("pipeline_id")
        if not isinstance(pipeline_id, str) or len(pipeline_id.strip()) == 0:
            raise click.ClickException("run-pipeline operation requires 'pipeline_id'")
        wait = _to_bool(operation.get("wait"), True)
        return _run_pipeline_operation(
            client=client,
            pipeline_id=pipeline_id,
            wait=wait,
            progress=False,
        )

    raise click.ClickException("Unsupported batch command: %s" % command)


def _handle_cli_error(exc: Exception) -> None:
    if isinstance(exc, DynaplanApiError):
        raise click.ClickException("API error %s: %s" % (exc.status_code, exc.message))
    if isinstance(exc, click.ClickException):
        raise exc
    raise click.ClickException(str(exc))


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--base-url",
    default="http://localhost:8000",
    show_default=True,
    envvar="DYNAPLAN_BASE_URL",
    help="Dynaplan API base URL.",
)
@click.option(
    "--api-key",
    required=True,
    envvar="DYNAPLAN_API_KEY",
    help="Dynaplan API key (or set DYNAPLAN_API_KEY).",
)
@click.option(
    "--timeout",
    default=60.0,
    show_default=True,
    type=float,
    help="HTTP timeout in seconds.",
)
@click.pass_context
def main(ctx: click.Context, base_url: str, api_key: str, timeout: float) -> None:
    """Dynaplan bulk API CLI."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = DynaplanClient(base_url=base_url, api_key=api_key, timeout=timeout)


@main.command(name="import")
@click.option("--module-id", type=str, default=None, help="Target module UUID.")
@click.option("--dimension-id", type=str, default=None, help="Target dimension UUID.")
@click.option("--name-column", type=str, default="name", show_default=True, help="Dimension name column.")
@click.option("--parent-column", type=str, default=None, help="Dimension parent column.")
@click.option("--progress/--no-progress", default=True, show_default=True, help="Show progress output.")
@click.argument("file_path", type=click.Path(path_type=Path, dir_okay=False))
@click.pass_context
def import_command(
    ctx: click.Context,
    module_id: Optional[str],
    dimension_id: Optional[str],
    name_column: str,
    parent_column: Optional[str],
    progress: bool,
    file_path: Path,
) -> None:
    """Import CSV/XLSX data into a module or dimension."""
    try:
        result = _run_import_operation(
            client=_get_client(ctx),
            file_path=file_path,
            module_id=module_id,
            dimension_id=dimension_id,
            name_column=name_column,
            parent_column=parent_column,
            progress=progress,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_cli_error(exc)
    click.echo("Import complete")
    _echo_json(result)


@main.command(name="export")
@click.option("--module-id", required=True, type=str, help="Source module UUID.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["csv", "xlsx"]),
    default=None,
    help="Export format (defaults from output extension).",
)
@click.option("--output", required=True, type=click.Path(path_type=Path, dir_okay=False), help="Output file path.")
@click.option("--progress/--no-progress", default=True, show_default=True, help="Show progress output.")
@click.pass_context
def export_command(
    ctx: click.Context,
    module_id: str,
    fmt: Optional[str],
    output: Path,
    progress: bool,
) -> None:
    """Export module data as CSV/XLSX."""
    try:
        result = _run_export_operation(
            client=_get_client(ctx),
            module_id=module_id,
            output=output,
            fmt=fmt,
            progress=progress,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_cli_error(exc)
    click.echo("Export complete")
    _echo_json(result)


@main.command(name="run-process")
@click.option("--process-id", required=True, type=str, help="Process UUID.")
@click.option("--progress/--no-progress", default=True, show_default=True, help="Show progress output.")
@click.pass_context
def run_process_command(ctx: click.Context, process_id: str, progress: bool) -> None:
    """Run a process."""
    try:
        result = _run_process_operation(
            client=_get_client(ctx),
            process_id=process_id,
            progress=progress,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_cli_error(exc)
    click.echo("Process run complete")
    _echo_json(result)


@main.command(name="run-pipeline")
@click.option("--pipeline-id", required=True, type=str, help="Pipeline UUID.")
@click.option("--wait/--no-wait", default=True, show_default=True, help="Wait for completion.")
@click.option("--progress/--no-progress", default=True, show_default=True, help="Show progress output.")
@click.pass_context
def run_pipeline_command(
    ctx: click.Context,
    pipeline_id: str,
    wait: bool,
    progress: bool,
) -> None:
    """Run a pipeline."""
    try:
        result = _run_pipeline_operation(
            client=_get_client(ctx),
            pipeline_id=pipeline_id,
            wait=wait,
            progress=progress,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_cli_error(exc)
    click.echo("Pipeline run request complete")
    _echo_json(result)


@main.command(name="batch")
@click.argument("batch_file", type=click.Path(path_type=Path, dir_okay=False, exists=True))
@click.option(
    "--continue-on-error/--fail-fast",
    default=False,
    show_default=True,
    help="Continue remaining operations when one fails.",
)
@click.pass_context
def batch_command(ctx: click.Context, batch_file: Path, continue_on_error: bool) -> None:
    """Run operations from a YAML/JSON batch file."""
    try:
        operations = _load_batch_operations(batch_file)
        client = _get_client(ctx)
        results: List[Dict[str, Any]] = []
        total = len(operations)

        with click.progressbar(length=total, label="Running batch") as bar:
            for index, operation in enumerate(operations):
                command = str(operation.get("command") or operation.get("operation") or operation.get("type") or "")
                try:
                    payload = _execute_batch_operation(client, operation, batch_file.parent.resolve())
                    results.append(
                        {
                            "index": index + 1,
                            "command": command,
                            "status": "ok",
                            "result": payload,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    if not continue_on_error:
                        _handle_cli_error(exc)
                    message = str(exc)
                    if isinstance(exc, DynaplanApiError):
                        message = "API error %s: %s" % (exc.status_code, exc.message)
                    results.append(
                        {
                            "index": index + 1,
                            "command": command,
                            "status": "error",
                            "error": message,
                        }
                    )
                bar.update(1)

        click.echo("Batch complete")
        _echo_json({"operations": results})
    except Exception as exc:  # noqa: BLE001
        _handle_cli_error(exc)


if __name__ == "__main__":
    main()

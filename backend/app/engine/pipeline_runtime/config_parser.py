import json
from typing import Any, Dict, List, Optional, Tuple


class PipelineRuntimeConfigError(ValueError):
    """Raised when a pipeline step config cannot be parsed or validated."""


def parse_step_config(raw_config: Optional[str], step_name: str) -> Dict[str, Any]:
    if raw_config is None:
        return {}

    if isinstance(raw_config, dict):
        return dict(raw_config)

    config_text = str(raw_config).strip()
    if len(config_text) == 0:
        return {}

    try:
        parsed = json.loads(config_text)
    except json.JSONDecodeError as exc:
        raise PipelineRuntimeConfigError(
            "Step '%s' has invalid JSON config: %s" % (step_name, exc.msg)
        ) from exc

    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise PipelineRuntimeConfigError(
            "Step '%s' config must be a JSON object" % step_name
        )

    return dict(parsed)


def resolve_connector_config(step_config: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    connector_type = step_config.get("connector_type") or step_config.get("type")
    if connector_type is None:
        raise PipelineRuntimeConfigError(
            "Source step requires 'connector_type' (or 'type') in config"
        )

    resolved_type = str(connector_type).strip().lower()
    if len(resolved_type) == 0:
        raise PipelineRuntimeConfigError("connector_type cannot be empty")

    resolved_config: Dict[str, Any] = {}

    nested_config = step_config.get("config")
    if isinstance(nested_config, dict):
        resolved_config.update(nested_config)

    for key, value in step_config.items():
        if key in {"connector_type", "type", "config"}:
            continue
        resolved_config[key] = value

    return resolved_type, resolved_config


def coerce_list(value: Any, field_name: str) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 0:
            return []
        return [text]
    raise PipelineRuntimeConfigError(
        "Expected '%s' to be a string or list" % field_name
    )

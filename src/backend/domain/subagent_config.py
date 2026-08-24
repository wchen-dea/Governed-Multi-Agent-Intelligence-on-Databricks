"""Define typed subagent configuration models and parsing helpers."""

import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

SubagentKind = Literal["genie", "serving_endpoint", "app", "mcp", "lakebase"]
ALLOWED_SUBAGENT_KINDS = {"genie", "serving_endpoint", "app", "mcp", "lakebase"}
SubagentAuthMode = Literal["app", "obo"]
ALLOWED_SUBAGENT_AUTH_MODES = {"app", "obo"}
DataClassification = Literal["public", "internal", "confidential", "restricted"]
ALLOWED_DATA_CLASSIFICATIONS = {"public", "internal", "confidential", "restricted"}
REQUIRED_METADATA_KEYS = {
    "data_classification",
    "owner",
    "freshness_sla",
    "allowed_personas",
    "requires_evidence",
}
DELEGATION_LIST_FIELDS = (
    "can_delegate_to",
    "accepts_delegations_from",
    "allowed_task_intents",
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubagentConfig:
    """Canonical configuration model for a single orchestrated subagent."""

    name: str
    kind: SubagentKind
    description: str
    system_prompt: str | None = None
    endpoint: str | None = None
    space_id: str | None = None
    mcp_url: str | None = None
    project_id: str | None = None
    branch_id: str | None = None
    database: str | None = None
    pg_host: str | None = None
    pg_user: str | None = None
    endpoint_id: str | None = None
    auth_mode: SubagentAuthMode = "app"
    data_classification: DataClassification = "internal"
    owner: str | None = None
    freshness_sla: str | None = None
    allowed_personas: tuple[str, ...] = ()
    requires_evidence: bool = False
    can_delegate_to: tuple[str, ...] = ()
    accepts_delegations_from: tuple[str, ...] = ()
    allowed_task_intents: tuple[str, ...] = ()
    max_delegation_depth: int = 0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Subagent name is required")
        if self.kind not in ALLOWED_SUBAGENT_KINDS:
            raise ValueError(
                f"Subagent {self.name!r} has unsupported type {self.kind!r}. "
                f"Allowed: {sorted(ALLOWED_SUBAGENT_KINDS)}"
            )
        if self.auth_mode not in ALLOWED_SUBAGENT_AUTH_MODES:
            raise ValueError(
                f"Subagent {self.name!r} has unsupported auth_mode {self.auth_mode!r}. "
                f"Allowed: {sorted(ALLOWED_SUBAGENT_AUTH_MODES)}"
            )
        if self.data_classification not in ALLOWED_DATA_CLASSIFICATIONS:
            raise ValueError(
                f"Subagent {self.name!r} has unsupported data_classification "
                f"{self.data_classification!r}. Allowed: {sorted(ALLOWED_DATA_CLASSIFICATIONS)}"
            )
        if not self.description:
            raise ValueError(f"Subagent {self.name!r} must include a description")
        if self.system_prompt is not None and not self.system_prompt.strip():
            raise ValueError(f"Subagent {self.name!r} has empty system_prompt")
        if self.kind == "genie" and not self.space_id:
            raise ValueError(f"Genie subagent {self.name!r} must define space_id")
        if self.kind == "mcp" and not self.mcp_url:
            raise ValueError(f"MCP subagent {self.name!r} must define mcp_url")
        if self.kind == "lakebase":
            if not self.project_id:
                raise ValueError(f"Lakebase subagent {self.name!r} must define project_id")
            if not self.branch_id:
                raise ValueError(f"Lakebase subagent {self.name!r} must define branch_id")
            if not self.database:
                raise ValueError(f"Lakebase subagent {self.name!r} must define database")
            if not self.pg_host:
                raise ValueError(f"Lakebase subagent {self.name!r} must define pg_host")
            if not self.endpoint_id:
                raise ValueError(f"Lakebase subagent {self.name!r} must define endpoint_id")
        if self.kind not in {"genie", "mcp", "lakebase"} and not self.endpoint:
            raise ValueError(f"Non-genie subagent {self.name!r} must define endpoint")
        if any(not persona.strip() for persona in self.allowed_personas):
            raise ValueError(f"Subagent {self.name!r} has invalid allowed_personas entry")
        for field_name in DELEGATION_LIST_FIELDS:
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"Subagent {self.name!r} has invalid {field_name} entry")
        if self.max_delegation_depth < 0:
            raise ValueError(f"Subagent {self.name!r} max_delegation_depth must not be negative")

    @property
    def is_genie(self) -> bool:
        return self.kind == "genie"

    @property
    def is_mcp(self) -> bool:
        return self.kind == "mcp"

    @property
    def is_lakebase(self) -> bool:
        return self.kind == "lakebase"

    @property
    def is_obo(self) -> bool:
        return self.auth_mode == "obo"

    @property
    def tool_name(self) -> str:
        return f"query_{self.name}"

    @property
    def model_name(self) -> str:
        if self.endpoint is None:
            raise ValueError(f"Subagent {self.name!r} has no endpoint configured")
        return f"apps/{self.endpoint}" if self.kind == "app" else self.endpoint

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SubagentConfig":
        missing_metadata = sorted(key for key in REQUIRED_METADATA_KEYS if key not in value)
        if missing_metadata:
            raise ValueError(
                f"Subagent {value.get('name', '<unknown>')!r} missing required metadata fields: "
                f"{', '.join(missing_metadata)}"
            )

        kind = value["type"]
        auth_mode = value.get("auth_mode", "obo" if kind == "genie" else "app")
        allowed_personas_raw = value.get("allowed_personas", [])
        if not isinstance(allowed_personas_raw, list) or not all(
            isinstance(item, str) for item in allowed_personas_raw
        ):
            raise ValueError(
                f"Subagent {value.get('name', '<unknown>')!r} allowed_personas must be a list of strings"
            )
        if not allowed_personas_raw:
            raise ValueError(
                f"Subagent {value.get('name', '<unknown>')!r} must define at least one allowed_personas entry"
            )
        owner = value.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError(f"Subagent {value.get('name', '<unknown>')!r} must define owner")
        freshness_sla = value.get("freshness_sla")
        if not isinstance(freshness_sla, str) or not freshness_sla.strip():
            raise ValueError(
                f"Subagent {value.get('name', '<unknown>')!r} must define freshness_sla"
            )
        try:
            delegation_values: dict[str, tuple[str, ...]] = {}
            for field_name in DELEGATION_LIST_FIELDS:
                raw_values = value.get(field_name, [])
                if not isinstance(raw_values, list) or not all(
                    isinstance(item, str) for item in raw_values
                ):
                    raise ValueError(
                        f"Subagent {value.get('name', '<unknown>')!r} "
                        f"{field_name} must be a list of strings"
                    )
                delegation_values[field_name] = tuple(raw_values)
            return cls(
                name=value["name"],
                kind=kind,
                description=value["description"],
                system_prompt=value.get("system_prompt"),
                endpoint=value.get("endpoint"),
                space_id=value.get("space_id"),
                mcp_url=value.get("mcp_url"),
                project_id=value.get("project_id"),
                branch_id=value.get("branch_id"),
                database=value.get("database"),
                pg_host=value.get("pg_host"),
                pg_user=value.get("pg_user"),
                endpoint_id=value.get("endpoint_id"),
                auth_mode=auth_mode,
                data_classification=value["data_classification"],
                owner=owner,
                freshness_sla=freshness_sla,
                allowed_personas=tuple(allowed_personas_raw),
                requires_evidence=bool(value["requires_evidence"]),
                can_delegate_to=delegation_values["can_delegate_to"],
                accepts_delegations_from=delegation_values["accepts_delegations_from"],
                allowed_task_intents=delegation_values["allowed_task_intents"],
                max_delegation_depth=int(value.get("max_delegation_depth", 0)),
            )
        except KeyError as exc:
            raise ValueError(f"Subagent config missing required key: {exc}") from exc


def parse_subagents(raw_subagents: Iterable[dict[str, Any]]) -> list[SubagentConfig]:
    """Parse and validate raw subagent dictionaries into typed models."""
    return [SubagentConfig.from_dict(value) for value in raw_subagents]


def _is_placeholder(value: Any) -> bool:
    """Return true for unresolved placeholder values like <SOME-ID>."""
    return isinstance(value, str) and value.startswith("<") and value.endswith(">")


def _is_configured_subagent(entry: dict[str, Any]) -> bool:
    """Return true when an entry is configured with concrete identifiers."""
    kind = entry.get("type")
    if kind == "genie" and _is_placeholder(entry.get("space_id")):
        return False
    if kind == "mcp" and _is_placeholder(entry.get("mcp_url")):
        return False
    if kind == "lakebase" and _is_placeholder(entry.get("project_id")):
        return False
    if kind not in {"genie", "mcp", "lakebase"} and _is_placeholder(entry.get("endpoint")):
        return False
    return True


SUBAGENTS_CONFIG_PATH_ENV = "SUBAGENTS_CONFIG_PATH"
TARGET_ENV_VARS = ("DATABRICKS_BUNDLE_TARGET", "BUNDLE_TARGET", "TARGET", "APP_ENV")
SUPPORTED_TARGETS = ("dev", "qa", "stg", "prod")
DEFAULT_TARGET_FALLBACK = "dev"


def _target_config_path(target: str) -> Path:
    """Build the expected env-specific subagent config path."""
    return Path(__file__).with_name(f"subagents.{target}.json")


def _find_supported_target_from_env() -> tuple[str, str] | None:
    """Return (env_var_name, target) for the first supported target found in env vars."""
    for env_name in TARGET_ENV_VARS:
        target = os.getenv(env_name, "").strip().lower()
        if target in SUPPORTED_TARGETS:
            return env_name, target
    return None


def _resolve_subagents_config_path(config_path: str | Path | None = None) -> Path:
    """Resolve subagent config path from explicit path, env override, or target fallback."""
    if config_path:
        return Path(config_path)

    env_path = os.getenv(SUBAGENTS_CONFIG_PATH_ENV)
    if env_path:
        return Path(env_path)

    target_selection = _find_supported_target_from_env()
    if target_selection:
        env_name, target = target_selection
        candidate = _target_config_path(target)
        if candidate.exists():
            logger.info(
                "Resolved subagent config via %s=%s -> %s",
                env_name,
                target,
                candidate,
            )
            return candidate

    default_target_path = _target_config_path(DEFAULT_TARGET_FALLBACK)
    if default_target_path.exists():
        logger.warning(
            "No %s or target env provided; defaulting to %s",
            SUBAGENTS_CONFIG_PATH_ENV,
            default_target_path,
        )
        return default_target_path

    available = [
        str(path.name)
        for path in sorted(Path(__file__).parent.glob("subagents.*.json"))
        if path.is_file()
    ]
    available_configs = ", ".join(available) if available else "<none>"
    raise ValueError(
        "Could not resolve subagent configuration file. "
        f"Set {SUBAGENTS_CONFIG_PATH_ENV} or one of {TARGET_ENV_VARS} to {', '.join(SUPPORTED_TARGETS)}. "
        f"Available env-specific config files: {available_configs}"
    )


def load_subagents(config_path: str | Path | None = None) -> list[SubagentConfig]:
    """Load and validate subagent configuration from JSON file."""
    resolved_path = _resolve_subagents_config_path(config_path)
    try:
        raw = json.loads(resolved_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Subagent configuration file not found: {resolved_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Subagent configuration file contains invalid JSON: {resolved_path}"
        ) from exc

    if not isinstance(raw, list):
        raise ValueError(f"Subagent configuration root must be a list: {resolved_path}")
    if not all(isinstance(item, dict) for item in raw):
        raise ValueError(f"Each subagent entry must be an object: {resolved_path}")

    configured_entries = [item for item in raw if _is_configured_subagent(item)]
    skipped = len(raw) - len(configured_entries)
    if skipped:
        logger.warning(
            "Skipped %s unconfigured subagent entries with placeholder identifiers from %s",
            skipped,
            resolved_path,
        )

    return parse_subagents(configured_entries)


def skipped_subagent_names(config_path: str | Path | None = None) -> list[str]:
    """Return names of subagent entries skipped for unresolved placeholder identifiers.

    Useful as a preflight check (for example before running quality evaluation)
    so operators can see which routes will never be exercised because their
    Genie space id, MCP URL, project id, or endpoint is still a placeholder.
    """
    resolved_path = _resolve_subagents_config_path(config_path)
    raw = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [
        str(item.get("name", "<unnamed>"))
        for item in raw
        if isinstance(item, dict) and not _is_configured_subagent(item)
    ]


SUBAGENTS = load_subagents()

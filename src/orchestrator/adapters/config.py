from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv(override=False)


@dataclass(frozen=True)
class AgentConfig:
    role: str = "worker"
    binary_env: str = ""
    model_env: str = ""
    provider_env: str = ""
    default_model: str = ""
    default_provider: str = ""
    capabilities: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class Settings:
    database: str = "data/orchestrator.db"
    workspace_root: str = "."
    default_executor: str = "simulated"
    kilo_model: str = "kilo/cohere/north-mini-code:free"
    hermes_model: str = ""
    hermes_provider: str = ""
    cline_model: str = "anthropic/claude-sonnet-5"
    cline_provider: str = "cline"
    max_output_bytes: int = 20000
    fallback_order: list[str] = field(
        default_factory=lambda: ["kilo", "hermes", "cline", "simulated"]
    )
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def load_settings() -> Settings:
    """Carga default.yaml + agents.yaml con override por variables MAOQ_*.

    Los ficheros YAML dejan de ser documentacion: son la fuente de verdad y el
    codigo los lee en cada ejecucion.
    """
    root = _project_root()
    default = _load_yaml(root / "config" / "default.yaml")
    agents_raw = _load_yaml(root / "config" / "agents.yaml")

    settings = Settings(
        database=os.environ.get(
            "MAOQ_DB_PATH", str(default.get("database", "data/orchestrator.db"))
        ),
        workspace_root=os.environ.get(
            "MAOQ_WORKSPACE_ROOT", str(default.get("workspace_root", "."))
        ),
        default_executor=os.environ.get(
            "MAOQ_DEFAULT_EXECUTOR", str(default.get("default_executor", "simulated"))
        ),
        kilo_model=os.environ.get(
            "MAOQ_KILO_MODEL", str(default.get("kilo_model", "kilo/cohere/north-mini-code:free"))
        ),
        hermes_model=os.environ.get(
            "MAOQ_HERMES_MODEL", str(default.get("hermes_model", ""))
        ),
        hermes_provider=os.environ.get(
            "MAOQ_HERMES_PROVIDER", str(default.get("hermes_provider", ""))
        ),
        cline_model=os.environ.get(
            "MAOQ_CLINE_MODEL", str(default.get("cline_model", "anthropic/claude-sonnet-5"))
        ),
        cline_provider=os.environ.get(
            "MAOQ_CLINE_PROVIDER", str(default.get("cline_provider", "cline"))
        ),
        max_output_bytes=int(default.get("max_output_bytes", 20000)),
        fallback_order=list(agents_raw.get("fallback_order") or default.get("fallback_order")
                            or ["kilo", "hermes", "cline", "simulated"]),
        agents=_parse_agents(agents_raw.get("agents", {})),
        raw={**default, **agents_raw},
    )
    return settings


def _parse_agents(data: dict[str, Any]) -> dict[str, AgentConfig]:
    return {
        name: AgentConfig(
            role=str(item.get("role", "worker")),
            binary_env=str(item.get("binary_env", "")),
            model_env=str(item.get("model_env", "")),
            provider_env=str(item.get("provider_env", "")),
            default_model=str(item.get("default_model", "")),
            default_provider=str(item.get("default_provider", "")),
            capabilities=list(item.get("capabilities", [])),
            notes=str(item.get("notes", "")),
        )
        for name, item in data.items()
        if isinstance(item, dict)
    }

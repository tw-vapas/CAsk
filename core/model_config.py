"""Dynamic AI Model configuration and JSON persistence.

Manages model entries, protocol definitions, presets, and migration from legacy env configs.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ModelEntry:
    """A configured AI model endpoint in the execution pipeline."""
    id: str
    name: str
    protocol: str  # 'openai_compatible' or 'gemini'
    model: str
    base_url: str = ""
    api_key: str = ""
    enabled: bool = True
    temperature: float = 0.2
    max_tokens: int = 4096

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelEntry:
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:8]),
            name=str(data.get("name", "Custom Model")),
            protocol=str(data.get("protocol", "openai_compatible")),
            model=str(data.get("model", "qwen/qwen3.8-27b")),
            base_url=str(data.get("base_url", "")),
            api_key=str(data.get("api_key", "")),
            enabled=bool(data.get("enabled", True)),
            temperature=float(data.get("temperature", 0.2)),
            max_tokens=int(data.get("max_tokens", 4096)),
        )


PRESETS: Dict[str, Dict[str, Any]] = {
    "groq": {
        "name": "Groq Cloud (LPU Instant)",
        "protocol": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "models": ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"],
    },
    "9router": {
        "name": "9Router (Local Gateway)",
        "protocol": "openai_compatible",
        "base_url": "http://localhost:20128/v1",
        "model": "claude-3-5-sonnet",
        "models": ["claude-3-5-sonnet", "gpt-4o", "deepseek-chat"],
    },
    "gemini": {
        "name": "Google Gemini",
        "protocol": "gemini",
        "base_url": "https://generativelanguage.googleapis.com",
        "model": "gemini-flash-lite-latest",
        "models": ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"],
    },
    "deepseek": {
        "name": "DeepSeek API",
        "protocol": "openai_compatible",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "ollama": {
        "name": "Ollama (Local)",
        "protocol": "openai_compatible",
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2:3b",
        "models": ["llama3.2:3b", "qwen2.5:7b", "mistral:7b"],
    },
    "custom": {
        "name": "Custom OpenAI Endpoint",
        "protocol": "openai_compatible",
        "base_url": "http://localhost:8000/v1",
        "model": "custom-model",
        "models": ["custom-model"],
    },
}


def create_entry_from_preset(preset_key: str, custom_name: Optional[str] = None) -> ModelEntry:
    """Create a new ModelEntry prefilled with template values from PRESETS."""
    data = PRESETS.get(preset_key, PRESETS["custom"])
    entry_id = f"{preset_key}_{uuid.uuid4().hex[:6]}"
    return ModelEntry(
        id=entry_id,
        name=custom_name or data["name"],
        protocol=data["protocol"],
        base_url=data.get("base_url", ""),
        model=data["model"],
        api_key="",
        enabled=True,
    )


def get_models_file_path(config_dir: Path) -> Path:
    """Return standard path to models.json."""
    return config_dir / "models.json"


def load_models_config(config_dir: Path, env_vars: Optional[Dict[str, str]] = None) -> List[ModelEntry]:
    """Load model entries from models.json, or migrate from config.env if missing."""
    file_path = get_models_file_path(config_dir)

    if file_path.is_file():
        try:
            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, list) and data:
                return [ModelEntry.from_dict(item) for item in data]
        except (json.JSONDecodeError, OSError):
            pass

    # Migration fallback: synthesize entries from legacy environment variables
    env = env_vars or {}
    models: List[ModelEntry] = []

    groq_key = env.get("GROQ_API_KEY", "")
    groq_model = env.get("GROQ_MODEL", "qwen/qwen3.8-27b")
    groq_base = env.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    models.append(
        ModelEntry(
            id="groq_default",
            name="Groq Cloud (LPU Instant)",
            protocol="openai_compatible",
            base_url=groq_base,
            model=groq_model,
            api_key=groq_key,
            enabled=bool(groq_key.strip()),
        )
    )

    gemini_key = env.get("GEMINI_API_KEY", "")
    gemini_model = env.get("GEMINI_MODEL", "gemini-flash-lite-latest")
    models.append(
        ModelEntry(
            id="gemini_default",
            name="Google Gemini",
            protocol="gemini",
            base_url="https://generativelanguage.googleapis.com",
            model=gemini_model,
            api_key=gemini_key,
            enabled=bool(gemini_key.strip()),
        )
    )

    custom_url = env.get("CUSTOM_OPENAI_BASE_URL", "http://localhost:20128/v1")
    custom_model = env.get("CUSTOM_OPENAI_MODEL", "claude-3-5-sonnet")
    custom_key = env.get("CUSTOM_OPENAI_API_KEY", "")
    models.append(
        ModelEntry(
            id="9router_default",
            name="9Router (Local Gateway)",
            protocol="openai_compatible",
            base_url=custom_url,
            model=custom_model,
            api_key=custom_key,
            enabled=False,
        )
    )

    # Respect legacy PROVIDER_ORDER if specified
    order_str = env.get("PROVIDER_ORDER", "")
    if order_str:
        order_keys = [k.strip().lower() for k in order_str.split(",") if k.strip()]
        for m in models:
            m.enabled = any(k in m.id or k in m.name.lower() for k in order_keys)

    return models


def save_models_config(models: List[ModelEntry], config_dir: Path) -> Path:
    """Atomically write model entries to models.json."""
    config_dir.mkdir(parents=True, exist_ok=True)
    file_path = get_models_file_path(config_dir)
    data = [m.to_dict() for m in models]
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    temp_path = file_path.with_suffix(".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(file_path)
    return file_path


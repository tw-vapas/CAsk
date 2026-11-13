"""Provider connections, saved model profiles, and private atomic persistence."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .model_config import ModelEntry, PRESETS


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class ModelProfile:
    id: str
    name: str
    model: str
    reasoning: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    token_parameter: str = "max_tokens"

    @classmethod
    def from_dict(cls, value):
        profile = cls(**{key: item for key, item in value.items() if key in cls.__dataclass_fields__})
        if not profile.id or not profile.name.strip() or not profile.model.strip():
            raise ValueError("Saved models require an ID, name, and model ID.")
        if profile.reasoning not in ("", "none", "low", "medium", "high", "xhigh", "max"):
            raise ValueError("Invalid reasoning effort.")
        if profile.max_tokens is not None and (type(profile.max_tokens) is not int or profile.max_tokens < 1):
            raise ValueError("Output limit must be a positive integer.")
        if profile.temperature is not None and not 0 <= profile.temperature <= 2:
            raise ValueError("Temperature must be between 0 and 2.")
        if profile.token_parameter not in ("max_tokens", "max_completion_tokens"):
            raise ValueError("Invalid Chat Completions token parameter.")
        return profile


@dataclass
class Provider:
    id: str
    name: str
    kind: str
    protocol: str
    base_url: str
    api_key: str = field(default="", repr=False)
    enabled: bool = True
    models: list[ModelProfile] = field(default_factory=list)
    active_model_id: str = ""
    catalog: list[dict] = field(default_factory=list)
    catalog_updated_at: str = ""

    @property
    def active_model(self) -> ModelProfile | None:
        return next((m for m in self.models if m.id == self.active_model_id), None)

    @property
    def authenticated(self) -> bool:
        return bool(self.api_key.strip()) or urlsplit(self.base_url).hostname in ("localhost", "127.0.0.1", "::1")

    @classmethod
    def from_dict(cls, value):
        data = {key: item for key, item in value.items() if key in cls.__dataclass_fields__}
        data["models"] = [ModelProfile.from_dict(m) for m in data.get("models", [])]
        provider = cls(**data)
        validate_provider(provider)
        return provider


def validate_provider(provider: Provider) -> None:
    if not provider.id or not provider.name.strip():
        raise ValueError("Providers require an ID and display name.")
    if type(provider.enabled) is not bool:
        raise ValueError("Provider enabled state must be a boolean.")
    if not isinstance(provider.catalog, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("id"), str)
        or not item["id"] or not isinstance(item.get("metadata", {}), dict)
        for item in provider.catalog
    ):
        raise ValueError("Invalid cached model catalog.")
    if provider.protocol not in ("openai_compatible", "openai_responses", "gemini"):
        raise ValueError("Unsupported provider protocol.")
    parsed = urlsplit(provider.base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Base URL must be an HTTP(S) URL without credentials, query, or fragment.")
    if len({m.id for m in provider.models}) != len(provider.models):
        raise ValueError("Duplicate saved model IDs.")
    for profile in provider.models:
        ModelProfile.from_dict(asdict(profile))
    if provider.models and not provider.active_model:
        raise ValueError("Choose one active model for each provider with saved models.")
    if not provider.models and provider.active_model_id:
        raise ValueError("The active model no longer exists.")


PROVIDER_PRESETS = {
    "openai": {"name": "OpenAI", "protocol": "openai_responses", "base_url": "https://api.openai.com/v1"},
    **{key: {k: v for k, v in value.items() if k in ("name", "protocol", "base_url")} for key, value in PRESETS.items()},
}


def create_provider(kind: str) -> Provider:
    return Provider(id=new_id(), kind=kind, **PROVIDER_PRESETS[kind])


def migrate_models(entries: list[ModelEntry]) -> list[Provider]:
    """Group legacy entries sharing credentials without touching their source file."""
    providers = []
    groups = {}
    for entry in entries:
        base = entry.base_url or ("https://generativelanguage.googleapis.com" if entry.protocol == "gemini" else "https://api.groq.com/openai/v1")
        identity = (entry.protocol, base.rstrip("/"), entry.api_key)
        provider = groups.get(identity)
        if provider is None:
            kind = next((k for k in PROVIDER_PRESETS if k in entry.id.lower()), "custom")
            provider = Provider(entry.id, entry.name, kind, entry.protocol, base, entry.api_key, False)
            groups[identity] = provider
            providers.append(provider)
        profile = ModelProfile(entry.id, entry.name, entry.model, temperature=entry.temperature, max_tokens=entry.max_tokens)
        provider.models.append(profile)
        if not provider.active_model_id or (entry.enabled and not provider.enabled):
            provider.active_model_id = profile.id
        provider.enabled = provider.enabled or entry.enabled
    return providers


def load_providers(config_dir: Path, legacy: list[ModelEntry]) -> tuple[list[Provider], str]:
    path = config_dir / "providers.json"
    if not path.exists():
        providers = migrate_models(legacy)
        return providers, next((p.id for p in providers if p.enabled), "")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != 1:
            raise ValueError("Unsupported providers.json version.")
        providers = [Provider.from_dict(p) for p in data["providers"]]
        primary = data.get("selected_provider_id", "")
        if len({p.id for p in providers}) != len(providers):
            raise ValueError("Duplicate provider IDs.")
        if primary and not any(p.id == primary and p.enabled for p in providers):
            raise ValueError("The selected provider must exist and be enabled.")
        return providers, primary
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Never silently reactivate old credentials when the authoritative file is invalid.
        raise ValueError("Cannot load providers.json; fix or restore the configuration file.") from exc


def save_providers(providers: list[Provider], config_dir: Path, selected_provider_id: str = "") -> Path:
    for provider in providers:
        validate_provider(provider)
    if len({p.id for p in providers}) != len(providers):
        raise ValueError("Duplicate provider IDs.")
    if selected_provider_id and not any(p.id == selected_provider_id and p.enabled for p in providers):
        raise ValueError("The selected provider must be enabled.")
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "selected_provider_id": selected_provider_id, "providers": [asdict(p) for p in providers]}
    path = config_dir / "providers.json"
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=config_dir, prefix=".providers-", delete=False) as stream:
            temp_name = stream.name
            os.fchmod(stream.fileno(), 0o600)
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return path

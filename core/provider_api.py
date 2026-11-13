"""Provider model discovery and protocol-specific text requests."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode, urlsplit

from .provider_config import ModelProfile, Provider, validate_provider


# A small verified catalog enriches discovery; unknown IDs always remain selectable.
# Source: https://developers.openai.com/api/docs/models/gpt-6.1-sol
CAPABILITIES = {
    "gpt-6.1-sol": {
        "name": "GPT-6.1 Sol", "text_output": True, "temperature": False,
        "reasoning": ["low", "medium", "high", "xhigh", "max"],
        "default_reasoning": "medium", "token_parameter": "max_completion_tokens",
    },
}


def api_root(provider: Provider) -> str:
    root = provider.base_url.rstrip("/")
    for suffix in ("/chat/completions", "/responses", "/models"):
        if root.endswith(suffix):
            root = root[:-len(suffix)]
            break
    if provider.protocol == "gemini" and not root.endswith(("/v1beta", "/v1")):
        root += "/v1beta"
    return root


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward credentials to redirected or unexpected endpoints."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(provider: Provider, path: str, payload=None, timeout=60):
    validate_provider(provider)
    headers = {"Content-Type": "application/json", "User-Agent": "CAsk/2.0"}
    if provider.api_key.strip():
        headers["x-goog-api-key" if provider.protocol == "gemini" else "Authorization"] = (
            provider.api_key.strip() if provider.protocol == "gemini" else f"Bearer {provider.api_key.strip()}"
        )
    req = urllib.request.Request(api_root(provider) + path, headers=headers,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 method="POST" if payload is not None else "GET")
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("Provider response exceeded the size limit.")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object from the provider.")
        return data
    except urllib.error.HTTPError as exc:
        message = f"HTTP {exc.code}"
        try:
            error = json.loads(exc.read(65536)).get("error", {})
            if isinstance(error, dict):
                message += ": " + str(error.get("message", "Request rejected"))
        except (ValueError, AttributeError):
            pass
        finally:
            exc.close()
        if provider.api_key:
            message = message.replace(provider.api_key, "[redacted]")
        raise ValueError(message) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError("Connection failed or timed out. Check the API URL and network.") from None


def discover_models(provider: Provider) -> list[dict]:
    """Fetch every page from the configured provider only; never contact a catalog host."""
    root_query = "/models"
    results = {}
    seen_pages = set()
    query = root_query
    for _ in range(100):
        if query in seen_pages:
            raise ValueError("The model API returned a repeated pagination cursor.")
        seen_pages.add(query)
        data = request_json(provider, query, timeout=15)
        items = data.get("models" if provider.protocol == "gemini" else "data")
        if not isinstance(items, list):
            raise ValueError("This endpoint does not return a supported model list. Enter a model ID manually.")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Invalid entry in the provider model list.")
            model_id = item.get("name" if provider.protocol == "gemini" else "id", "")
            if not isinstance(model_id, str) or not model_id:
                raise ValueError("Model list entries require a model ID.")
            model_id = model_id.removeprefix("models/") if provider.protocol == "gemini" else model_id
            metadata = dict(CAPABILITIES.get(model_id, {}))
            methods = item.get("supportedGenerationMethods", [])
            if methods:
                metadata["text_output"] = "generateContent" in methods
            results[model_id] = {
                "id": model_id, "name": item.get("displayName") or metadata.get("name", model_id),
                "metadata": metadata, "source": "provider_api",
            }
        token = data.get("nextPageToken") if provider.protocol == "gemini" else data.get("last_id") if data.get("has_more") else None
        if not token:
            if data.get("has_more"):
                raise ValueError("The model list indicates another page but has no cursor.")
            return sorted(results.values(), key=lambda item: (item["metadata"].get("text_output") is False, item["name"].lower()))
        query = root_query + "?" + urlencode({"pageToken" if provider.protocol == "gemini" else "after": token})
    raise ValueError("Too many model list pages; the previous catalog was retained.")


def default_profile(model_id: str, name="") -> ModelProfile:
    from .provider_config import new_id
    info = CAPABILITIES.get(model_id, {})
    return ModelProfile(new_id(), name or info.get("name", model_id), model_id,
                        reasoning=info.get("default_reasoning", ""),
                        token_parameter=info.get("token_parameter", "max_tokens"))


def generate_text(provider: Provider, profile: ModelProfile, system: str, user: str, history=None, timeout=60):
    """Translate a saved model profile into its provider protocol without guessing IDs."""
    info = CAPABILITIES.get(profile.model, {})
    if profile.reasoning and info.get("reasoning") and profile.reasoning not in info["reasoning"]:
        raise ValueError("This model does not support the selected reasoning effort.")
    temperature_allowed = info.get("temperature") is not False and profile.reasoning in ("", "none")
    messages = [{"role": "system", "content": system}, *(history or []), {"role": "user", "content": user}]
    if provider.protocol == "gemini":
        if profile.reasoning:
            raise ValueError("Reasoning effort is not configured for this Gemini model. Use provider defaults.")
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in messages[1:]],
            "generationConfig": {},
        }
        if profile.max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = profile.max_tokens
        if profile.temperature is not None:
            payload["generationConfig"]["temperature"] = profile.temperature
        data = request_json(provider, f"/models/{quote(profile.model, safe='-._')}:generateContent", payload, timeout)
        candidates = data.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "\n".join(p["text"] for p in parts if isinstance(p.get("text"), str) and not p.get("thought"))
    elif provider.protocol == "openai_responses":
        payload = {"model": profile.model, "instructions": system, "input": messages[1:], "store": False}
        if profile.reasoning:
            payload["reasoning"] = {"effort": profile.reasoning}
        if profile.max_tokens is not None:
            payload["max_output_tokens"] = profile.max_tokens
        if profile.temperature is not None and temperature_allowed:
            payload["temperature"] = profile.temperature
        data = request_json(provider, "/responses", payload, timeout)
        if data.get("status") in ("failed", "incomplete"):
            raise ValueError("The response did not complete. Check the output limit and model settings.")
        text = "\n".join(part["text"] for item in data.get("output", []) if item.get("type") == "message"
                         for part in item.get("content", []) if part.get("type") == "output_text" and isinstance(part.get("text"), str))
    else:
        payload = {"model": profile.model, "messages": messages}
        if profile.reasoning:
            payload["reasoning_effort"] = profile.reasoning
        if profile.max_tokens is not None:
            parameter = info.get("token_parameter", profile.token_parameter)
            payload[parameter] = profile.max_tokens
        if profile.temperature is not None and temperature_allowed:
            payload["temperature"] = profile.temperature
        data = request_json(provider, "/chat/completions", payload, timeout)
        choices = data.get("choices", [])
        text = choices[0].get("message", {}).get("content", "") if choices else ""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("No text response returned. Check model support and output settings.")
    return text.strip()

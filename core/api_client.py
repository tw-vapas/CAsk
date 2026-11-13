"""Hybrid AI API Client (Groq primary, Google Gemini fallback).

Implements fast HTTP request handling using Python standard library (urllib),
with IPv4 support, robust timeouts, and Qt worker integration.
"""

from __future__ import annotations

import json
import socket
import time
import threading
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

from .config import Config

# Force IPv4 resolution to prevent DNS/IPv6 delays on Linux/Wayland systems
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo


class APIClient:
    """Synchronous hybrid API client."""

    response_context = threading.local()

    @staticmethod
    def call_openai_compatible(
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt_content: str,
        max_tokens: int = 4096,
        history: Optional[List[Dict[str, str]]] = None,
        provider_name: str = "OpenAI",
        timeout: int = 15,
    ) -> Tuple[str, Optional[str]]:
        """Execute request to any OpenAI-compatible API endpoint (Groq, 9Router, Ollama, etc.)."""
        clean_base = (base_url or "https://api.groq.com/openai/v1").rstrip("/")
        if clean_base.endswith("/chat/completions"):
            endpoint_url = clean_base
        elif clean_base.endswith("/v1"):
            endpoint_url = f"{clean_base}/chat/completions"
        else:
            endpoint_url = f"{clean_base}/v1/chat/completions"

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt_content})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CAsk/2.0",
        }
        if api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"

        req = urllib.request.Request(
            url=endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "")
                    if content:
                        return content.strip(), None
                return "", f"Empty response received from {provider_name}."
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                err_msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            return "", f"{provider_name} HTTP Error {e.code}: {err_msg}"
        except urllib.error.URLError as e:
            return "", f"{provider_name} Connection Error: {e.reason}"
        except Exception as e:
            return "", f"{provider_name} Unexpected Error: {str(e)}"

    @classmethod
    def call_groq(
        cls,
        system_prompt: str,
        user_prompt_content: str,
        config: Config,
        history: Optional[List[Dict[str, str]]] = None,
        timeout: int = 15,
    ) -> Tuple[str, Optional[str]]:
        """Execute request to Groq Cloud API with optional conversation history."""
        if not config.groq_api_key:
            return "", "Groq API key not configured."
        return cls.call_openai_compatible(
            base_url=config.groq_base_url,
            api_key=config.groq_api_key,
            model=config.groq_model,
            system_prompt=system_prompt,
            user_prompt_content=user_prompt_content,
            max_tokens=config.max_tokens,
            history=history,
            provider_name="Groq",
            timeout=timeout,
        )

    @classmethod
    def call_custom_openai(
        cls,
        system_prompt: str,
        user_prompt_content: str,
        config: Config,
        history: Optional[List[Dict[str, str]]] = None,
        timeout: int = 15,
    ) -> Tuple[str, Optional[str]]:
        """Execute request to 9Router or custom OpenAI-compatible endpoint."""
        base_url = config.custom_openai_base_url or "http://localhost:20128/v1"
        return cls.call_openai_compatible(
            base_url=base_url,
            api_key=config.custom_openai_api_key,
            model=config.custom_openai_model or "claude-3-5-sonnet",
            system_prompt=system_prompt,
            user_prompt_content=user_prompt_content,
            max_tokens=config.max_tokens,
            history=history,
            provider_name="Custom OpenAI",
            timeout=timeout,
        )

    @staticmethod
    def call_gemini(
        system_prompt: str,
        user_prompt_content: str,
        config: Config,
        history: Optional[List[Dict[str, str]]] = None,
        timeout: int = 15,
    ) -> Tuple[str, Optional[str]]:
        """Execute request to Google Gemini API with optional conversation history."""
        if not config.gemini_api_key:
            return "", "Gemini API key not configured."

        if history:
            contents = []
            for turn in history:
                role = "user" if turn.get("role") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": turn.get("content", "")}]
                })
            contents.append({
                "role": "user",
                "parts": [{"text": user_prompt_content}]
            })
            payload = {
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": config.max_tokens,
                    "temperature": 0.2,
                },
            }
        else:
            gemini_text = f"{system_prompt}\n\nUser Query:\n{user_prompt_content}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": gemini_text}
                        ]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": config.max_tokens,
                    "temperature": 0.2,
                },
            }

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.gemini_model}:generateContent?key={config.gemini_api_key}"
        )

        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CAsk/2.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        content = parts[0].get("text", "")
                        if content:
                            return content.strip(), None
                return "", "Empty response received from Gemini."
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                err_msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            return "", f"Gemini HTTP Error {e.code}: {err_msg}"
        except urllib.error.URLError as e:
            return "", f"Gemini Connection Error: {e.reason}"
        except Exception as e:
            return "", f"Gemini Unexpected Error: {str(e)}"

    @classmethod
    def request(
        cls,
        system_prompt: str,
        user_prompt_content: str,
        config: Config,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, Optional[str]]:
        """Perform request across configured provider pipeline with automatic fallback."""
        cls.response_context.source = ""
        if config.providers is not None:
            from .provider_api import generate_text
            providers = list(config.providers)
            providers.sort(key=lambda p: p.id != config.selected_provider_id)
            errors = []
            for provider in providers:
                profile = provider.active_model
                if not provider.enabled or not profile:
                    continue
                if not provider.authenticated:
                    errors.append(f"{provider.name}: Missing API key.")
                    continue
                try:
                    content = generate_text(provider, profile, system_prompt, user_prompt_content, history)
                    cls.response_context.source = f"{provider.name} / {profile.name} ({profile.model})"
                    return content, None
                except Exception as exc:
                    message = str(exc)
                    if provider.api_key:
                        message = message.replace(provider.api_key, "[redacted]")
                    errors.append(f"{provider.name} / {profile.name}: {message}")
            return "", " | ".join(errors) or "No enabled provider has an active model. Open Settings [Ctrl+,]."
        if not config.has_any_api_key:
            return "", (
                "API Key not configured!\n\n"
                f"Please configure your AI provider in the Settings panel [Ctrl+,] or in:\n"
                f"{config.config_dir / 'config.env'}\n"
                "(See .env.example for template)"
            )

        errors: List[str] = []

        # 1. Primary path: Dynamic Model Entries (models.json)
        if config.models:
            for entry in config.models:
                if not entry.enabled:
                    continue
                is_local = "localhost" in entry.base_url or "127.0.0.1" in entry.base_url
                if not entry.api_key.strip() and not is_local:
                    continue

                if entry.protocol == "gemini":
                    test_cfg = Config(gemini_api_key=entry.api_key, gemini_model=entry.model, max_tokens=entry.max_tokens)
                    content, err = cls.call_gemini(system_prompt, user_prompt_content, test_cfg, history=history)
                else:
                    content, err = cls.call_openai_compatible(
                        base_url=entry.base_url,
                        api_key=entry.api_key,
                        model=entry.model,
                        system_prompt=system_prompt,
                        user_prompt_content=user_prompt_content,
                        max_tokens=entry.max_tokens,
                        history=history,
                        provider_name=entry.name,
                    )

                if content:
                    return content, None
                if err:
                    errors.append(f"{entry.name}: {err}")

            if errors:
                return "", " | ".join(errors)

        # 2. Fallback path: Legacy provider_order pipeline
        pipeline = config.provider_order if config.provider_order else ("groq", "gemini")

        for provider in pipeline:
            if provider == "groq" and config.groq_api_key:
                content, err = cls.call_groq(system_prompt, user_prompt_content, config, history=history)
                if content:
                    return content, None
                if err:
                    errors.append(f"Groq: {err}")
            elif provider == "gemini" and config.gemini_api_key:
                content, err = cls.call_gemini(system_prompt, user_prompt_content, config, history=history)
                if content:
                    return content, None
                if err:
                    errors.append(f"Gemini: {err}")
            elif provider == "custom_openai" and (config.custom_openai_base_url or config.custom_openai_api_key):
                content, err = cls.call_custom_openai(system_prompt, user_prompt_content, config, history=history)
                if content:
                    return content, None
                if err:
                    errors.append(f"Custom OpenAI: {err}")

        # If none succeeded, try any remaining provider that has keys configured but wasn't in pipeline
        if not errors:
            if config.groq_api_key and "groq" not in pipeline:
                content, err = cls.call_groq(system_prompt, user_prompt_content, config, history=history)
                if content:
                    return content, None
                if err:
                    errors.append(f"Groq: {err}")
            elif config.gemini_api_key and "gemini" not in pipeline:
                content, err = cls.call_gemini(system_prompt, user_prompt_content, config, history=history)
                if content:
                    return content, None
                if err:
                    errors.append(f"Gemini: {err}")

        final_err = " | ".join(errors) if errors else "No response received from any configured AI provider."
        return "", final_err

    @classmethod
    def test_provider_connection(
        cls,
        provider_type: str,
        model: str,
        api_key: str,
        base_url: str = "",
        timeout: int = 8,
    ) -> Tuple[bool, float, str]:
        """Test provider connectivity with a minimal prompt, returning (success, latency_seconds, message)."""
        t0 = time.time()
        provider_lower = provider_type.lower()
        try:
            if "gemini" in provider_lower:
                if not api_key.strip():
                    return False, 0.0, "Missing API Key"
                test_cfg = Config(gemini_api_key=api_key.strip(), gemini_model=model.strip(), max_tokens=10)
                res, err = cls.call_gemini("You are a test assistant.", "ping", test_cfg, timeout=timeout)
            else:
                target_base = (
                    base_url.strip()
                    if base_url.strip()
                    else ("https://api.groq.com/openai/v1" if "groq" in provider_lower else "http://localhost:20128/v1")
                )
                res, err = cls.call_openai_compatible(
                    base_url=target_base,
                    api_key=api_key.strip(),
                    model=model.strip(),
                    system_prompt="You are a test assistant.",
                    user_prompt_content="ping",
                    max_tokens=10,
                    provider_name=provider_type,
                    timeout=timeout,
                )

            dt = time.time() - t0
            if res:
                return True, round(dt, 2), "Connected"
            return False, round(dt, 2), err or "Empty response"
        except Exception as e:
            dt = time.time() - t0
            return False, round(dt, 2), str(e)


# Optional PyQt6 worker thread integration
try:
    import threading
    from PyQt6.QtCore import QObject, pyqtSignal

    class APIWorker(QObject):
        """Asynchronous QObject worker with a daemon thread for non-blocking API calls."""

        finished = pyqtSignal(str)
        error = pyqtSignal(str)

        def __init__(
            self,
            system_prompt: str,
            user_prompt_content: str,
            config: Config,
            history: Optional[List[Dict[str, str]]] = None,
            parent=None,
        ) -> None:
            super().__init__(parent)
            self.system_prompt = system_prompt
            self.user_prompt_content = user_prompt_content
            self.config = config
            self.history = history
            self._is_cancelled: bool = False
            self._thread: Optional[threading.Thread] = None
            self.response_source = ""

        def start(self) -> None:
            """Start background API request on a daemon thread."""
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

        def isRunning(self) -> bool:
            """Return True if background thread is still executing."""
            return self._thread is not None and self._thread.is_alive()

        def cancel(self) -> None:
            """Flag worker as cancelled to suppress further signal emissions."""
            self._is_cancelled = True

        def quit(self) -> None:
            """Compatibility method matching QThread interface."""
            self.cancel()

        def wait(self, timeout_ms: int = 0) -> bool:
            """Wait for worker thread termination."""
            if self._thread and self._thread.is_alive():
                timeout_s = (timeout_ms / 1000.0) if timeout_ms > 0 else None
                self._thread.join(timeout=timeout_s)
                return not self._thread.is_alive()
            return True

        def _run(self) -> None:
            content, err = APIClient.request(
                self.system_prompt,
                self.user_prompt_content,
                self.config,
                history=self.history,
            )
            self.response_source = getattr(APIClient.response_context, "source", "")
            if self._is_cancelled:
                return

            try:
                if content:
                    self.finished.emit(content)
                else:
                    self.error.emit(err or "Unknown error occurred.")
            except (RuntimeError, Exception):
                pass

except ImportError:
    class APIWorker:  # type: ignore[no-redef]
        """Fallback placeholder when PyQt6 is not yet loaded."""
        pass

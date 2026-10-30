"""Hybrid AI API Client (Groq primary, Google Gemini fallback).

Implements fast HTTP request handling using Python standard library (urllib),
with IPv4 support, robust timeouts, and Qt worker integration.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Optional, Tuple

from .config import Config

# Force IPv4 resolution to prevent DNS/IPv6 delays on Linux/Wayland systems
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo


class APIClient:
    """Synchronous hybrid API client."""

    @staticmethod
    def call_groq(
        system_prompt: str,
        user_prompt_content: str,
        config: Config,
    ) -> Tuple[str, Optional[str]]:
        """Execute request to Groq Cloud API."""
        if not config.groq_api_key:
            return "", "Groq API key not configured."

        payload = {
            "model": config.groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt_content},
            ],
            "temperature": 0.2,
            "max_tokens": config.max_tokens,
        }

        req = urllib.request.Request(
            url="https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.groq_api_key}",
                "User-Agent": "CAsk/2.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "")
                    if content:
                        return content.strip(), None
                return "", "Empty response received from Groq."
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                err_msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            return "", f"Groq HTTP Error {e.code}: {err_msg}"
        except urllib.error.URLError as e:
            return "", f"Groq Connection Error: {e.reason}"
        except Exception as e:
            return "", f"Groq Unexpected Error: {str(e)}"

    @staticmethod
    def call_gemini(
        system_prompt: str,
        user_prompt_content: str,
        config: Config,
    ) -> Tuple[str, Optional[str]]:
        """Execute request to Google Gemini API."""
        if not config.gemini_api_key:
            return "", "Gemini API key not configured."

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
            with urllib.request.urlopen(req, timeout=45) as resp:
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
    ) -> Tuple[str, Optional[str]]:
        """Perform hybrid request: Groq primary with Gemini fallback."""
        if not config.has_any_api_key:
            return "", (
                "API Key not configured!\n\n"
                f"Please configure GROQ_API_KEY or GEMINI_API_KEY in:\n"
                f"{config.config_dir / 'config.env'}\n"
                "(See .env.example for template)"
            )

        last_error = ""

        # 1. Try Primary: Groq API
        if config.groq_api_key:
            content, err = cls.call_groq(system_prompt, user_prompt_content, config)
            if content:
                return content, None
            if err:
                last_error = err

        # 2. Try Fallback: Gemini API
        if config.gemini_api_key:
            content, err = cls.call_gemini(system_prompt, user_prompt_content, config)
            if content:
                return content, None
            if err:
                last_error = err

        final_err = last_error or "No response received from AI API (timeout or unstable network)."
        return "", final_err


# Optional PyQt6 worker thread integration
try:
    from PyQt6.QtCore import QThread, pyqtSignal

    class APIWorker(QThread):
        """Asynchronous QThread worker for non-blocking API calls."""

        finished = pyqtSignal(str)
        error = pyqtSignal(str)

        def __init__(
            self,
            system_prompt: str,
            user_prompt_content: str,
            config: Config,
            parent=None,
        ) -> None:
            super().__init__(parent)
            self.system_prompt = system_prompt
            self.user_prompt_content = user_prompt_content
            self.config = config

        def run(self) -> None:
            content, err = APIClient.request(
                self.system_prompt,
                self.user_prompt_content,
                self.config,
            )
            if content:
                self.finished.emit(content)
            else:
                self.error.emit(err or "Unknown error occurred.")

except ImportError:
    class APIWorker:  # type: ignore[no-redef]
        """Fallback placeholder when PyQt6 is not yet loaded."""
        pass

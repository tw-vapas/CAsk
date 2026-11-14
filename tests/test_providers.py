"""Provider migration, discovery, request compatibility, and Qt workflow tests."""

import copy
import json
import os
import tempfile
import threading
import time
import unittest
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QRadioButton

from core.api_client import APIClient
from core.command_loader import CommandCatalog
from core.config import Config, load_config
from core.model_config import ModelEntry
from core.provider_api import default_profile, discover_models, generate_text
from core.provider_config import ModelProfile, Provider, load_providers, migrate_models, save_providers
from ui.capsule import CAskCapsule
from ui.input_bar import InputBar
from ui.provider_settings import ModelEditor, ProviderCard, SettingsView


def provider_fixture():
    model = default_profile("gpt-6.1-sol", "Sol Medium")
    model.max_tokens = 4096
    return Provider("openai-test", "OpenAI Test", "openai", "openai_responses", "https://api.openai.com/v1", "test-key", models=[model], active_model_id=model.id)


class ProviderCoreTests(unittest.TestCase):
    def test_migration_groups_credentials_and_preserves_variants(self):
        entries = [ModelEntry("first", "First", "openai_compatible", "model-a", "http://localhost:8000/v1", enabled=False),
                   ModelEntry("second", "Second", "openai_compatible", "model-b", "http://localhost:8000/v1", enabled=True)]
        result = migrate_models(entries)
        self.assertEqual(len(result), 1)
        self.assertEqual([m.model for m in result[0].models], ["model-a", "model-b"])
        self.assertEqual(result[0].active_model_id, "second")
        self.assertTrue(result[0].enabled)

    def test_private_persistence_and_authoritative_empty_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = provider_fixture()
            path = save_providers([provider], root, provider.id)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            loaded, selected = load_providers(root, [])
            self.assertEqual(asdict(loaded[0]), asdict(provider))
            self.assertEqual(selected, provider.id)
            save_providers([], root)
            loaded, _ = load_providers(root, [ModelEntry("old", "Old", "gemini", "old", api_key="old-key")])
            self.assertEqual(loaded, [])
            config = Config(providers=(), groq_api_key="old-key")
            self.assertFalse(config.has_any_api_key)
            with patch("core.provider_api.generate_text") as generate:
                content, error = APIClient.request("s", "u", config)
                self.assertFalse(content)
                self.assertIn("No enabled provider", error)
                generate.assert_not_called()
            path.write_text('{"version": 999}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Cannot load"):
                load_providers(root, [])

    def test_failed_save_keeps_last_valid_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = provider_fixture()
            path = save_providers([provider], root, provider.id)
            before = path.read_bytes()
            provider.active_model_id = "missing"
            with self.assertRaises(ValueError):
                save_providers([provider], root, provider.id)
            self.assertEqual(path.read_bytes(), before)

    def test_clean_install_and_environment_migration_use_resolved_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("core.config.resolve_config_dir", return_value=root), patch.dict(os.environ, {"GROQ_API_KEY": "env-test-key", "PROVIDER_ORDER": "groq,gemini"}):
                config = load_config(script_dir=root)
            self.assertEqual(config.providers[0].api_key, "env-test-key")
            self.assertTrue(config.providers[0].active_model.model)
            save_providers(list(config.providers), root, config.selected_provider_id)

    def test_legacy_environment_priority_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("core.config.resolve_config_dir", return_value=root), patch.dict(os.environ, {"PROVIDER_ORDER": "gemini,groq"}):
                config = load_config(script_dir=root)
            self.assertEqual(config.providers[0].id, "gemini_default")
            self.assertEqual(config.selected_provider_id, "gemini_default")

    def test_discovery_pagination_deduplication_and_unknown_models(self):
        provider = provider_fixture()
        responses = [{"data": [{"id": "new-unknown"}, {"id": "gpt-6.1-sol"}], "has_more": True, "last_id": "cursor"},
                     {"data": [{"id": "gpt-6.1-sol"}]}]
        with patch("core.provider_api.request_json", side_effect=responses) as request:
            models = discover_models(provider)
        self.assertEqual(len(models), 2)
        self.assertEqual(request.call_args_list[1].args[1], "/models?after=cursor")
        self.assertEqual(next(m for m in models if m["id"] == "new-unknown")["metadata"], {})
        with patch("core.provider_api.request_json", return_value={"data": [], "has_more": True, "last_id": "same"}):
            with self.assertRaisesRegex(ValueError, "repeated"):
                discover_models(provider)

    def test_gemini_discovery_uses_generation_methods_and_pages(self):
        provider = replace(provider_fixture(), protocol="gemini", base_url="https://generativelanguage.googleapis.com")
        with patch("core.provider_api.request_json", side_effect=[
            {"models": [{"name": "models/embed", "supportedGenerationMethods": ["embedContent"]}], "nextPageToken": "page two"},
            {"models": [{"name": "models/chat", "supportedGenerationMethods": ["generateContent"]}]},
        ]) as request:
            models = discover_models(provider)
        self.assertEqual(models[0]["id"], "chat")
        self.assertFalse(models[1]["metadata"]["text_output"])
        self.assertEqual(request.call_args_list[1].args[1], "/models?pageToken=page+two")

    def test_responses_sol_medium_preserves_history_and_omits_temperature(self):
        provider = provider_fixture()
        profile = provider.active_model
        profile.temperature = 0.2
        with patch("core.provider_api.request_json", return_value={"status": "completed", "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": "One"}, {"type": "output_text", "text": "Two"}]},
        ]}) as request:
            text = generate_text(provider, profile, "system", "question", [{"role": "assistant", "content": "prior"}])
        payload = request.call_args.args[2]
        self.assertEqual(text, "One\nTwo")
        self.assertEqual(payload["reasoning"], {"effort": "medium"})
        self.assertEqual(payload["input"][0]["content"], "prior")
        self.assertEqual(payload["max_output_tokens"], 4096)
        self.assertNotIn("temperature", payload)
        self.assertNotIn("max_tokens", payload)

    def test_chat_sol_and_unknown_model_parameter_handling(self):
        provider = replace(provider_fixture(), protocol="openai_compatible")
        response = {"choices": [{"message": {"content": "answer"}}]}
        with patch("core.provider_api.request_json", return_value=response) as request:
            generate_text(provider, provider.active_model, "s", "u")
        payload = request.call_args.args[2]
        self.assertEqual(payload["max_completion_tokens"], 4096)
        self.assertEqual(payload["reasoning_effort"], "medium")
        with patch("core.provider_api.request_json", return_value=response) as request:
            generate_text(provider, default_profile("brand-new"), "s", "u")
        self.assertEqual(set(request.call_args.args[2]), {"model", "messages"})

    def test_only_active_model_runs_and_provider_fallback_reports_source(self):
        primary = provider_fixture()
        primary.models.append(replace(primary.active_model, id="unused", name="Do not run"))
        fallback = replace(copy.deepcopy(primary), id="fallback", name="Fallback")
        config = Config(providers=(primary, fallback), selected_provider_id=primary.id)
        with patch("core.provider_api.generate_text", side_effect=[ValueError("rate limited"), "Fallback answer"]) as request:
            content, error = APIClient.request("system", "user", config)
        self.assertEqual(content, "Fallback answer")
        self.assertIsNone(error)
        self.assertEqual(request.call_count, 2)
        self.assertTrue(all(c.args[1].id == primary.active_model_id for c in request.call_args_list))
        self.assertIn("Fallback /", APIClient.response_context.source)

    def test_partial_response_is_not_accepted_as_success(self):
        provider = provider_fixture()
        with patch("core.provider_api.request_json", return_value={"status": "incomplete", "output": []}):
            with self.assertRaisesRegex(ValueError, "did not complete"):
                generate_text(provider, provider.active_model, "s", "u")


class LocalProviderTests(unittest.TestCase):
    """Exercise real urllib requests against a local fake provider, never a paid API."""

    def test_discovery_generation_headers_and_redirect_rejection(self):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                calls.append((self.path, dict(self.headers), None))
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", "/v1/models")
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"data":[{"id":"gpt-6.1-sol"}]}')

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, dict(self.headers), body))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"Local answer"}]}]}')

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            provider = replace(provider_fixture(), base_url=base + "/v1")
            self.assertEqual(discover_models(provider)[0]["id"], "gpt-6.1-sol")
            self.assertEqual(generate_text(provider, provider.active_model, "s", "u"), "Local answer")
            self.assertEqual(calls[0][1]["Authorization"], "Bearer test-key")
            self.assertEqual(calls[1][0], "/v1/responses")
            self.assertNotIn("temperature", calls[1][2])
            redirected = replace(provider, base_url=base + "/redirect")
            with self.assertRaisesRegex(ValueError, "302"):
                discover_models(redirected)
            self.assertEqual(len(calls), 3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class ProviderUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_until(self, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            QTest.qWait(5)
        self.assertTrue(condition())

    def test_draft_apply_cancel_cache_preservation_and_reload(self):
        provider = provider_fixture()
        provider.catalog = [{"id": "cached-model", "name": "Cached", "metadata": {}}]
        with tempfile.TemporaryDirectory() as directory:
            config = Config(config_dir=Path(directory), providers=(provider,), selected_provider_id=provider.id)
            view = SettingsView(config)
            self.addCleanup(view.deleteLater)
            card = view.cards[0]
            card._duplicate(card.provider.active_model)
            self.assertEqual(len(provider.models), 1)
            with patch("ui.provider_settings.discover_models", side_effect=ValueError("offline")):
                card.refresh_catalog()
                self.wait_until(lambda: not card._busy)
            self.assertEqual(card.provider.catalog[0]["id"], "cached-model")
            self.assertFalse((Path(directory) / "providers.json").exists())
            saved = []
            view.saved.connect(saved.append)
            view._handle_save()
            self.assertEqual(len(saved), 1)
            loaded, _ = load_providers(Path(directory), [])
            self.assertEqual(len(loaded[0].models), 2)
            self.assertEqual(loaded[0].catalog[0]["id"], "cached-model")
            with patch("core.config.resolve_config_dir", return_value=Path(directory)):
                reloaded = load_config(script_dir=Path(directory))
            self.assertEqual(reloaded.providers[0].active_model_id, provider.active_model_id)

    def test_catalog_result_is_discarded_after_credentials_change(self):
        card = ProviderCard(provider_fixture())
        self.addCleanup(card.deleteLater)
        release = threading.Event()
        self.addCleanup(release.set)

        def delayed(provider):
            release.wait(2)
            return [{"id": "stale", "metadata": {}}]

        with patch("ui.provider_settings.discover_models", side_effect=delayed):
            card.refresh_catalog()
            worker = card._thread
            card.key_input.setText("new-key")
            card._connection_changed()
            release.set()
            worker.join(2)
            self.app.processEvents()
        self.assertEqual(card.provider.catalog, [])
        self.assertEqual(card.provider.api_key, "new-key")

    def test_model_editor_catalog_manual_entry_and_parameters(self):
        provider = provider_fixture()
        provider.catalog = [{"id": "gpt-6.1-sol", "metadata": {}}]
        dialog = ModelEditor(provider)
        self.addCleanup(dialog.deleteLater)
        dialog.catalog_list.setCurrentRow(0)
        self.assertEqual(dialog.model_id.text(), "gpt-6.1-sol")
        self.assertEqual(dialog.reasoning.currentData(), "medium")
        self.assertFalse(dialog.temperature.isEnabled())
        dialog.name.setText("Sol Medium")
        dialog.accept()
        self.assertIsNotNone(dialog.result_profile)
        self.assertEqual(dialog.result_profile.reasoning, "medium")
        manual = ModelEditor(provider)
        self.addCleanup(manual.deleteLater)
        manual.model_id.setText("private-alias")
        manual.accept()
        self.assertEqual(manual.result_profile.model, "private-alias")
        self.assertIsNone(manual.result_profile.temperature)

    def test_quick_switch_persists_without_changing_text_and_updates_other_capsules(self):
        from ui.main_window import MainWindow
        provider = provider_fixture()
        alternate = replace(provider.active_model, id="high-profile", name="Sol High", reasoning="high")
        provider.models.append(alternate)
        with tempfile.TemporaryDirectory() as directory:
            config = Config(config_dir=Path(directory), providers=(provider,), selected_provider_id=provider.id)
            window = MainWindow(config, CommandCatalog({}))
            self.addCleanup(window.deleteLater)
            first = window.primary_capsule
            first.input_bar.setText("Keep this question")
            first._handle_model_selection(provider.id, alternate.id)
            self.assertEqual(first.input_bar.text(), "Keep this question")
            self.assertEqual(first.config.providers[0].active_model_id, alternate.id)
            self.assertEqual(window.config.providers[0].active_model_id, alternate.id)
            loaded, selected = load_providers(Path(directory), [])
            self.assertEqual(loaded[0].active_model_id, alternate.id)
            self.assertEqual(selected, provider.id)
            self.assertIn("Sol High", first.input_bar.model_btn.text())

    def test_model_test_error_reenables_controls(self):
        card = ProviderCard(provider_fixture())
        self.addCleanup(card.deleteLater)
        with patch("ui.provider_settings.generate_text", side_effect=TimeoutError("timeout")):
            card.test_model(card.provider.active_model)
            self.wait_until(lambda: not card._busy)
        self.assertTrue(card.connect_btn.isEnabled())
        self.assertIn("timeout", card.test_result.text())

    def test_stale_draft_does_not_overwrite_quick_selection_from_another_card(self):
        provider = provider_fixture()
        with tempfile.TemporaryDirectory() as directory:
            capsule = CAskCapsule(Config(config_dir=Path(directory), providers=(provider,)), CommandCatalog({}))
            self.addCleanup(capsule.deleteLater)
            settings = capsule.settings_view
            capsule.config = replace(capsule.config, selected_provider_id=provider.id)
            settings._handle_save()
            self.assertIn("changed in another card", settings.footer_status.text())
            self.assertFalse((Path(directory) / "providers.json").exists())

    def test_connect_add_apply_and_query_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config(config_dir=Path(directory), providers=())
            settings = SettingsView(config)
            self.addCleanup(settings.deleteLater)
            settings.preset_combo.setCurrentIndex(settings.preset_combo.findData("openai"))
            settings.add_card_btn.click()
            card = settings.cards[0]
            card.key_input.setText("workflow-key")
            card._connection_changed()
            catalog = [{"id": "gpt-6.1-sol", "name": "GPT-6.1 Sol", "metadata": {"text_output": True}}]
            with patch("ui.provider_settings.discover_models", return_value=catalog):
                card.connect_btn.click()
                self.wait_until(lambda: not card._busy)
            self.assertIn("Connected", card.connection_status.text())

            card.add_model()
            editor = settings.editor
            self.assertIsNone(self.app.activeModalWidget())
            editor.catalog_list.setCurrentRow(0)
            editor.continue_btn.click()
            editor.name.setText("Sol Medium")
            editor.save_btn.click()
            self.assertEqual(len(card.provider.models), 1)
            saved = []
            settings.saved.connect(saved.append)
            settings.save_btn.click()
            self.assertEqual(len(saved), 1)
            capsule = CAskCapsule(saved[0], CommandCatalog({}))
            self.addCleanup(capsule.deleteLater)
            with patch("core.provider_api.generate_text", return_value="Workflow answer") as generate:
                capsule._handle_submit("Hello")
                self.wait_until(lambda: capsule.state == CAskCapsule.STATE_RESULT)
            self.assertIn("Workflow answer", capsule.result_view._raw_content)
            self.assertIn("Sol Medium", capsule.result_view.badge_label.text())
            self.assertEqual(generate.call_args.args[1].reasoning, "medium")

    def test_embedded_selectors_do_not_overlap_typing_or_change_enter_behavior(self):
        bar = InputBar()
        self.addCleanup(bar.deleteLater)
        provider = provider_fixture()
        bar.resize(600, 96)
        bar.set_provider_config(Config(providers=(provider,), selected_provider_id=provider.id))
        bar.show()
        self.app.processEvents()
        self.assertLess(bar.viewport().geometry().bottom(), bar.provider_btn.y())
        self.assertLess(bar.provider_btn.geometry().right(), bar.model_btn.x())
        self.assertLess(bar.model_btn.geometry().right(), bar.settings_btn.x())
        submitted = []
        bar.submitted.connect(submitted.append)
        bar.setText("Test question")
        QTest.keyClick(bar, Qt.Key.Key_Return)
        self.assertEqual(submitted, ["Test question"])
        bar.close()


if __name__ == "__main__":
    unittest.main()

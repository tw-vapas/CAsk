"""Unit tests for Ctrans Core engine."""

import unittest
from pathlib import Path
from core.config import Config, load_config, parse_env_file
from core.command_loader import load_commands, CommandCatalog, CommandMetadata
from core.router import RouteType, route_input


class TestCoreConfig(unittest.TestCase):
    def test_load_config_defaults(self):
        script_dir = Path(__file__).resolve().parent.parent
        config = load_config(script_dir=script_dir)
        self.assertIsInstance(config, Config)
        self.assertEqual(config.groq_model, "openai/gpt-oss-120b")
        self.assertEqual(config.gemini_model, "gemini-3.5-flash-lite")
        self.assertTrue(config.default_execution_dir.is_dir())
        self.assertTrue(config.default_commands_dir.is_dir())


class TestCoreCommandLoader(unittest.TestCase):
    def setUp(self):
        self.script_dir = Path(__file__).resolve().parent.parent
        self.config = load_config(script_dir=self.script_dir)
        self.catalog = load_commands(self.config)

    def test_catalog_loads_known_commands(self):
        names = self.catalog.list_names()
        self.assertIn("ask", names)
        self.assertIn("eva", names)
        self.assertNotIn("guide", names)
        self.assertNotIn("readme", names)
        self.assertNotIn("default", names)

    def test_ask_command_metadata(self):
        ask = self.catalog.get("ask")
        self.assertIsNotNone(ask)
        self.assertEqual(ask.name, "ask")
        self.assertEqual(ask.signature, "/ask <topic>")
        self.assertIn("Bilingual concept explanation", ask.description)
        self.assertEqual(ask.example, "/ask Quantum computing")
        self.assertIn("Output Structure:", ask.prompt)

    def test_help_text_generation(self):
        help_text = self.catalog.generate_help_text()
        self.assertIn("Ctrans Quick AI Assistant", help_text)
        self.assertIn("• /help", help_text)
        self.assertIn("• /ask <topic>", help_text)
        self.assertIn("• /eva <sentence>", help_text)
        self.assertNotIn("• /default", help_text)


class TestCoreRouter(unittest.TestCase):
    def setUp(self):
        self.script_dir = Path(__file__).resolve().parent.parent
        self.config = load_config(script_dir=self.script_dir)
        self.catalog = load_commands(self.config)

    def test_empty_input(self):
        res = route_input("", self.catalog, self.config)
        self.assertEqual(res.route_type, RouteType.EMPTY)

        res = route_input("   ", self.catalog, self.config)
        self.assertEqual(res.route_type, RouteType.EMPTY)

    def test_help_routing(self):
        for inp in ["/", "/help", "/help me"]:
            res = route_input(inp, self.catalog, self.config)
            self.assertEqual(res.route_type, RouteType.HELP, f"Failed on {inp}")
            self.assertIn("Ctrans Quick AI Assistant", res.display_text)

    def test_valid_command(self):
        res = route_input("/ask What is entropy?", self.catalog, self.config)
        self.assertEqual(res.route_type, RouteType.COMMAND)
        self.assertEqual(res.command, "ask")
        self.assertEqual(res.payload, "What is entropy?")
        self.assertEqual(res.user_prompt_content, "What is entropy?")
        self.assertEqual(res.loading_label, "processing /ask...")
        self.assertIn("Output Structure:", res.system_prompt)

    def test_missing_argument(self):
        res = route_input("/ask", self.catalog, self.config)
        self.assertEqual(res.route_type, RouteType.MISSING_ARG)
        self.assertIn("Missing argument for /ask", res.display_text)
        self.assertIn("/ask <topic>", res.display_text)

        res = route_input("/ask   ", self.catalog, self.config)
        self.assertEqual(res.route_type, RouteType.MISSING_ARG)

    def test_unknown_command(self):
        res = route_input("/nonexistent hello", self.catalog, self.config)
        self.assertEqual(res.route_type, RouteType.UNKNOWN_COMMAND)
        self.assertIn("Unknown Command: /nonexistent", res.display_text)
        self.assertIn("Available Commands:", res.display_text)

    def test_path_collision_avoidance(self):
        # Linux paths like /etc/hosts or /var/log should fall back to default assistant
        for path_input in ["/etc/hosts", "/var/log/syslog", "/usr/bin/bash"]:
            res = route_input(path_input, self.catalog, self.config)
            self.assertEqual(res.route_type, RouteType.DEFAULT, f"Failed on {path_input}")
            self.assertEqual(res.payload, path_input)
            self.assertEqual(res.user_prompt_content, path_input)
            self.assertEqual(res.loading_label, "Thinking...")

    def test_standard_default_routing(self):
        res = route_input("Hello world", self.catalog, self.config)
        self.assertEqual(res.route_type, RouteType.DEFAULT)
        self.assertEqual(res.payload, "Hello world")
        self.assertEqual(res.user_prompt_content, "Hello world")
        self.assertEqual(res.loading_label, "Thinking...")
        self.assertIn("Default AI Assistant Prompt", res.system_prompt)


if __name__ == "__main__":
    unittest.main()

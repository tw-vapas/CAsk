"""Unit tests for CAsk Core engine."""

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
        self.assertEqual(config.max_tokens, 4096)
        self.assertEqual(config.max_followup_turns, 3)
        self.assertTrue(config.default_execution_dir.is_dir())
        self.assertTrue(config.default_commands_dir.is_dir())

    def test_max_followup_turns_clamping(self):
        import os
        from unittest.mock import patch
        script_dir = Path(__file__).resolve().parent.parent

        with patch.dict(os.environ, {"MAX_FOLLOWUP_TURNS": "5"}):
            cfg = load_config(script_dir=script_dir)
            self.assertEqual(cfg.max_followup_turns, 5)

        with patch.dict(os.environ, {"MAX_FOLLOWUP_TURNS": "999"}):
            cfg = load_config(script_dir=script_dir)
            self.assertEqual(cfg.max_followup_turns, 10)

        with patch.dict(os.environ, {"MAX_FOLLOWUP_TURNS": "-5"}):
            cfg = load_config(script_dir=script_dir)
            self.assertEqual(cfg.max_followup_turns, 1)

        with patch.dict(os.environ, {"MAX_FOLLOWUP_TURNS": "invalid"}):
            cfg = load_config(script_dir=script_dir)
            self.assertEqual(cfg.max_followup_turns, 3)

    def test_placeholder_key_detection(self):
        from core.config import is_placeholder_key

        self.assertTrue(is_placeholder_key(""))
        self.assertTrue(is_placeholder_key("   "))
        self.assertTrue(is_placeholder_key("your_groq_api_key_here"))
        self.assertTrue(is_placeholder_key('"your_gemini_api_key_here"'))
        self.assertTrue(is_placeholder_key("'your_api_key_here'"))
        self.assertTrue(is_placeholder_key("gsk_your_groq_api_key_here"))
        self.assertFalse(is_placeholder_key("gsk_actualRealKey1234567890abcdef"))
        self.assertFalse(is_placeholder_key("AIzaSyActualRealGeminiKey123456"))


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
        self.assertIn("Concept explanation", ask.description)
        self.assertEqual(ask.example, "/ask Quantum computing")
        self.assertIn("Output Structure:", ask.prompt)

    def test_help_text_generation(self):
        help_text = self.catalog.generate_help_text()
        self.assertIn("CAsk - Available Commands", help_text)
        self.assertIn("/help", help_text)
        self.assertIn("/ask &lt;topic&gt;", help_text)
        self.assertIn("/eva &lt;sentence&gt;", help_text)
        self.assertNotIn("/default", help_text)
        self.assertIn("Keyboard Shortcuts", help_text)
        self.assertIn("Alt + ← / →", help_text)
        self.assertIn("Alt + H", help_text)
        self.assertIn("Shift + P", help_text)


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
            self.assertIn("Available Commands", res.display_text)

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
        self.assertIn("Missing argument for", res.display_text)
        self.assertIn("/ask", res.display_text)
        self.assertIn("/ask <topic>", res.display_text)

        res = route_input("/ask   ", self.catalog, self.config)
        self.assertEqual(res.route_type, RouteType.MISSING_ARG)

    def test_unknown_command(self):
        res = route_input("/nonexistent hello", self.catalog, self.config)
        self.assertEqual(res.route_type, RouteType.UNKNOWN_COMMAND)
        self.assertIn("Unknown Command: /nonexistent", res.display_text)
        self.assertIn("Available Commands", res.display_text)

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


class TestMathFormatter(unittest.TestCase):
    def test_formula_conversions(self):
        from core.math_formatter import format_math_expression

        # Quadratic formula
        res = format_math_expression(r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}")
        self.assertIn("±", res)
        self.assertIn("√", res)
        self.assertIn("b²", res)

        # Physics & Greeks
        res_e = format_math_expression(r"E = mc^2")
        self.assertEqual(res_e, "E = mc²")

        res_circle = format_math_expression(r"S = \pi r^2")
        self.assertEqual(res_circle, "S = π r²")

        res_disc = format_math_expression(r"\Delta = b^2 - 4ac")
        self.assertEqual(res_disc, "Δ = b² - 4ac")

    def test_markdown_math_processing(self):
        from core.math_formatter import format_math_in_markdown

        doc = "Equation: $E = mc^2$\n\n$$\\Delta = b^2 - 4ac$$\n\nCost is $50."
        processed = format_math_in_markdown(doc)
        self.assertIn("`E = mc²`", processed)
        self.assertIn("Δ = b² - 4ac", processed)
        self.assertIn("Cost is $50.", processed)


if __name__ == "__main__":
    unittest.main()

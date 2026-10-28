"""Unit tests for Ctrans PyQt6 UI components (run headlessly via offscreen QPA)."""

import os
import sys
import unittest
from pathlib import Path

# Run tests headlessly
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from core.config import load_config
from core.command_loader import load_commands
from ui.input_bar import InputBar
from ui.loading_indicator import LoadingIndicator
from ui.result_view import ResultView
from ui.main_window import MainWindow
from ui.app import load_stylesheet


class TestUIComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication([])

        cls.script_dir = Path(__file__).resolve().parent.parent
        cls.config = load_config(script_dir=cls.script_dir)
        cls.catalog = load_commands(cls.config)

    def test_stylesheet_loads(self):
        css = load_stylesheet()
        self.assertIn("#CentralContainer", css)
        self.assertIn("rgba(28, 28, 30, 0.95)", css)
        self.assertIn("border-radius: 12px", css)
        self.assertIn("#89b4fa", css)
        self.assertIn("#cdd6f4", css)
        self.assertIn("JetBrainsMono Nerd Font", css)
        self.assertIn("QScrollBar:vertical", css)

    def test_input_bar_autocomplete(self):
        bar = InputBar(catalog=self.catalog)
        self.assertEqual(bar.placeholderText(), "Ask anything, enter prompt, or /help for commands...")
        completer = bar.completer()
        self.assertIsNotNone(completer)
        model = completer.model()
        self.assertIsNotNone(model)
        string_list = model.stringList()
        self.assertIn("/help", string_list)
        self.assertIn("/ask", string_list)
        self.assertIn("/eva", string_list)

    def test_loading_indicator(self):
        indicator = LoadingIndicator()
        self.assertTrue(indicator.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        indicator.set_loading_text("processing /ask...")
        self.assertEqual(indicator.label.text(), "processing /ask...")
        indicator.start()
        indicator._animate_step()
        self.assertTrue(indicator.label.text().startswith("processing /ask"))
        indicator.stop()

    def test_result_view(self):
        view = ResultView()
        self.assertTrue(view.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        test_md = "## Test Title\n\n• Point 1\n• Point 2"
        view.set_content(badge="/ask", content=test_md, is_error=False)
        self.assertEqual(view.badge_label.text(), "/ask")
        self.assertEqual(view._raw_content, test_md)
        self.assertIn("Test Title", view.text_browser.toPlainText())

        # Test copy functionality
        view._copy_to_clipboard()
        self.assertEqual(view.copy_button.text(), "✓ Copied!")

    def test_main_window_state_machine(self):
        window = MainWindow(config=self.config, catalog=self.catalog)
        self.assertEqual(window.stack.currentIndex(), MainWindow.STATE_INPUT)
        self.assertIsNotNone(window.container.graphicsEffect())

        # Verify zero layout margins on container (no box-in-box)
        margins = window.container.layout().contentsMargins()
        self.assertEqual(margins.left(), 0)
        self.assertEqual(margins.top(), 0)
        self.assertEqual(margins.right(), 0)
        self.assertEqual(margins.bottom(), 0)

        # Verify initial input state centering
        g0 = window.geometry()
        screen = window._get_target_screen()
        screen_geo = screen.availableGeometry()
        self.assertEqual(g0.x() + g0.width() // 2, screen_geo.x() + screen_geo.width() // 2)
        self.assertEqual(g0.y() + g0.height() // 2, screen_geo.y() + screen_geo.height() // 2)

        # Submit /help
        window._handle_submit("/help")
        self.assertEqual(window.stack.currentIndex(), MainWindow.STATE_RESULT)
        self.assertEqual(window.result_view.badge_label.text(), "Help")
        self.assertIn("Available Commands:", window.result_view.text_browser.toPlainText())

        # Verify result state horizontal and vertical centering
        g2 = window.geometry()
        self.assertEqual(g2.x() + g2.width() // 2, screen_geo.x() + screen_geo.width() // 2)
        self.assertEqual(g2.y() + g2.height() // 2, screen_geo.y() + screen_geo.height() // 2)

        # Submit missing argument
        window._handle_submit("/ask")
        self.assertEqual(window.stack.currentIndex(), MainWindow.STATE_RESULT)
        self.assertEqual(window.result_view.badge_label.text(), "Usage")
        self.assertIn("Missing argument for /ask", window.result_view.text_browser.toPlainText())

        # Submit unknown command
        window._handle_submit("/unknown_command_foo")
        self.assertEqual(window.stack.currentIndex(), MainWindow.STATE_RESULT)
        self.assertEqual(window.result_view.badge_label.text(), "Unknown Command")
        self.assertIn("Unknown Command: /unknown_command_foo", window.result_view.text_browser.toPlainText())

        window.close()


if __name__ == "__main__":
    unittest.main()

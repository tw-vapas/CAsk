"""Unit tests for Ctrans PyQt6 UI components (run headlessly via offscreen QPA)."""

import os
import sys
import unittest
from pathlib import Path

# Run tests headlessly
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QEvent, QPointF
from PyQt6.QtGui import QMouseEvent

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
        self.assertIn("#dcdfe7", css)
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

        # Test command property toggle
        bar.setText("/ask entropy")
        self.assertTrue(bar.property("is_command"))
        bar.setText("plain query")
        self.assertFalse(bar.property("is_command"))

    def test_input_bar_command_formatting_and_vietnamese(self):
        bar = InputBar(catalog=self.catalog)
        self.assertTrue(bar.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled))

        # Command token formatting only
        bar.setText("/ask giải thích entropy")
        self.assertEqual(bar.text(), "/ask giải thích entropy")
        formats = bar.document().firstBlock().layout().formats()
        self.assertEqual(len(formats), 1)
        fmt = formats[0]
        self.assertEqual(fmt.start, 0)
        self.assertEqual(fmt.length, 4)  # len('/ask')
        self.assertEqual(fmt.format.foreground().color().name(), "#f9e2af")
        self.assertEqual(fmt.format.fontWeight(), 700)

        # Content behind command token is not formatted
        trailing_text = bar.text()[fmt.start + fmt.length:]
        self.assertEqual(trailing_text, " giải thích entropy")

        # Plain Vietnamese input without command should have 0 custom formats
        bar.setText("Giải thích thuật toán tìm kiếm")
        self.assertEqual(bar.text(), "Giải thích thuật toán tìm kiếm")
        self.assertEqual(len(bar.document().firstBlock().layout().formats()), 0)

    def test_loading_indicator(self):
        indicator = LoadingIndicator()
        self.assertTrue(indicator.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        indicator.set_loading_text("processing /ask...")
        self.assertIn("/ask", indicator.label.text())
        self.assertIn("#f9e2af", indicator.label.text())
        indicator.start()
        indicator._animate_step()
        self.assertIn("/ask", indicator.label.text())
        indicator.stop()

    def test_result_view(self):
        view = ResultView()
        self.assertTrue(view.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        self.assertEqual(view.text_browser.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.assertEqual(view.text_browser.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        test_md = "## Test Title\n\n• Point 1\n• Point 2\n\nFormula: $E = mc^2$"
        view.set_content(badge="/ask", content=test_md, is_error=False)
        self.assertEqual(view.badge_label.text(), "/ask")
        self.assertIn("#f9e2af", view.badge_label.styleSheet())
        self.assertEqual(view._raw_content, test_md)
        self.assertIn("Test Title", view.text_browser.toPlainText())
        # Verify math formula was parsed into Unicode
        self.assertIn("E = mc²", view.text_browser.toPlainText())

        # Test elastic height calculation
        short_h = view.calculate_ideal_height(available_width=760)
        self.assertGreater(short_h, 85)
        self.assertLess(short_h, 300)

        long_md = "\n\n".join([f"### Section {i}\nDetailed paragraph text {i}" for i in range(12)])
        view.set_content(badge="/ask", content=long_md, is_error=False)
        long_h = view.calculate_ideal_height(available_width=760)
        self.assertGreater(long_h, short_h)

        # Test copy functionality
        view._copy_to_clipboard()
        self.assertEqual(view.copy_button.text(), "✓ Copied!")

    def test_main_window_state_machine(self):
        window = MainWindow(config=self.config, catalog=self.catalog)
        self.assertEqual(window.stack.currentIndex(), MainWindow.STATE_INPUT)
        self.assertIsNotNone(window.container.graphicsEffect())
        self.assertEqual(window.windowType(), Qt.WindowType.Dialog)
        self.assertTrue(window.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled))

        # Verify zero layout margins on container (no box-in-box)
        margins = window.container.layout().contentsMargins()
        self.assertEqual(margins.left(), 0)
        self.assertEqual(margins.top(), 0)
        self.assertEqual(margins.right(), 0)
        self.assertEqual(margins.bottom(), 0)

        # Verify initial input state centering on screen
        screen = window._get_target_screen()
        screen_geo = screen.availableGeometry()
        window.layout().activate()
        c0 = window.container.geometry()
        self.assertEqual(c0.x() + c0.width() // 2, screen_geo.width() // 2)
        self.assertEqual(c0.y() + c0.height() // 2, screen_geo.height() // 2)

        # Submit /help
        window._handle_submit("/help")
        self.assertEqual(window.stack.currentIndex(), MainWindow.STATE_RESULT)
        self.assertEqual(window.result_view.badge_label.text(), "Help")
        self.assertIn("Available Commands", window.result_view.text_browser.toPlainText())

        # Verify result state horizontal and vertical centering
        window.layout().activate()
        c2 = window.container.geometry()
        self.assertEqual(c2.x() + c2.width() // 2, screen_geo.width() // 2)
        self.assertEqual(c2.y() + c2.height() // 2, screen_geo.height() // 2)

        # Submit missing argument
        window._handle_submit("/ask")
        self.assertEqual(window.stack.currentIndex(), MainWindow.STATE_RESULT)
        self.assertEqual(window.result_view.badge_label.text(), "Usage")
        self.assertIn("Missing argument for", window.result_view.text_browser.toPlainText())
        self.assertIn("/ask", window.result_view.text_browser.toPlainText())

        # Submit unknown command
        window._handle_submit("/unknown_command_foo")
        self.assertEqual(window.stack.currentIndex(), MainWindow.STATE_RESULT)
        self.assertEqual(window.result_view.badge_label.text(), "Unknown Command")
        self.assertIn("Unknown Command: /unknown_command_foo", window.result_view.text_browser.toPlainText())

        # Test click outside floating capsule dismisses the HUD
        closed = []
        window.close = lambda: closed.append(True)
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window.mousePressEvent(event)
        self.assertTrue(closed)


if __name__ == "__main__":
    unittest.main()

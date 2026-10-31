"""Unit tests for CAsk PyQt6 UI components (run headlessly via offscreen QPA)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Run tests headlessly
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QEvent, QPointF
from PyQt6.QtGui import QInputMethodEvent, QKeyEvent, QMouseEvent

from core.config import load_config
from core.command_loader import load_commands
from ui.input_bar import InputBar
from ui.loading_indicator import LoadingIndicator
from ui.result_view import ResultView
from ui.capsule import CAskCapsule
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
        self.assertIn("rgba(27, 31, 38, 0.75)", css)
        self.assertIn("rgba(27, 31, 38, 0.78)", css)
        self.assertIn("border-radius: 14px", css)
        self.assertIn("#e6ebf5", css)
        self.assertIn("JetBrainsMono Nerd Font", css)
        self.assertIn("QScrollBar:vertical", css)

    def test_input_bar_autocomplete(self):
        bar = InputBar(catalog=self.catalog)
        self.assertEqual(bar.placeholderText(), "Type what's on your mind...")
        completer = bar.completer()
        self.assertIsNotNone(completer)
        model = completer.model()
        self.assertIsNotNone(model)
        string_list = model.stringList()
        self.assertIn("/help", string_list)
        self.assertIn("/ask", string_list)
        self.assertIn("/eva", string_list)

        popup = completer.popup()
        self.assertIsNotNone(popup)
        self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertTrue(bool(popup.windowFlags() & Qt.WindowType.FramelessWindowHint))

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
        self.assertEqual(window.windowType(), Qt.WindowType.Window)
        self.assertTrue(window.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled))

        # Verify zero layout margins on container (no box-in-box)
        margins = window.container.layout().contentsMargins()
        self.assertEqual(margins.left(), 0)
        self.assertEqual(margins.top(), 0)
        self.assertEqual(margins.right(), 0)
        self.assertEqual(margins.bottom(), 0)

        # Verify initial input state centering on screen
        screen = window._get_target_screen()
        # Verify initial input state centering on screen
        screen = window._get_target_screen()
        screen_geo = screen.availableGeometry()
        c0 = window.capsules[0].geometry()
        self.assertEqual(window.x() + c0.x() + c0.width() // 2, screen_geo.width() // 2)
        self.assertAlmostEqual(window.y() + c0.y() + c0.height() // 2, screen_geo.height() // 2, delta=1)

        # Test focus loss (ActivationChange) in STATE_INPUT does NOT close window
        input_closed = []
        window.close = lambda: input_closed.append(True)
        window.changeEvent(QEvent(QEvent.Type.ActivationChange))
        self.assertFalse(input_closed)

        # Test focus loss in STATE_LOADING does NOT close window
        window._switch_state(MainWindow.STATE_LOADING, target_width=600, target_height=54)
        window.changeEvent(QEvent(QEvent.Type.ActivationChange))
        self.assertFalse(input_closed)

        # Submit /help
        window._handle_submit("/help")
        self.assertEqual(window.stack.currentIndex(), MainWindow.STATE_RESULT)
        self.assertEqual(window.result_view.badge_label.text(), "Help")
        self.assertIn("Available Commands", window.result_view.text_browser.toPlainText())
        self.assertIn("/ask <topic>", window.result_view.text_browser.toPlainText())
        self.assertIn("/eva <sentence>", window.result_view.text_browser.toPlainText())

        # Verify result state horizontal and vertical centering
        c2 = window.capsules[0].geometry()
        self.assertEqual(window.x() + c2.x() + c2.width() // 2, screen_geo.width() // 2)
        self.assertAlmostEqual(window.y() + c2.y() + c2.height() // 2, screen_geo.height() // 2, delta=1)

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

        # Test focus loss in STATE_RESULT DOES dismiss unpinned window
        result_closed = []
        window.close = lambda: result_closed.append(True)
        window.changeEvent(QEvent(QEvent.Type.ActivationChange))
        self.assertTrue(result_closed)

        # Test click outside floating capsule dismisses the HUD in Result state
        window2 = MainWindow(config=self.config, catalog=self.catalog)
        window2._handle_submit("/help")
        click_closed = []
        window2.close = lambda: click_closed.append(True)
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window2.mousePressEvent(event)
        self.assertTrue(click_closed)

    def test_input_bar_dynamic_height_expansion(self):
        bar = InputBar(catalog=self.catalog)
        bar.resize(600, 50)
        # Empty text
        self.assertEqual(bar.calculate_ideal_height(600), 50)

        height_events = []
        bar.height_changed.connect(lambda h: height_events.append(h))

        # Single line text
        bar.setText("Hello world")
        self.assertEqual(bar.calculate_ideal_height(600), 50)
        self.assertEqual(bar.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Multiline text expands height
        bar.setText("Line 1\nLine 2\nLine 3\nLine 4")
        expanded_h = bar.calculate_ideal_height(600)
        self.assertGreater(expanded_h, 50)
        self.assertTrue(len(height_events) > 0)
        self.assertEqual(bar.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Clamped at maximum 220 -> scrollbar becomes AsNeeded
        bar.setText("\n".join(f"Line {i}" for i in range(25)))
        self.assertEqual(bar.calculate_ideal_height(600), 220)
        self.assertEqual(bar.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def test_result_view_pinning(self):
        view = ResultView()
        view.set_content("Test", "Some response content")
        self.assertFalse(view.is_pinned)

        # Verify buttons and icons
        self.assertFalse(view.ask_button.icon().isNull())
        self.assertEqual(view.ask_button.text(), "Ask")
        self.assertFalse(view.copy_button.icon().isNull())
        self.assertFalse(view.pin_button.icon().isNull())
        self.assertFalse(view.close_button.icon().isNull())

        dismissed = []
        view.dismiss_requested.connect(lambda: dismissed.append(True))

        from PyQt6.QtGui import QKeyEvent
        esc_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        enter_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)

        # Unpinned: Esc emits dismiss_requested
        view.keyPressEvent(esc_event)
        self.assertEqual(len(dismissed), 1)

        # Pin the view
        view.pin_button.click()
        self.assertTrue(view.is_pinned)
        self.assertEqual(view.pin_button.text(), "Pinned")

        # Pinned: Esc and Enter do NOT emit dismiss_requested
        view.keyPressEvent(esc_event)
        view.keyPressEvent(enter_event)
        self.assertEqual(len(dismissed), 1)

        # Pinned: Close button still emits dismiss_requested
        view.close_button.click()
        self.assertEqual(len(dismissed), 2)

        # Unpin: Esc again emits dismiss_requested
        view.pin_button.click()
        self.assertFalse(view.is_pinned)
        self.assertEqual(view.pin_button.text(), "Pin")
        view.keyPressEvent(esc_event)
        self.assertEqual(len(dismissed), 3)

    def test_result_view_shortcuts(self):
        view = ResultView()
        view.set_content("Test", "Sample content to test shortcuts")

        search_invoked = []
        view.return_to_input_requested.connect(lambda: search_invoked.append(True))

        from PyQt6.QtGui import QKeyEvent
        # Key 'Shift + A': return to input bar
        a_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier, "A")
        view.keyPressEvent(a_event)
        self.assertEqual(len(search_invoked), 1)

        # Key 'Shift + P': toggle pin
        self.assertFalse(view.is_pinned)
        p_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_P, Qt.KeyboardModifier.ShiftModifier, "P")
        view.keyPressEvent(p_event)
        self.assertTrue(view.is_pinned)
        view.keyPressEvent(p_event)
        self.assertFalse(view.is_pinned)

        # Key 'Shift + C': copy content
        c_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ShiftModifier, "C")
        view.keyPressEvent(c_event)
        self.assertEqual(view.copy_button.text(), "✓ Copied!")

        # Plain keys without Shift should NOT trigger shortcuts
        search_invoked.clear()
        plain_a = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a")
        view.keyPressEvent(plain_a)
        self.assertEqual(len(search_invoked), 0)

        # Test shortcut via text_browser event filter
        search_invoked.clear()
        from PyQt6.QtWidgets import QApplication
        QApplication.sendEvent(view.text_browser, a_event)
        self.assertEqual(len(search_invoked), 1)

    def test_result_view_table_rendering(self):
        view = ResultView()
        table_md = (
            "## Self-Love\n\n"
            "| Why it matters | How to practice it |\n"
            "| :--- | :--- |\n"
            "| Empty cup | • Identify strengths<br>• Forgive yourself |\n"
            "| Resilience | • Set boundaries |\n\n"
            "1. First point\n"
            "   - Sub point A\n"
        )
        view.set_content("Test", table_md)
        plain = view.text_browser.toPlainText()
        self.assertIn("Why it matters", plain)
        self.assertIn("How to practice it", plain)
        self.assertIn("Empty cup", plain)
        self.assertIn("Identify strengths", plain)
        self.assertIn("Forgive yourself", plain)
        self.assertIn("Set boundaries", plain)
        self.assertIn("First point", plain)
        self.assertIn("Sub point A", plain)

    def test_capsule_return_to_input(self):
        from ui.capsule import CAskCapsule
        capsule = CAskCapsule(config=self.config, catalog=self.catalog)
        capsule.switch_state(CAskCapsule.STATE_RESULT)
        self.assertEqual(capsule.state, CAskCapsule.STATE_RESULT)

        # Trigger return to input
        capsule.result_view.return_to_input_requested.emit()
        self.assertEqual(capsule.state, CAskCapsule.STATE_INPUT)
        self.assertEqual(capsule.stack.currentIndex(), CAskCapsule.STATE_INPUT)

    def test_multi_capsule_layout(self):
        window = MainWindow(config=self.config, catalog=self.catalog)
        screen = window._get_target_screen()
        screen_geo = screen.availableGeometry()
        sw = screen_geo.width()
        # 1 Window: centered with 35% screen width
        self.assertEqual(len(window.capsules), 1)
        slots1 = window._calculate_slot_geometries(screen_geo)
        self.assertEqual(len(slots1), 1)
        w1_cap, x1, y1, w1, h1 = slots1[0]
        self.assertEqual(w1, max(400, int(sw * 0.35)))
        self.assertEqual(x1 + w1 // 2, screen_geo.x() + sw // 2)

        # 2 Windows: 80% of screen width, equal width, W1 on left, W2 on right
        window.handle_external_launch("")
        self.assertEqual(len(window.capsules), 2)
        slots2 = window._calculate_slot_geometries(screen_geo)
        self.assertEqual(len(slots2), 2)
        cap_left, x_l, _, w_l, _ = slots2[0]
        cap_right, x_r, _, w_r, _ = slots2[1]
        self.assertIs(cap_left, window.capsules[0])   # W1
        self.assertIs(cap_right, window.capsules[1])  # W2
        self.assertEqual(w_l, w_r)
        total_2w = (x_r + w_r) - x_l
        self.assertAlmostEqual(total_2w, int(sw * 0.80), delta=1)

        # 3 Windows: full screen, 30:40:30 ratio, W3 on left, W1 in center, W2 on right
        window.handle_external_launch("")
        self.assertEqual(len(window.capsules), 3)
        slots3 = window._calculate_slot_geometries(screen_geo)
        self.assertEqual(len(slots3), 3)
        s_left, s_center, s_right = slots3
        self.assertIs(s_left[0], window.capsules[2])    # W3
        self.assertIs(s_center[0], window.capsules[0])  # W1
        self.assertIs(s_right[0], window.capsules[1])   # W2

        w_left = s_left[3]
        w_center = s_center[3]
        w_right = s_right[3]
        # Verify 30:40:30 ratio
        total_content_w = w_left + w_center + w_right
        self.assertAlmostEqual(w_left / total_content_w, 0.30, delta=0.03)
        self.assertAlmostEqual(w_right / total_content_w, 0.30, delta=0.03)
        self.assertAlmostEqual(w_center / total_content_w, 0.40, delta=0.03)

        # 4th launch must NOT exceed 3 capsules
        window.handle_external_launch("extra launch")
        self.assertEqual(len(window.capsules), 3)

        # Close W3 -> falls back to 2 windows (W1 left, W2 right)
        window._handle_capsule_close(window.capsules[2])
        self.assertEqual(len(window.capsules), 2)
        slots_after = window._calculate_slot_geometries(screen_geo)
        self.assertIs(slots_after[0][0], window.capsules[0])
        self.assertIs(slots_after[1][0], window.capsules[1])

    def test_enter_key_dismissal(self):
        # Empty input bar cancels on Enter
        bar = InputBar(catalog=self.catalog)
        cancelled = []
        bar.cancelled.connect(lambda: cancelled.append(True))
        from PyQt6.QtGui import QKeyEvent
        enter_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        bar.keyPressEvent(enter_event)
        self.assertTrue(cancelled)

        # MainWindow dismisses on Enter in Loading state
        window = MainWindow(config=self.config, catalog=self.catalog)
        window._switch_state(MainWindow.STATE_LOADING, 600, 54)
        closed = []
        window.close = lambda: closed.append(True)
        window.keyPressEvent(enter_event)
        self.assertTrue(closed)

    def test_single_instance_manager(self):
        from ui.single_instance import SingleInstanceManager
        app_name = "cask_unit_test"
        mgr1 = SingleInstanceManager(app_name=app_name)
        try:
            self.assertTrue(mgr1.try_acquire())
            # Second attempt while mgr1 is running must return False
            mgr2 = SingleInstanceManager(app_name=app_name)
            self.assertFalse(mgr2.try_acquire())
        finally:
            mgr1.cleanup()

    def test_window_reorder_shortcuts(self):
        """Test Shift+Left and Shift+Right window swapping at N=2 and N=3."""
        from PyQt6.QtGui import QKeyEvent
        window = MainWindow(config=self.config, catalog=self.catalog)
        screen = window._get_target_screen()
        screen_geo = screen.availableGeometry()

        # N=1: swap does nothing
        self.assertFalse(window.swap_capsule_slot(window.capsules[0], -1))
        self.assertFalse(window.swap_capsule_slot(window.capsules[0], 1))

        # Launch 2nd window
        window.handle_external_launch("")
        self.assertEqual(len(window.capsules), 2)
        w1 = window.capsules[0]
        w2 = window.capsules[1]

        # Initially slot 0 = w1, slot 1 = w2
        self.assertEqual(window.get_capsule_slot_index(w1), 0)
        self.assertEqual(window.get_capsule_slot_index(w2), 1)

        # Swapping left on slot 0 does nothing
        self.assertFalse(window.swap_capsule_slot(w1, -1))

        # Swap w1 to right (+1)
        self.assertTrue(window.swap_capsule_slot(w1, 1))
        self.assertEqual(window.get_capsule_slot_index(w1), 1)
        self.assertEqual(window.get_capsule_slot_index(w2), 0)

        # Swap w1 back to left (-1)
        self.assertTrue(window.swap_capsule_slot(w1, -1))
        self.assertEqual(window.get_capsule_slot_index(w1), 0)
        self.assertEqual(window.get_capsule_slot_index(w2), 1)

        # Launch 3rd window
        window.handle_external_launch("")
        self.assertEqual(len(window.capsules), 3)
        w3 = window.capsules[2]

        # Initial layout slots: Slot 0 = w3 (30%), Slot 1 = w1 (40%), Slot 2 = w2 (30%)
        self.assertEqual(window.get_capsule_slot_index(w3), 0)
        self.assertEqual(window.get_capsule_slot_index(w1), 1)
        self.assertEqual(window.get_capsule_slot_index(w2), 2)

        # Swap center card (w1) to the left (-1) -> w1 takes slot 0 (30%), w3 takes slot 1 (40%)
        self.assertTrue(window.swap_capsule_slot(w1, -1))
        self.assertEqual(window.get_capsule_slot_index(w1), 0)
        self.assertEqual(window.get_capsule_slot_index(w3), 1)
        self.assertEqual(window.get_capsule_slot_index(w2), 2)

        # Verify geometry ratio preservation: slot 1 is 40%, slot 0 is 30%
        slots = window._calculate_slot_geometries(screen_geo)
        w_s0 = slots[0][3]
        w_s1 = slots[1][3]
        w_s2 = slots[2][3]
        total = w_s0 + w_s1 + w_s2
        self.assertIs(slots[0][0], w1)
        self.assertIs(slots[1][0], w3)
        self.assertAlmostEqual(w_s0 / total, 0.30, delta=0.03)
        self.assertAlmostEqual(w_s1 / total, 0.40, delta=0.03)
        self.assertAlmostEqual(w_s2 / total, 0.30, delta=0.03)

        # Test key event interception via MainWindow keyPressEvent with AltModifier
        alt_right_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
        window.keyPressEvent(alt_right_event)
        # w1 was at slot 0, should now be at slot 1
        self.assertEqual(window.get_capsule_slot_index(w1), 1)

        # Test reordering directly from InputBar via Alt+Left / Alt+Right
        w1.switch_state(CAskCapsule.STATE_INPUT)
        w1.input_bar.setText("Some query text to highlight")
        # Ensure text is not selected by Alt+Left/Right and reorders smoothly
        alt_left_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
        w1.input_bar.keyPressEvent(alt_left_event)
        # w1 was at slot 1, should now be back at slot 0
        self.assertEqual(window.get_capsule_slot_index(w1), 0)

        # Verify tooltip on drag handle
        w1.switch_state(CAskCapsule.STATE_RESULT)
        self.assertIn("Alt + ← / →", w1.result_view.drag_handle.toolTip())

    def test_drag_reorder_and_ghost_indicator(self):
        """Test drag handle and drop ghost indicator reordering."""
        from PyQt6.QtCore import QPoint
        window = MainWindow(config=self.config, catalog=self.catalog)
        window.handle_external_launch("")
        window.handle_external_launch("")
        self.assertEqual(len(window.capsules), 3)

        w1 = window.capsules[0]
        w2 = window.capsules[1]
        w3 = window.capsules[2]

        screen = window._get_target_screen()
        screen_geo = screen.availableGeometry()
        slots = window._calculate_slot_geometries(screen_geo)
        # Slot 0 = w3, Slot 1 = w1, Slot 2 = w2
        self.assertEqual(window.get_capsule_slot_index(w3), 0)

        # Drag w3 towards rightmost slot (Slot 2)
        target_center_x = slots[2][1] + slots[2][3] // 2
        drag_pos = QPoint(target_center_x, screen_geo.height() // 2)

        window._handle_capsule_drag_start(w3, drag_pos)
        self.assertTrue(window.ghost_indicator.isVisible())
        self.assertEqual(window._target_drop_slot, 2)

        # Drop onto slot 2
        window._handle_capsule_drag_end(w3, drag_pos)
        self.assertFalse(window.ghost_indicator.isVisible())
        self.assertEqual(window.get_capsule_slot_index(w3), 2)

    def test_vietnamese_ime_preedit_expansion(self):
        """Verify InputBar expands immediately during Vietnamese IME preedit composition without space."""
        bar = InputBar()
        bar.resize(600, 50)
        # Find single line boundary text
        words = ["word"] * 50
        base_t = ""
        wrap_word = "word"
        for i in range(1, len(words)):
            t = " ".join(words[:i])
            bar.setText(t)
            if bar.calculate_ideal_height(600) > 50:
                base_t = " ".join(words[:i-1])
                wrap_word = words[i-1]
                break

        bar.setText(base_t)
        self.assertEqual(bar.calculate_ideal_height(600), 50)

        # Simulate Vietnamese IME typing next word in uncommitted preedit mode
        ev = QInputMethodEvent(" " + wrap_word, [])
        bar.inputMethodEvent(ev)
        self.assertGreater(bar.calculate_ideal_height(600), 50)
        self.assertGreater(bar._current_ideal_height, 50)

    def test_toggle_always_on_top_shortcut(self):
        """Verify Alt + H toggles window on-top state across MainWindow, InputBar, and ResultView."""
        window = MainWindow(config=self.config, catalog=self.catalog)
        self.assertTrue(window._is_always_on_top)

        # Direct toggle to False (send to back / lower layer)
        res = window.toggle_always_on_top()
        self.assertFalse(res)
        self.assertFalse(window._is_always_on_top)

        # Direct toggle back to True (bring to front / on-top)
        res = window.toggle_always_on_top()
        self.assertTrue(res)
        self.assertTrue(window._is_always_on_top)

        # Alt + H key event on MainWindow
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_H, Qt.KeyboardModifier.AltModifier)
        window.keyPressEvent(event)
        self.assertFalse(window._is_always_on_top)

        # Alt + H on InputBar emits toggle_on_top_requested
        bar = window.primary_capsule.input_bar
        emitted = []
        bar.toggle_on_top_requested.connect(lambda: emitted.append("bar"))
        bar.keyPressEvent(event)
        self.assertEqual(emitted, ["bar"])

        # Alt + H on ResultView emits toggle_on_top_requested
        view = window.primary_capsule.result_view
        view_emitted = []
        view.toggle_on_top_requested.connect(lambda: view_emitted.append("view"))
        view._handle_key_event(event)
        self.assertEqual(view_emitted, ["view"])

    def test_result_view_followup_input_and_turn_status(self):
        """Verify ResultView follow-up footer visibility, turn badge, and turn limit clamping."""
        view = ResultView()
        view.show()
        self.assertTrue(view.footer_widget.isVisible())

        # Render normal response: footer visible, turn 1 of 3
        view.set_content("Assistant", "Initial response content", current_turn=1, max_turns=3)
        self.assertTrue(view.footer_widget.isVisible())
        self.assertEqual(view.turn_badge.text(), "1/3")
        self.assertTrue(view.followup_input.isEnabled())
        self.assertFalse(view.turn_badge.property("limit_reached"))

        # Advance to turn limit (3 of 3)
        view.update_turn_status(3, 3)
        self.assertEqual(view.turn_badge.text(), "3/3")
        self.assertFalse(view.followup_input.isEnabled())
        self.assertTrue(view.turn_badge.property("limit_reached"))
        self.assertIn("limit reached", view.followup_input.placeholderText().lower())

        # Error response: footer should be hidden
        view.set_content("Error [Assistant]", "Error description", is_error=True)
        self.assertFalse(view.footer_widget.isVisible())

    def test_result_view_append_turn(self):
        """Verify ResultView appends Q&A markdown turns and updates turn status."""
        view = ResultView()
        view.set_content("Assistant", "First response", current_turn=1, max_turns=3)
        self.assertEqual(view._raw_content, "First response")

        # Append turn 2
        view.append_turn("Can you give an example?", "Here is an example: `code`", current_turn=2, max_turns=3)
        self.assertIn("First response", view._raw_content)
        self.assertIn('<div class="user-turn"><strong>User:</strong> Can you give an example?</div>', view._raw_content)
        self.assertIn("Here is an example: `code`", view._raw_content)
        self.assertEqual(view.turn_badge.text(), "2/3")
        self.assertTrue(view.followup_input.isEnabled())

        # Test clipboard copy cleanses HTML tags into standard Markdown
        view._copy_to_clipboard()
        clipboard_text = self.app.clipboard().text()
        self.assertIn("**User:** Can you give an example?", clipboard_text)

    def test_result_view_keyboard_guards_in_followup(self):
        """Verify keyboard shortcuts (Shift+A, Shift+P) do not trigger when typing in follow-up input."""
        view = ResultView()
        view.show()
        self.app.setActiveWindow(view)
        view.followup_input.setFocus()
        self.assertTrue(view.followup_input.hasFocus())

        # Shift + A (user typing 'A'): should not trigger return_to_input_requested
        return_emitted = []
        view.return_to_input_requested.connect(lambda: return_emitted.append(True))
        event_a = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier)
        handled = view._handle_key_event(event_a)
        self.assertFalse(handled)
        self.assertEqual(len(return_emitted), 0)

        # Shift + P (user typing 'P'): should not toggle pin
        pin_emitted = []
        view.pin_toggled.connect(lambda val: pin_emitted.append(val))
        event_p = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_P, Qt.KeyboardModifier.ShiftModifier)
        handled = view._handle_key_event(event_p)
        self.assertFalse(handled)
        self.assertEqual(len(pin_emitted), 0)

        # Esc in follow-up input: clears input first
        view.followup_input.setText("incomplete query")
        event_esc = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        self.assertTrue(view.eventFilter(view.followup_input, event_esc))
        self.assertEqual(view.followup_input.text(), "")

    def test_capsule_multiturn_thread_management(self):
        """Verify CAskCapsule tracks multi-turn history, limits turns, and resets on return to input."""
        import dataclasses
        from unittest.mock import MagicMock, patch

        with patch("ui.capsule.APIWorker") as MockWorker:
            mock_worker = MagicMock()
            mock_worker.isRunning.return_value = False
            MockWorker.return_value = mock_worker

            # Ensure config has dummy key and max_turns=3
            cfg = dataclasses.replace(
                self.config,
                groq_api_key="dummy_key",
                gemini_api_key="dummy_gemini",
                max_followup_turns=3,
            )

            capsule = CAskCapsule(config=cfg, catalog=self.catalog)
            self.assertEqual(capsule._chat_history, [])
            self.assertEqual(capsule._turn_count, 1)

            # Turn 1: Initial query
            capsule._handle_submit("First question")
            self.assertEqual(capsule.state, CAskCapsule.STATE_LOADING)

            # Simulate worker response for turn 1
            callbacks = [call[0][0] for call in mock_worker.finished.connect.call_args_list]
            callbacks[-1]("First answer from AI")

            self.assertEqual(capsule.state, CAskCapsule.STATE_RESULT)
            self.assertEqual(len(capsule._chat_history), 2)
            self.assertEqual(capsule._chat_history[0], {"role": "user", "content": "First question"})
            self.assertEqual(capsule._chat_history[1], {"role": "assistant", "content": "First answer from AI"})
            self.assertEqual(capsule._turn_count, 1)

            # Turn 2: Follow-up query
            capsule._handle_followup_submit("Second follow-up question")
            # Verify MockWorker received history with the previous turn
            last_kwargs = MockWorker.call_args[1]
            self.assertEqual(len(last_kwargs["history"]), 2)
            self.assertEqual(last_kwargs["user_prompt_content"], "Second follow-up question")

            # Simulate worker response for turn 2
            callbacks = [call[0][0] for call in mock_worker.finished.connect.call_args_list]
            callbacks[-1]("Second answer from AI")

            self.assertEqual(capsule._turn_count, 2)
            self.assertEqual(len(capsule._chat_history), 4)
            self.assertEqual(capsule._chat_history[2], {"role": "user", "content": "Second follow-up question"})
            self.assertEqual(capsule._chat_history[3], {"role": "assistant", "content": "Second answer from AI"})

            # Turn 3: Follow-up query reaching limit
            capsule._handle_followup_submit("Third question reaching limit")
            callbacks = [call[0][0] for call in mock_worker.finished.connect.call_args_list]
            callbacks[-1]("Third answer")

            self.assertEqual(capsule._turn_count, 3)
            self.assertFalse(capsule.result_view.followup_input.isEnabled())

            # Attempting Turn 4: Should be blocked by turn limit
            call_count_before = MockWorker.call_count
            capsule._handle_followup_submit("Fourth question should be rejected")
            self.assertEqual(MockWorker.call_count, call_count_before)

            # Returning to input (Shift + A) must reset conversation history
            capsule._handle_return_to_input()
            self.assertEqual(capsule.state, CAskCapsule.STATE_INPUT)
            self.assertEqual(capsule._chat_history, [])
            self.assertEqual(capsule._turn_count, 1)

    def test_initial_launch_enforces_kwin_layer(self):
        """Verify that window display and external launch proactively enforce KWin Keep Above layer."""
        window = MainWindow(config=self.config, catalog=self.catalog)
        self.assertTrue(window._is_always_on_top)

        with patch.object(window, "_set_kwin_layer") as mock_set_layer:
            # 1. When window is shown, showEvent invokes _apply_initial_layer
            with patch.object(window, "_apply_initial_layer") as mock_apply:
                window.showEvent(None)
                mock_apply.assert_called_once()

            # 2. _apply_initial_layer calls _set_kwin_layer(True) when on-top is active
            window._apply_initial_layer(retries=0)
            mock_set_layer.assert_called_with(True)

            mock_set_layer.reset_mock()
            # 3. When on-top is disabled, _apply_initial_layer does not force keep-above
            window._is_always_on_top = False
            window._apply_initial_layer(retries=0)
            mock_set_layer.assert_not_called()

            # 4. handle_external_launch re-enforces on-top layer
            window._is_always_on_top = True
            with patch.object(window, "_apply_initial_layer") as mock_apply_launch:
                window.handle_external_launch()
                mock_apply_launch.assert_any_call(retries=2)

    def test_followup_slash_command_routing_and_completer(self):
        """Verify ResultView follow-up input supports command completer and routes slash commands."""
        import dataclasses
        from unittest.mock import MagicMock, patch

        cfg = dataclasses.replace(
            self.config,
            groq_api_key="dummy_key",
            gemini_api_key="dummy_gemini",
            max_followup_turns=5,
        )

        capsule = CAskCapsule(config=cfg, catalog=self.catalog)
        view = capsule.result_view

        # 1. Verify completer is registered on followup_input
        self.assertIsNotNone(view._completer)
        view.followup_input.setText("/t")
        self.assertTrue(view.followup_input.property("is_command"))

        with patch("ui.capsule.APIWorker") as MockWorker:
            mock_worker = MagicMock()
            mock_worker.isRunning.return_value = False
            MockWorker.return_value = mock_worker

            # Simulate initial response
            capsule._handle_submit("Initial prompt")
            callbacks = [call[0][0] for call in mock_worker.finished.connect.call_args_list]
            callbacks[0]("Initial AI response")
            self.assertEqual(capsule.state, CAskCapsule.STATE_RESULT)

            # 2. Follow-up with /help: zero API calls, instantly appends turn
            MockWorker.reset_mock()
            capsule._handle_followup_submit("/help")
            MockWorker.assert_not_called()
            self.assertIn("Available Commands", view._raw_content)

            # 3. Follow-up with registered command /trans
            MockWorker.reset_mock()
            capsule._handle_followup_submit("/trans Dịch câu này sang tiếng Anh")
            MockWorker.assert_called_once()
            call_kwargs = MockWorker.call_args[1]
            self.assertEqual(call_kwargs["user_prompt_content"], "Dịch câu này sang tiếng Anh")
            self.assertIn("translation", call_kwargs["system_prompt"].lower())

    def test_worker_cancellation_and_stop_worker(self):
        """Verify stop_worker cancels active worker and detaches signals cleanly."""
        from core.api_client import APIWorker
        from ui.capsule import is_worker_active

        worker = APIWorker(
            system_prompt="sys",
            user_prompt_content="usr",
            config=self.config,
            history=None,
            parent=None,
        )
        self.assertFalse(worker._is_cancelled)
        worker.cancel()
        self.assertTrue(worker._is_cancelled)

        # Verify is_worker_active handles None cleanly
        self.assertFalse(is_worker_active(None))

        # Verify stop_worker does not crash when called multiple times or when worker is None
        capsule = CAskCapsule(config=self.config, catalog=self.catalog)
        capsule._worker = None
        capsule.stop_worker()
        self.assertIsNone(capsule._worker)

    def test_enter_key_in_followup_input_does_not_dismiss_window(self):
        """Verify pressing Enter in follow-up input bar submits query without closing unpinned window."""
        window = MainWindow(config=self.config, catalog=self.catalog)
        self.assertEqual(len(window.capsules), 1)
        capsule = window.primary_capsule
        capsule.switch_state(CAskCapsule.STATE_RESULT)
        self.assertFalse(capsule.is_pinned)

        view = capsule.result_view
        view.followup_input.setText("Follow-up question")
        view.followup_input.setFocus()

        # Simulate Enter key event filtered on followup_input
        enter_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        handled = view.eventFilter(view.followup_input, enter_event)
        self.assertTrue(handled)

        # Capsule remains open
        self.assertEqual(len(window.capsules), 1)


if __name__ == "__main__":
    unittest.main()




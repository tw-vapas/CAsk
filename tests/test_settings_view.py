"""Regression tests for settings dropdown scrolling and background connection tests."""

import os
import threading
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QEvent, QPoint, QPointF, QThread, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.config import Config
from core.model_config import ModelEntry
from ui.settings_view import ModelCardWidget, SettingsView


class RecordingModelCard(ModelCardWidget):
    """Record which thread receives a connection test result."""

    def _apply_test_result(self, success, latency, msg):
        self.result_thread = QThread.currentThread()
        super()._apply_test_result(success, latency, msg)


class TestSettingsView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.entries = tuple(
            ModelEntry(
                id=f"local_{index}", name=f"Local {index}",
                protocol="openai_compatible", model="test-model",
                base_url="http://localhost:11434/v1",
            )
            for index in range(3)
        )
        self.view = SettingsView(Config(models=self.entries))
        self.view.resize(760, 460)
        self.view.show()
        self.app.processEvents()
        self.addCleanup(self.view.close)
        self.addCleanup(self.view.deleteLater)

    def send_wheel(self, widget, delta=-120):
        window = widget.window()
        position = widget.mapTo(window, widget.rect().center())
        event = QWheelEvent(
            QPointF(position), QPointF(window.mapToGlobal(position)),
            QPoint(), QPoint(0, delta), Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
        )
        self.app.sendEvent(window.windowHandle(), event)
        self.app.processEvents()

    def test_closed_dropdowns_keep_selection_and_allow_panel_scrolling(self):
        card = self.view.cards[0]
        scrollbar = self.view.scroll_area.verticalScrollBar()
        self.assertGreater(scrollbar.maximum(), 0)
        for combo in (card.proto_combo, card.model_combo, self.view.preset_combo):
            for focused in (False, True):
                with self.subTest(combo=combo, focused=focused):
                    scrollbar.setValue(0)
                    if focused:
                        combo.setFocus()
                    else:
                        card.name_input.setFocus()
                    self.app.processEvents()
                    selected = combo.currentText()
                    self.send_wheel(combo)
                    self.assertEqual(combo.currentText(), selected)
                    if combo is not self.view.preset_combo:
                        self.assertGreater(scrollbar.value(), 0)

        scrollbar.setValue(0)
        selected = card.model_combo.currentText()
        self.send_wheel(card.model_combo.lineEdit())
        self.assertEqual(card.model_combo.currentText(), selected)
        self.assertGreater(scrollbar.value(), 0)

    def test_dropdowns_still_support_explicit_selection(self):
        combo = self.view.preset_combo
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key.Key_Down)
        self.assertEqual(combo.currentIndex(), 1)

        combo.showPopup()
        self.app.processEvents()
        popup = combo.view()
        self.assertTrue(popup.isVisible())
        target = combo.model().index(2, 0)
        QTest.mouseClick(
            popup.viewport(), Qt.MouseButton.LeftButton,
            pos=popup.visualRect(target).center(),
        )
        self.assertEqual(combo.currentIndex(), 2)
        combo.hidePopup()

    def test_connection_results_reach_gui_thread_and_allow_retry(self):
        card = RecordingModelCard(self.entries[0])
        self.addCleanup(card.deleteLater)
        outcomes = (
            (True, 0.12, "Connected"),
            (False, 0.04, "Invalid API key"),
            TimeoutError("Connection timed out"),
            RuntimeError("Unexpected provider failure"),
            (False, 0.01, "A" * 60),
            (True, 0.08, "Connected"),
        )
        with patch(
            "ui.settings_view.APIClient.test_provider_connection", side_effect=outcomes
        ) as request:
            for outcome in outcomes:
                with self.subTest(outcome=outcome):
                    card.test_btn.click()
                    self.assertFalse(card.test_btn.isEnabled())
                    self.assertEqual(card.test_result.text(), "Testing...")
                    worker = card._test_thread
                    worker.join(timeout=2)
                    self.assertFalse(worker.is_alive())
                    self.app.processEvents()
                    self.assertTrue(card.test_btn.isEnabled())
                    self.assertEqual(card.result_thread, self.app.thread())
                    success = not isinstance(outcome, Exception) and outcome[0]
                    self.assertTrue(card.test_result.text().startswith("✓" if success else "✗"))
                    message = str(outcome) if isinstance(outcome, Exception) else outcome[2]
                    self.assertEqual(card.test_result.toolTip(), message)
            self.assertEqual(request.call_count, len(outcomes))
            self.assertEqual(request.call_args.kwargs["timeout"], 8)

    def test_pending_test_can_finish_after_card_deletion(self):
        card = ModelCardWidget(self.entries[0])
        release = threading.Event()
        self.addCleanup(release.set)

        def delayed_result(**kwargs):
            release.wait(timeout=2)
            return True, 0.1, "Connected"

        thread_errors = []
        with patch("ui.settings_view.APIClient.test_provider_connection", side_effect=delayed_result), \
                patch("threading.excepthook", side_effect=thread_errors.append):
            card.test_btn.click()
            worker = card._test_thread
            card.deleteLater()
            self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            release.set()
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.app.processEvents()
        self.assertEqual(thread_errors, [])


if __name__ == "__main__":
    unittest.main()

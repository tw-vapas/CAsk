"""Settings navigation, isolation, inline removal, and scrolling regressions."""
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
from core.config import Config
from core.provider_api import default_profile
from core.provider_config import Provider
from ui.app import load_stylesheet
from ui.provider_settings import SettingsView


class SettingsRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(load_stylesheet())

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        models = [default_profile('gpt-6.1-sol', f'Sol {i}') for i in range(12)]
        first = Provider('first', 'OpenAI Personal', 'openai', 'openai_responses',
                         'https://example.invalid/v1', '', models=models, active_model_id=models[0].id)
        second = replace(first, id='second', name='Other')
        self.config = Config(config_dir=Path(self.directory.name), providers=(first, second))
        self.host = QWidget()
        self.host.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(self.host)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = SettingsView(self.config)
        layout.addWidget(self.view)
        self.host.resize(800, 760)
        self.host.show()
        self.app.processEvents()
        self.addCleanup(self.host.deleteLater)
        self.addCleanup(self.host.close)

    def test_one_accordion_and_bounded_scroll(self):
        first, second = self.view.cards
        self.assertTrue(first._expanded)
        self.assertFalse(second._expanded)
        self.assertTrue(first.connection_fields.isHidden())
        self.assertGreater(first.models_scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(first.add_model_btn.isVisible())
        self.view._expand(second)
        self.assertFalse(first._expanded)
        self.assertTrue(second._expanded)
        self.view._expand(second)
        self.assertFalse(any(c._expanded for c in self.view.cards))

    def test_back_preserves_drafts_expansion_and_scroll_without_windows(self):
        card = self.view.cards[0]
        bar = card.models_scroll.verticalScrollBar()
        bar.setValue(110)
        before = bar.value()
        card.name_input.setText('Draft connection')
        card._rename('Draft connection')
        card.add_model()
        editor = self.view.editor
        editor.model_id.setText('gpt-6.1-sol')
        editor.continue_btn.click()
        editor.name.setText('Draft model')
        editor.reasoning.setCurrentText('High')
        editor.back_btn.click()
        self.assertEqual(editor.pages.currentIndex(), 0)
        editor.continue_btn.click()
        self.assertEqual(editor.name.text(), 'Draft model')
        self.assertEqual(editor.reasoning.currentData(), 'high')
        self.assertIsNone(self.app.activeModalWidget())
        self.assertFalse(editor.isWindow())
        editor.save_btn.click()
        self.app.processEvents()
        self.assertIsNone(self.view.editor)
        self.assertTrue(card._expanded)
        self.assertEqual(card.provider.name, 'Draft connection')
        self.assertEqual(bar.value(), before)
        self.assertEqual(len(card.provider.models), 13)
        self.assertEqual(len(self.config.providers[0].models), 12)
        self.assertFalse((self.config.config_dir / 'providers.json').exists())

    def test_inline_model_confirmation_cancels_and_guards_active(self):
        card = self.view.cards[0]
        profile = card.provider.models[1]
        card._confirm_model(profile)
        self.assertEqual(card.models_scroll.height(), 258)
        prompt = card.findChild(QPushButton, 'SettingsDanger')
        self.assertIsNotNone(prompt)
        self.assertEqual(len(card.provider.models), 12)
        card._cancel_model_removal()
        self.assertEqual(card.models_scroll.height(), 214)
        self.assertEqual(len(card.provider.models), 12)
        card._confirm_model(card.provider.active_model)
        self.app.sendPostedEvents()
        # Current confirmation is in the newly rendered model container.
        prompts = [b for b in card.models_container.findChildren(QPushButton, 'SettingsDanger') if not b.isHidden()]
        self.assertTrue(prompts)
        self.assertFalse(prompts[-1].isEnabled())
        card._confirm_model(profile)
        prompts = card.models_container.findChildren(QPushButton, 'SettingsDanger')
        prompts[-1].click()
        self.assertEqual(len(card.provider.models), 11)
        self.assertEqual(card.provider.active_model_id, self.config.providers[0].active_model_id)

    def test_provider_removal_is_inline_and_cancel_restores_expansion(self):
        card = self.view.cards[0]
        card._confirm_provider()
        self.assertTrue(card.provider_confirmation.isVisible())
        self.assertFalse(card.details.isVisible())
        self.assertEqual(len(self.view.cards), 2)
        card._cancel_provider_removal()
        self.assertTrue(card.details.isVisible())
        card._confirm_provider()
        card.provider_confirmation.findChild(QPushButton, 'SettingsDanger').click()
        self.assertEqual(len(self.view.cards), 1)
        self.assertEqual(len(self.config.providers), 2)

    def test_render_preserves_panel_opacity_and_transparent_corners(self):
        for edit in (False, True):
            if edit:
                card = self.view.cards[0]
                card._edit_model(card.provider.models[0])
            self.app.processEvents()
            image = self.host.grab().toImage()
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
            self.assertEqual(image.pixelColor(image.width()-1, image.height()-1).alpha(), 0)
            self.assertIn(image.pixelColor(image.width()//2, 8).alpha(), range(190, 193))

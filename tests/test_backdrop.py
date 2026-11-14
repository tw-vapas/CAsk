"""Blur geometry, protocol safety, and capsule lifecycle regressions."""
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtWidgets import QApplication
from core.config import Config
from core.command_loader import CommandCatalog
from ui.backdrop import rounded_rectangles, as_region
from ui.main_window import MainWindow
from ui.wayland_blur import WaylandBlur


class BlurRegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_rounded_regions_exclude_corners_and_gaps(self):
        left, right = QRect(10, 20, 200, 96), QRect(240, 10, 300, 400)
        rects = rounded_rectangles(left, 28) + rounded_rectangles(right, 14)
        region = as_region(rects)
        for rect in (left, right):
            self.assertTrue(region.contains(rect.center()))
            self.assertFalse(region.contains(rect.topLeft()))
            self.assertFalse(region.contains(rect.bottomRight()))
        self.assertFalse(region.contains(QPoint(225, 50)))
        for x, y, width, height in rects:
            self.assertTrue(left.contains(QRect(x, y, width, height)) or right.contains(QRect(x, y, width, height)))
        self.assertEqual(rounded_rectangles(QRect(), 14), [])
        self.assertLess(len(rects), 100)

    def test_layout_updates_mask_for_state_count_and_close(self):
        with patch.object(MainWindow, '_apply_initial_layer'):
            window = MainWindow(Config(providers=()), CommandCatalog({}))
            window.show()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        native = MagicMock()
        window._backdrop_blur = native
        window._recompute_layout()
        initial = tuple(window._blur_rectangles)
        window.primary_capsule.switch_state(3)
        self.assertNotEqual(initial, tuple(window._blur_rectangles))
        window.handle_external_launch()
        window.handle_external_launch()
        for capsule in window.capsules:
            self.assertTrue(window.mask().contains(capsule.geometry().center()))
            self.assertFalse(window.mask().contains(capsule.geometry().topLeft()))
        self.assertEqual(len(window.capsules), 3)
        window._handle_capsule_close(window.capsules[-1])
        window._handle_capsule_close(window.capsules[-1])
        self.assertEqual(len(window.capsules), 1)
        self.assertEqual(native.update.call_args.args[1], window._blur_rectangles)
        window.hide()
        self.assertEqual(native.update.call_args.args[1], [])
        window.show()
        self.assertTrue(native.update.call_args.args[1])

    def transport(self, standard=True):
        transport = WaylandBlur.__new__(WaylandBlur)
        transport._closed = False
        transport.manager = 1
        transport.compositor = 2
        transport.surface = 3
        transport.display = 4
        transport.blur = None
        transport._standard = standard
        transport._supports_blur = True
        transport._applied = None
        transport._desired = ((10, 20, 100, 200),)
        transport._repaint = MagicMock()
        transport.wl = MagicMock()
        transport.region_interface = 'region'
        transport.effect_interface = 'effect'
        transport.blur_interface = 'blur'
        transport._request = MagicMock(return_value=9)
        return transport

    def test_standard_region_is_bounded_and_empty_region_destroys_effect(self):
        transport = self.transport()
        transport._apply()
        calls = transport._request.call_args_list
        additions = [c for c in calls if c.args == (9, 1) and len(c.kwargs.get('arguments', [])) == 4]
        self.assertEqual([[a.i for a in c.kwargs['arguments']] for c in additions], [[10, 20, 100, 200]])
        self.assertTrue(any(c.args[:2] == (1, 1) for c in calls))
        before = transport._request.call_count
        transport._apply()
        self.assertEqual(transport._request.call_count, before)
        transport._request.reset_mock()
        transport._desired = ()
        transport._apply()
        transport._request.assert_called_once_with(9, 0, destroy=True)
        self.assertIsNone(transport.blur)

    def test_legacy_empty_region_unsets_without_creating_region(self):
        transport = self.transport(standard=False)
        transport._desired = ()
        transport._apply()
        transport._request.assert_called_once()
        call = transport._request.call_args
        self.assertEqual(call.args, (1, 1))
        self.assertEqual(call.kwargs['arguments'][0].o, 3)

    def test_disabled_capability_and_missing_native_symbols_fall_back(self):
        transport = self.transport()
        transport._capabilities(None, 1, 0)
        transport._apply()
        transport._request.assert_not_called()
        self.assertIn('disabled', transport.status)
        self.assertFalse(transport._supports_blur)
        # Real QObject is needed only as the timer's parent.
        from PyQt6.QtWidgets import QWidget
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        with patch('ui.wayland_blur.QGuiApplication.platformName', return_value='wayland'), patch.object(WaylandBlur, '_load_native', side_effect=AttributeError('symbol missing')):
            fallback = WaylandBlur(parent)
        self.assertIn('symbol missing', fallback.status)
        fallback.update(None, [(0, 0, 50, 50)])
        self.assertFalse(fallback.timer.isActive())

    def test_detach_releases_before_forgetting_surface(self):
        transport = self.transport()
        transport.blur = 9
        transport.detach()
        transport._request.assert_called_once_with(9, 0, destroy=True)
        self.assertIsNone(transport.surface)

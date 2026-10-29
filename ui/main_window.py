"""Frameless Glassmorphic HUD Window with multi-capsule management."""

from __future__ import annotations

from typing import List, Optional

try:
    from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt
    from PyQt6.QtGui import QCursor, QGuiApplication, QMouseEvent, QRegion
    from PyQt6.QtWidgets import QWidget
except ImportError:
    pass

from core.command_loader import CommandCatalog
from core.config import Config
from ui.capsule import CAskCapsule


class MainWindow(QWidget):
    """Main Glassmorphism HUD hosting up to 3 side-by-side CAsk capsules."""

    STATE_INPUT = 0
    STATE_LOADING = 1
    STATE_RESULT = 2

    GAP = 20
    SCREEN_MARGIN = 24
    MAX_CAPSULES = 3

    def __init__(
        self,
        config: Config,
        catalog: CommandCatalog,
        initial_input: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.catalog = catalog
        self.initial_input = initial_input
        self.capsules: List[CAskCapsule] = []

        self._setup_window_properties()

        # Create initial capsule W1
        first_capsule = self._create_capsule(initial_input=self.initial_input)
        self.capsules.append(first_capsule)

        self._recompute_layout()

    # --- Backward compatibility accessors for tests / single-capsule calls ---
    @property
    def primary_capsule(self) -> Optional[CAskCapsule]:
        return self.capsules[0] if self.capsules else None

    @property
    def container(self):
        return self.primary_capsule.container if self.primary_capsule else None

    @property
    def stack(self):
        return self.primary_capsule.stack if self.primary_capsule else None

    @property
    def input_bar(self):
        return self.primary_capsule.input_bar if self.primary_capsule else None

    @property
    def loading_widget(self):
        return self.primary_capsule.loading_widget if self.primary_capsule else None

    @property
    def result_view(self):
        return self.primary_capsule.result_view if self.primary_capsule else None

    def _setup_window_properties(self) -> None:
        """Configure frameless, translucent, always-on-top window flags with IME support."""
        self.setWindowTitle("CAsk")
        self.setObjectName("CAskHUD")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setProperty("kwin_blur", True)

    def _get_target_screen(self):
        """Identify the screen under current mouse pointer."""
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if not screen:
            screen = QGuiApplication.primaryScreen()
        return screen

    def _create_capsule(self, initial_input: str = "") -> CAskCapsule:
        """Instantiate a new CAskCapsule and connect its lifecycle signals."""
        capsule = CAskCapsule(
            config=self.config,
            catalog=self.catalog,
            initial_input=initial_input,
            parent=self,
        )
        capsule.close_requested.connect(self._handle_capsule_close)
        capsule.size_changed.connect(lambda _: self._recompute_layout())
        capsule.state_changed.connect(lambda *_: self._recompute_layout())
        capsule.show()
        return capsule

    def handle_external_launch(self, initial_input: str = "") -> None:
        """Launch another capsule (up to 3) or focus newest active capsule."""
        self.show()
        try:
            self.raise_()
        except Exception:
            pass
        self.activateWindow()

        if len(self.capsules) < self.MAX_CAPSULES:
            new_capsule = self._create_capsule(initial_input=initial_input)
            self.capsules.append(new_capsule)
            self._recompute_layout()
            if new_capsule.state == CAskCapsule.STATE_INPUT:
                new_capsule.input_bar.setFocus()
        else:
            # Already at maximum (3 capsules); focus newest
            active_capsule = self.capsules[-1]
            if initial_input and active_capsule.state == CAskCapsule.STATE_INPUT:
                active_capsule.input_bar.setText(initial_input)
            if active_capsule.state == CAskCapsule.STATE_INPUT:
                active_capsule.input_bar.setFocus()

    def _handle_capsule_close(self, capsule: CAskCapsule) -> None:
        """Close an individual capsule and recompute layout for remaining capsules."""
        if capsule in self.capsules:
            self.capsules.remove(capsule)
            capsule.setParent(None)
            capsule.deleteLater()

        if not self.capsules:
            self.close()
        else:
            self._recompute_layout()

    def _calculate_slot_geometries(
        self,
        screen_geo: QRect,
    ) -> List[tuple[CAskCapsule, int, int, int, int]]:
        """Calculate layout coordinates for 1, 2, or 3 concurrent capsules.

        Layout Rules:
        - 1 Capsule (W1):
            Preserved centered horizontally & vertically.
        - 2 Capsules (W1, W2):
            Horizontal side-by-side, equal widths, occupying 2/3 of screen width.
            W1 on left, W2 on right.
        - 3 Capsules (W1, W2, W3):
            Horizontal side-by-side, full screen width with ratio 30:40:30.
            W3 on left (30%), W1 in center (40%), W2 on right (30%).
        """
        n = len(self.capsules)
        if n == 0:
            return []

        sw = screen_geo.width()
        sh = screen_geo.height()
        sx = screen_geo.x()
        sy = screen_geo.y()

        layout_results: List[tuple[CAskCapsule, int, int, int, int]] = []

        if n == 1:
            capsule = self.capsules[0]
            target_w = 760 if capsule.state == CAskCapsule.STATE_RESULT else 600
            ideal_h = capsule.calculate_ideal_height(
                available_width=target_w,
                max_available_height=sh - 80,
            )
            x = sx + (sw - target_w) // 2
            y = sy + (sh - ideal_h) // 2
            layout_results.append((capsule, x, y, target_w, ideal_h))

        elif n == 2:
            w1 = self.capsules[0]
            w2 = self.capsules[1]
            total_w = int(sw * 2 / 3)
            card_w = (total_w - self.GAP) // 2
            x_start = sx + (sw - total_w) // 2

            # Left card (W1)
            h1 = w1.calculate_ideal_height(available_width=card_w, max_available_height=sh - 80)
            y1 = sy + (sh - h1) // 2
            layout_results.append((w1, x_start, y1, card_w, h1))

            # Right card (W2)
            x2 = x_start + card_w + self.GAP
            h2 = w2.calculate_ideal_height(available_width=card_w, max_available_height=sh - 80)
            y2 = sy + (sh - h2) // 2
            layout_results.append((w2, x2, y2, card_w, h2))

        elif n >= 3:
            w1 = self.capsules[0]
            w2 = self.capsules[1]
            w3 = self.capsules[2]

            total_avail_w = sw - (self.SCREEN_MARGIN * 2) - (self.GAP * 2)
            w_left = int(total_avail_w * 0.30)
            w_right = int(total_avail_w * 0.30)
            w_center = total_avail_w - w_left - w_right

            # Left card: W3 (30%)
            x_left = sx + self.SCREEN_MARGIN
            h3 = w3.calculate_ideal_height(available_width=w_left, max_available_height=sh - 80)
            y3 = sy + (sh - h3) // 2
            layout_results.append((w3, x_left, y3, w_left, h3))

            # Center card: W1 (40%)
            x_center = x_left + w_left + self.GAP
            h1 = w1.calculate_ideal_height(available_width=w_center, max_available_height=sh - 80)
            y1 = sy + (sh - h1) // 2
            layout_results.append((w1, x_center, y1, w_center, h1))

            # Right card: W2 (30%)
            x_right = x_center + w_center + self.GAP
            h2 = w2.calculate_ideal_height(available_width=w_right, max_available_height=sh - 80)
            y2 = sy + (sh - h2) // 2
            layout_results.append((w2, x_right, y2, w_right, h2))

        return layout_results

    def _recompute_layout(self) -> None:
        """Position capsules according to active slot geometry and update click mask."""
        if not self.capsules:
            return

        screen = self._get_target_screen()
        screen_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        # Cover target screen area
        self.setGeometry(screen_geo)

        slots = self._calculate_slot_geometries(screen_geo)
        total_mask = QRegion()

        for capsule, x, y, w, h in slots:
            # Coordinates relative to MainWindow (which starts at screen_geo.topLeft())
            rel_x = x - screen_geo.x()
            rel_y = y - screen_geo.y()
            capsule.setGeometry(rel_x, rel_y, w, h)
            capsule.container.setFixedSize(w, h)
            # Expand mask slightly to encompass shadow / glow
            card_rect = QRect(rel_x - 12, rel_y - 12, w + 24, h + 24)
            total_mask = total_mask.united(QRegion(card_rect))

        # Set transparent click-through mask
        try:
            self.setMask(total_mask)
        except Exception:
            pass

    def _switch_state(self, state: int, target_width: int = 600, target_height: int = 50) -> None:
        """Backward-compatible state switch on primary capsule."""
        if self.primary_capsule:
            self.primary_capsule.switch_state(state)
            self._recompute_layout()

    def _handle_submit(self, text: str) -> None:
        """Backward-compatible submit on primary capsule."""
        if self.primary_capsule:
            self.primary_capsule._handle_submit(text)

    def _show_result(self, badge: str, content: str, is_error: bool = False) -> None:
        """Backward-compatible result show on primary capsule."""
        if self.primary_capsule:
            self.primary_capsule._show_result(badge, content, is_error)

    def changeEvent(self, event) -> None:
        """Detect window focus loss for click-outside dismissal."""
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                # Check for open completer popups in any capsule
                for c in self.capsules:
                    completer = c.input_bar.completer()
                    if completer and completer.popup() and completer.popup().isVisible():
                        super().changeEvent(event)
                        return

                # Dismiss unpinned capsules in RESULT state
                to_remove = []
                for c in list(self.capsules):
                    if c.state == CAskCapsule.STATE_RESULT and not c.is_pinned:
                        to_remove.append(c)

                for c in to_remove:
                    self._handle_capsule_close(c)

        super().changeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Dismiss unpinned result capsules when clicking empty masked areas."""
        click_pos = event.pos()
        clicked_capsule = None
        for c in self.capsules:
            if c.geometry().contains(click_pos):
                clicked_capsule = c
                break

        if not clicked_capsule:
            to_remove = [
                c for c in list(self.capsules)
                if c.state == CAskCapsule.STATE_RESULT and not c.is_pinned
            ]
            for c in to_remove:
                self._handle_capsule_close(c)

        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        """Handle Esc and Enter keys, honoring pin status."""
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Find focused capsule
            focused_capsule = None
            for c in self.capsules:
                if c.hasFocus() or c.isAncestorOf(self.focusWidget()):
                    focused_capsule = c
                    break

            target = focused_capsule or (self.capsules[-1] if self.capsules else None)
            if target:
                if target.is_pinned:
                    # Pinned capsule ignores Esc/Enter
                    event.accept()
                    return
                # Unpinned capsule is dismissed
                self._handle_capsule_close(target)
                event.accept()
                return

        super().keyPressEvent(event)

"""Frameless Glassmorphic HUD Window with multi-capsule management."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

try:
    from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer
    from PyQt6.QtGui import QCursor, QGuiApplication, QIcon, QKeyEvent, QMouseEvent, QRegion
    from PyQt6.QtWidgets import QFrame, QLineEdit, QTextEdit, QWidget
except ImportError:
    pass

from core.command_loader import CommandCatalog
from core.config import Config
from ui.capsule import CAskCapsule


class DropGhostIndicator(QFrame):
    """Visual drop target indicator during capsule dragging."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DropGhostIndicator")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()


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

        self._dragging_capsule: Optional[CAskCapsule] = None
        self._target_drop_slot: Optional[int] = None

        self._setup_window_properties()

        # Ghost indicator for drag & drop visual feedback
        self.ghost_indicator = DropGhostIndicator(self)

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

        logo_path = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
        if logo_path.is_file():
            self.setWindowIcon(QIcon(str(logo_path)))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setProperty("kwin_blur", True)
        self._is_always_on_top: bool = True

    def _set_kwin_layer(self, keep_above: bool) -> bool:
        """Dynamically switch KWin window layer between Keep Above and Keep Below via DBus scripting."""
        target_above = "true" if keep_above else "false"
        target_below = "false" if keep_above else "true"
        js_code = f"""
        var windows = workspace.windowList();
        for (var i = 0; i < windows.length; i++) {{
            var w = windows[i];
            if (w.caption === "CAsk" || w.resourceClass === "cask" || w.resourceName === "cask" || w.desktopFileName === "cask") {{
                w.keepAbove = {target_above};
                w.keepBelow = {target_below};
            }}
        }}
        """
        f_path = ""
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                f.write(js_code)
                f_path = f.name
            out = subprocess.check_output(
                f"busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting loadScript s \"{f_path}\"",
                shell=True,
                stderr=subprocess.DEVNULL,
            ).decode()
            script_num = out.strip().split()[-1]
            subprocess.run(
                f"busctl --user call org.kde.KWin /Scripting/Script{script_num} org.kde.kwin.Script run",
                shell=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                f"busctl --user call org.kde.KWin /Scripting/Script{script_num} org.kde.kwin.Script stop",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False
        finally:
            if f_path and os.path.exists(f_path):
                try:
                    os.unlink(f_path)
                except OSError:
                    pass

    def _apply_initial_layer(self, retries: int = 5) -> None:
        """Ensure initial Always-On-Top / Keep Above status is enforced by KWin on Wayland."""
        if not getattr(self, "_is_always_on_top", True):
            return

        self._set_kwin_layer(True)
        if retries > 0:
            delays = [40, 80, 160, 300, 500]
            delay = delays[5 - retries] if (5 - retries) < len(delays) else 100
            QTimer.singleShot(delay, lambda: self._apply_initial_layer(retries - 1))

    def showEvent(self, event) -> None:
        """Handle window display event and enforce compositor layer policies."""
        super().showEvent(event)
        self._apply_initial_layer()

    def toggle_always_on_top(self) -> bool:
        """Toggle window between Keep Above (on-top) and Keep Below (behind other windows)."""
        self._is_always_on_top = not getattr(self, "_is_always_on_top", True)

        # 1. Primary path for KWin/KDE: switch layer directly without surface recreation or fade
        if self._set_kwin_layer(self._is_always_on_top):
            if self._is_always_on_top:
                try:
                    self.raise_()
                except Exception:
                    pass
                self.activateWindow()
            return self._is_always_on_top

        # 2. Universal fallback for other compositors/X11
        if self._is_always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnBottomHint, False)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnBottomHint, True)

        self.show()
        self._recompute_layout()
        if self._is_always_on_top:
            try:
                self.raise_()
            except Exception:
                pass
            self.activateWindow()
        else:
            try:
                self.lower()
            except Exception:
                pass
        return self._is_always_on_top

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
        capsule.reorder_requested.connect(self.swap_capsule_slot)
        capsule.toggle_on_top_requested.connect(self.toggle_always_on_top)
        capsule.drag_started.connect(self._handle_capsule_drag_start)
        capsule.drag_moved.connect(self._handle_capsule_drag_move)
        capsule.drag_ended.connect(self._handle_capsule_drag_end)
        capsule.show()
        return capsule

    def handle_external_launch(self, initial_input: str = "") -> None:
        """Launch another capsule (up to 3) or focus newest active capsule."""
        if not getattr(self, "_is_always_on_top", True):
            self.toggle_always_on_top()
        else:
            self._apply_initial_layer(retries=2)
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
            if hasattr(capsule, "stop_worker"):
                capsule.stop_worker()
            self.capsules.remove(capsule)
            capsule.setParent(None)
            capsule.deleteLater()

        if not self.capsules:
            self.close()
        else:
            self._recompute_layout()

    def _get_slot_capsules(self) -> List[CAskCapsule]:
        """Return capsules mapped to left-to-right visual slot order."""
        n = len(self.capsules)
        if n == 0:
            return []
        if n == 1:
            return [self.capsules[0]]
        if n == 2:
            return [self.capsules[0], self.capsules[1]]
        # 3 capsules: Slot 0 = capsules[2], Slot 1 = capsules[0], Slot 2 = capsules[1]
        return [self.capsules[2], self.capsules[0], self.capsules[1]]

    def _set_slot_capsules(self, slot_capsules: List[CAskCapsule]) -> None:
        """Map visual left-to-right ordered capsules back into self.capsules."""
        n = len(slot_capsules)
        if n <= 2:
            self.capsules = list(slot_capsules)
        else:
            # slot_capsules: [Slot 0, Slot 1, Slot 2]
            # self.capsules: [W1 (center/slot 1), W2 (right/slot 2), W3 (left/slot 0)]
            self.capsules = [slot_capsules[1], slot_capsules[2], slot_capsules[0]]

    def get_capsule_slot_index(self, capsule: CAskCapsule) -> int:
        """Return the current visual 0-indexed slot (left to right) of a capsule."""
        slot_caps = self._get_slot_capsules()
        if capsule in slot_caps:
            return slot_caps.index(capsule)
        return -1

    def swap_capsule_slot(self, capsule: CAskCapsule, direction: int) -> bool:
        """Swap capsule with its neighbor left (-1) or right (+1)."""
        slot_caps = self._get_slot_capsules()
        if capsule not in slot_caps:
            return False

        curr_idx = slot_caps.index(capsule)
        target_idx = curr_idx + direction

        if 0 <= target_idx < len(slot_caps):
            slot_caps[curr_idx], slot_caps[target_idx] = slot_caps[target_idx], slot_caps[curr_idx]
            self._set_slot_capsules(slot_caps)
            self._recompute_layout()
            # Retain focus on moved capsule
            if capsule.state == CAskCapsule.STATE_INPUT:
                capsule.input_bar.setFocus()
            elif capsule.state == CAskCapsule.STATE_RESULT:
                capsule.result_view.text_browser.setFocus()
            return True
        return False

    def _handle_capsule_drag_start(self, capsule: CAskCapsule, global_pos: QPoint) -> None:
        """Initiate drag reorder."""
        if len(self.capsules) <= 1:
            return
        self._dragging_capsule = capsule
        self._update_ghost_indicator(global_pos)

    def _handle_capsule_drag_move(self, capsule: CAskCapsule, global_pos: QPoint) -> None:
        """Track drag motion and update target slot ghost indicator."""
        if self._dragging_capsule is not capsule:
            return
        self._update_ghost_indicator(global_pos)

    def _handle_capsule_drag_end(self, capsule: CAskCapsule, global_pos: QPoint) -> None:
        """Complete drag reorder and re-slot."""
        if self._dragging_capsule is not capsule:
            return

        target_slot = self._target_drop_slot
        self.ghost_indicator.hide()
        self._dragging_capsule = None
        self._target_drop_slot = None

        if target_slot is not None:
            slot_caps = self._get_slot_capsules()
            curr_slot = slot_caps.index(capsule)
            if curr_slot != target_slot:
                slot_caps.pop(curr_slot)
                slot_caps.insert(target_slot, capsule)
                self._set_slot_capsules(slot_caps)
                self._recompute_layout()
                if capsule.state == CAskCapsule.STATE_RESULT:
                    capsule.result_view.text_browser.setFocus()
                elif capsule.state == CAskCapsule.STATE_INPUT:
                    capsule.input_bar.setFocus()

    def _update_ghost_indicator(self, global_pos: QPoint) -> None:
        """Position drop ghost indicator over the candidate target slot."""
        screen = self._get_target_screen()
        screen_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        slots = self._calculate_slot_geometries(screen_geo)

        if not slots or not self._dragging_capsule:
            self.ghost_indicator.hide()
            return

        cursor_x = global_pos.x()
        best_slot_idx = 0
        min_dist = float("inf")

        for idx, (cap, x, y, w, h) in enumerate(slots):
            center_x = x + w // 2
            dist = abs(cursor_x - center_x)
            if dist < min_dist:
                min_dist = dist
                best_slot_idx = idx

        self._target_drop_slot = best_slot_idx
        _, target_x, target_y, target_w, target_h = slots[best_slot_idx]
        rel_x = target_x - screen_geo.x()
        rel_y = target_y - screen_geo.y()
        self.ghost_indicator.setGeometry(rel_x, rel_y, target_w, target_h)
        self.ghost_indicator.show()
        self.ghost_indicator.raise_()

    def _calculate_slot_geometries(
        self,
        screen_geo: QRect,
    ) -> List[tuple[CAskCapsule, int, int, int, int]]:
        """Calculate layout coordinates for 1, 2, or 3 concurrent capsules.

        Layout Rules:
        - 1 Capsule (W1):
            Preserved centered horizontally & vertically.
        - 2 Capsules (W1, W2):
            Horizontal side-by-side, equal widths, occupying 80% of screen width.
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
            target_w = 760 if capsule.state == CAskCapsule.STATE_RESULT else max(400, int(sw * 0.35))
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
            total_w = int(sw * 0.80)
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
            card_rect = QRect(rel_x, rel_y, w, h)
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
        """Handle window reordering shortcuts (Shift+Left/Right), Esc, and Enter."""
        key = event.key()
        modifiers = event.modifiers()

        # Window reorder shortcuts: Alt + Left / Alt + Right
        if modifiers & Qt.KeyboardModifier.AltModifier:
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                # Find focused capsule
                focused_capsule = None
                for c in self.capsules:
                    if c.hasFocus() or c.isAncestorOf(self.focusWidget()):
                        focused_capsule = c
                        break

                target = focused_capsule or (self.capsules[0] if self.capsules else None)
                if target:
                    direction = -1 if key == Qt.Key.Key_Left else 1
                    if self.swap_capsule_slot(target, direction):
                        event.accept()
                        return
            elif key == Qt.Key.Key_H:
                self.toggle_always_on_top()
                event.accept()
                return

        # Enter / Return: Focus active input bar if not already typing in an editable input
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focus_widget = self.focusWidget()
            is_editable = (isinstance(focus_widget, QLineEdit) and not focus_widget.isReadOnly()) or (
                isinstance(focus_widget, QTextEdit) and not focus_widget.isReadOnly()
            )
            if not is_editable:
                focused_capsule = None
                for c in self.capsules:
                    if c.hasFocus() or c.isAncestorOf(focus_widget):
                        focused_capsule = c
                        break
                target = focused_capsule or (self.capsules[-1] if self.capsules else None)
                if target:
                    if target.state == CAskCapsule.STATE_RESULT:
                        if target.result_view and target.result_view.followup_input.isEnabled():
                            target.result_view.followup_input.setFocus()
                            event.accept()
                            return
                    elif target.state == CAskCapsule.STATE_INPUT:
                        target.input_bar.setFocus()
                        event.accept()
                        return

        if key == Qt.Key.Key_Escape:
            # Find focused capsule
            focused_capsule = None
            for c in self.capsules:
                if c.hasFocus() or c.isAncestorOf(self.focusWidget()):
                    focused_capsule = c
                    break

            target = focused_capsule or (self.capsules[-1] if self.capsules else None)
            if target:
                if target.is_pinned:
                    # Pinned capsule ignores Esc
                    event.accept()
                    return
                # Unpinned capsule is dismissed
                self._handle_capsule_close(target)
                event.accept()
                return

        super().keyPressEvent(event)

"""Capture real compositor blur with placeholder data and a controlled background.

Run from the repository root on KDE/Wayland:
    QT_QPA_PLATFORM=wayland python3 resources/verify-desktop-blur.py

Requires Spectacle. Writes only to the output directory (ignored by Git by default).
No user configuration, API credentials, or provider network requests are used.
The generated background and HUD close after capture. Compare the on/off images:
background stripes must soften only behind rounded capsules; controls stay sharp.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QProcess, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QApplication, QWidget

from core.command_loader import CommandCatalog
from core.config import Config
from core.provider_api import default_profile
from core.provider_config import Provider
from ui.app import load_stylesheet
from ui.main_window import MainWindow


class Pattern(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#d7dde8'))
        for x in range(0, self.width(), 8):
            painter.fillRect(x, 0, 4, self.height(), QColor('#303749'))
        painter.setFont(QFont('DejaVu Sans', 18))
        painter.setPen(QColor('white'))
        for y in range(30, self.height(), 55):
            painter.drawText(20, y, 'CAsk native backdrop verification — sharp background stripes')


class Verification:
    def __init__(self, app, output):
        self.app = app
        self.output = output
        self.failed = False
        self.attempts = 0
        self.capture_process = None
        self.config_directory = tempfile.TemporaryDirectory(prefix='cask-blur-')
        self.background = Pattern()
        self.background.setWindowTitle('Backdrop verification background')
        self.background.showFullScreen()
        models = [default_profile('gpt-6.1-sol', 'Sol ' + name) for name in ('Medium', 'High', 'Low', 'Review')]
        provider = Provider('demo', 'OpenAI Personal', 'openai', 'openai_responses',
                            'https://example.invalid/v1', '', models=models, active_model_id=models[0].id)
        self.window = MainWindow(Config(config_dir=Path(self.config_directory.name),
                                        providers=(provider,), selected_provider_id=provider.id), CommandCatalog({}))
        QTimer.singleShot(500, self.start)
        QTimer.singleShot(30000, self.timeout)

    def start(self):
        self.window.show()
        self.window.primary_capsule.switch_state(3)
        self.wait_for_blur()

    def wait_for_blur(self):
        backend = self.window._backdrop_blur
        if backend._applied and backend._applied == tuple(self.window._blur_rectangles):
            print(backend.status, flush=True)
            QTimer.singleShot(500, lambda: self.capture('settings-native-blur-on', self.disable))
        elif self.attempts < 50:
            self.attempts += 1
            QTimer.singleShot(100, self.wait_for_blur)
        else:
            self.fail('Native blur unavailable: ' + backend.status)

    def capture(self, name, next_step):
        process = QProcess(self.app)
        self.capture_process = process
        path = self.output / (name + '.png')
        geometry = {
            'backend': self.window._backdrop_blur.status,
            'device_pixel_ratio': self.window.devicePixelRatioF(),
            'rectangles': self.window._blur_rectangles,
            'capsules': [[c.x(), c.y(), c.width(), c.height()] for c in self.window.capsules],
        }
        (self.output / (name + '.json')).write_text(json.dumps(geometry, indent=2) + '\n')

        def finished(code, status):
            if code or status != QProcess.ExitStatus.NormalExit or not path.exists():
                self.fail('Spectacle capture failed: ' + process.readAllStandardError().data().decode(errors='replace'))
                return
            print(path, flush=True)
            process.deleteLater()
            self.capture_process = None
            QTimer.singleShot(250, next_step)

        process.finished.connect(finished)
        process.errorOccurred.connect(lambda error: self.fail('Spectacle failed to start'))
        process.start(shutil.which('spectacle'), ['-b', '-n', '-f', '-o', str(path)])

    def disable(self):
        self.window._backdrop_blur.update(self.window.windowHandle(), [])
        self.window.update()
        QTimer.singleShot(600, lambda: self.capture('settings-native-blur-off', self.multiple))

    def multiple(self):
        self.window.primary_capsule.switch_state(0)
        self.window.handle_external_launch()
        self.window.handle_external_launch()
        for index, capsule in enumerate(self.window.capsules):
            capsule.input_bar.setText(f'Capsule {index + 1}: background blurs, controls stay sharp.')
        QTimer.singleShot(600, lambda: self.capture('three-capsules-native-blur', self.restore))

    def restore(self):
        self.window._handle_capsule_close(self.window.capsules[-1])
        self.window._handle_capsule_close(self.window.capsules[-1])
        self.window.hide()
        self.window.show()
        self.window._update_backdrop()
        QTimer.singleShot(500, lambda: self.capture('restored-capsule-native-blur', self.finish))

    def fail(self, reason):
        print(reason, file=sys.stderr, flush=True)
        self.failed = True
        self.finish()

    def timeout(self):
        self.fail('Desktop verification timed out')

    def finish(self):
        if self.capture_process:
            self.capture_process.kill()
        self.window.close()
        self.background.close()
        self.config_directory.cleanup()
        self.app.exit(1 if self.failed else 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).parent / 'bug_screenshots' / 'blur-verification')
    args = parser.parse_args()
    if not shutil.which('spectacle'):
        parser.error('Spectacle is required for real compositor screenshots')
    app = QApplication([])
    if app.platformName() != 'wayland':
        parser.error('Run with QT_QPA_PLATFORM=wayland in a Wayland desktop session')
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(load_stylesheet())
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    verification = Verification(app, output)
    raise SystemExit(app.exec())

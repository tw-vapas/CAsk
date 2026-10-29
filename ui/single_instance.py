"""Single instance lock and IPC manager for CAsk HUD."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import Optional

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
except ImportError:
    pass


class SingleInstanceManager:
    """Ensures only a single instance of CAsk GUI runs at any given time.

    If an instance is already active, subsequent launches send an activation
    message to bring the existing window to the front and exit cleanly.
    """

    def __init__(self, app_name: str = "cask") -> None:
        self.server_name = f"{app_name}_instance_{os.getuid()}"
        self.server: Optional[QLocalServer] = None
        self._lock_file: Optional[Path] = None
        self._lock_fd: Optional[int] = None

    def try_acquire(self, initial_input: str = "") -> bool:
        """Attempt to acquire primary instance lock.

        Returns:
            True if this process is the primary instance.
            False if another instance is already running (activation requested).
        """
        runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
        self._lock_file = runtime_dir / f"cask_{os.getuid()}.lock"

        try:
            self._lock_fd = os.open(
                str(self._lock_file),
                os.O_CREAT | os.O_RDWR,
                0o600,
            )
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            # Another instance holds the file lock.
            # Notify existing instance via QLocalSocket to activate window.
            self._notify_running_instance(initial_input)
            return False

        # File lock acquired. Now initialize QLocalServer for incoming activations.
        try:
            QLocalServer.removeServer(self.server_name)
            self.server = QLocalServer()
            if not self.server.listen(self.server_name):
                QLocalServer.removeServer(self.server_name)
                self.server.listen(self.server_name)
        except Exception:
            pass

        return True

    def _notify_running_instance(self, initial_input: str = "") -> None:
        """Send IPC command to existing instance to bring it to foreground."""
        try:
            socket = QLocalSocket()
            socket.connectToServer(self.server_name)
            if socket.waitForConnected(300):
                payload = f"ACTIVATE:{initial_input}\n".encode("utf-8")
                socket.write(payload)
                socket.waitForBytesWritten(500)
                socket.disconnectFromServer()
        except Exception:
            pass

    def register_window(self, window) -> None:
        """Connect incoming activation signals to window focus and raise."""
        if not self.server:
            return

        def _on_new_connection() -> None:
            sock = self.server.nextPendingConnection()
            if not sock:
                return
            if sock.waitForReadyRead(500):
                try:
                    data = sock.readAll().data().decode("utf-8", errors="ignore")
                    if data.startswith("ACTIVATE:"):
                        query = data[len("ACTIVATE:"):].strip()
                        if query and hasattr(window, "input_bar"):
                            if window.stack.currentIndex() == window.STATE_INPUT:
                                window.input_bar.setText(query)
                except Exception:
                    pass
            try:
                sock.disconnectFromServer()
            except Exception:
                pass

            # Bring window to front and activate
            window.show()
            window.raise_()
            window.activateWindow()
            if hasattr(window, "input_bar") and window.stack.currentIndex() == window.STATE_INPUT:
                window.input_bar.setFocus()

        self.server.newConnection.connect(_on_new_connection)

    def cleanup(self) -> None:
        """Release IPC server and file lock."""
        if self.server:
            try:
                self.server.close()
            except Exception:
                pass
            try:
                QLocalServer.removeServer(self.server_name)
            except Exception:
                pass
            self.server = None

        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            except Exception:
                pass
            self._lock_fd = None

        if self._lock_file and self._lock_file.exists():
            try:
                self._lock_file.unlink()
            except Exception:
                pass

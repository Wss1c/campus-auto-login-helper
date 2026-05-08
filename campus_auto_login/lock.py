from __future__ import annotations

import socket
import threading
from collections.abc import Callable


class SingleInstanceLock:
    def __init__(self, port: int = 48173) -> None:
        self.port = port
        self._socket: socket.socket | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def acquire(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("127.0.0.1", self.port))
            sock.listen(1)
            sock.settimeout(1.0)
        except OSError:
            sock.close()
            return False
        self._socket = sock
        return True

    def start_server(self, command_handler: Callable[[str], None]) -> None:
        if self._socket is None or self._thread is not None:
            return

        def serve() -> None:
            while not self._stop.is_set():
                try:
                    conn, _ = self._socket.accept()
                except TimeoutError:
                    continue
                except OSError:
                    break
                with conn:
                    try:
                        command = conn.recv(128).decode("utf-8", errors="ignore")
                    except OSError:
                        command = ""
                if command:
                    command_handler(command.strip())
                    try:
                        conn.sendall(b"ok")
                    except OSError:
                        pass

        self._thread = threading.Thread(
            target=serve,
            name="SingleInstanceIpc",
            daemon=True,
        )
        self._thread.start()

    @classmethod
    def request_show(cls, port: int = 48173) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.5) as sock:
                sock.sendall(b"show")
                sock.settimeout(1.5)
                return sock.recv(16) == b"ok"
        except OSError:
            return False

    def release(self) -> None:
        self._stop.set()
        if self._socket is not None:
            self._socket.close()
            self._socket = None

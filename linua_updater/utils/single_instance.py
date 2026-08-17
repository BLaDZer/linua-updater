import socket
from typing import Optional

DEFAULT_LOCK_PORT = 12345
LOCK_PORT_RANGE = 10
BIND_HOST = "127.0.0.1"
SOCKET_PROBE_TIMEOUT = 0.5


class SingleInstanceLock:
    def __init__(self, port: int = DEFAULT_LOCK_PORT) -> None:
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.is_locked = False

    def acquire(self) -> bool:
        for port in range(self.port, self.port + LOCK_PORT_RANGE):
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((BIND_HOST, port))
                sock.listen(1)
                self.socket = sock
                self.port = port
                self.is_locked = True
                return True
            except OSError:
                if sock is not None:
                    sock.close()
                continue
        return False

    def release(self) -> None:
        if self.socket:
            self.socket.close()
            self.is_locked = False

    @staticmethod
    def is_already_running(port: int = DEFAULT_LOCK_PORT) -> bool:
        for test_port in range(port, port + LOCK_PORT_RANGE):
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(SOCKET_PROBE_TIMEOUT)
                test_socket.connect((BIND_HOST, test_port))
                test_socket.close()
                return True
            except:
                continue
        return False

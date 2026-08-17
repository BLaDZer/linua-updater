import socket


class SingleInstanceLock:
    def __init__(self, port=12345):
        self.port = port
        self.socket = None
        self.is_locked = False

    def acquire(self):
        for port in range(self.port, self.port + 10):
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port))
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

    def release(self):
        if self.socket:
            self.socket.close()
            self.is_locked = False

    @staticmethod
    def is_already_running(port=12345):
        for test_port in range(port, port + 10):
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)
                test_socket.connect(("127.0.0.1", test_port))
                test_socket.close()
                return True
            except:
                continue
        return False

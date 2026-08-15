import socket

import pytest

from linua_updater.utils.single_instance import SingleInstanceLock

BASE_PORT = 55555


@pytest.fixture
def lock():
    return SingleInstanceLock(port=BASE_PORT)


def test_acquire_release_roundtrip(lock):
    assert lock.acquire()
    assert lock.is_locked
    assert lock.socket is not None
    lock.release()
    assert not lock.is_locked
    assert lock.socket.fileno() == -1


def test_acquire_after_release_reuses(lock):
    assert lock.acquire()
    port = lock.port
    lock.release()
    assert lock.acquire()
    assert lock.is_locked
    assert lock.port == port
    lock.release()


def test_is_already_running_true_while_held(lock):
    assert lock.acquire()
    assert SingleInstanceLock.is_already_running(port=BASE_PORT)
    lock.release()


def test_is_already_running_false_when_free():
    assert not SingleInstanceLock.is_already_running(port=BASE_PORT)


def test_acquire_falls_through_port_range(lock, monkeypatch):
    failures = 3
    real_bind = socket.socket.bind

    def flaky_bind(self, address):
        nonlocal failures
        if failures > 0:
            failures -= 1
            raise OSError("port busy")
        return real_bind(self, address)

    monkeypatch.setattr(socket.socket, "bind", flaky_bind)
    assert lock.acquire()
    assert lock.port > BASE_PORT
    lock.release()

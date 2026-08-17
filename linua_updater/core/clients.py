import os
import re
import subprocess
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from linua_updater.constants import APP_VERSION, DEFAULT_DOWNLOAD_TIMEOUT_SEC, GB, KB, MB
from linua_updater.logging_util import ImprovedLogger
from linua_updater.utils.aria2 import Aria2Finder

PROCESS_KILL_WAIT_SEC = 2
TORRENT_STOP_TIMEOUT_SEC = 600

ARIA2_FLAG_SEED_TIME = "--seed-time=0"
ARIA2_FLAG_BT_STOP_TIMEOUT = "--bt-stop-timeout="
ARIA2_FLAG_CONTINUE = "--continue=true"
ARIA2_FLAG_ALLOW_OVERWRITE = "--allow-overwrite=true"
ARIA2_FLAG_FILE_ALLOCATION = "--file-allocation=none"
ARIA2_FLAG_CHECK_INTEGRITY = "--check-integrity=true"


def _popen_kwargs() -> Dict[str, Any]:
    """Popen kwargs hiding the console window on Windows. No-op elsewhere."""
    kwargs: Dict[str, Any] = {}
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if flag:
        kwargs["creationflags"] = flag
    return kwargs


class HTTPClient:
    """Generic HTTP transport: owns the session, headers, proxy and request verbs."""

    def __init__(
        self,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT_SEC,
        verify: bool = True,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = timeout
        self.verify = verify
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "Linua-Updater/" + APP_VERSION})

    def set_proxy(self, proxy_dict: Optional[Dict[str, str]]) -> None:
        if proxy_dict:
            self.session.proxies = proxy_dict
        else:
            self.session.proxies = {}

    def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
        proxies: Optional[Dict[str, str]] = None,
        stream: bool = False,
    ) -> requests.Response:
        return self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=self.timeout if timeout is None else timeout,
            verify=self.verify if verify is None else verify,
            proxies=proxies,
            stream=stream,
        )

    def head(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        allow_redirects: bool = True,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
        proxies: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        return self.session.head(
            url,
            params=params,
            headers=headers,
            allow_redirects=allow_redirects,
            timeout=self.timeout if timeout is None else timeout,
            verify=self.verify if verify is None else verify,
            proxies=proxies,
        )

    def post(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
        proxies: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        return self.session.post(
            url,
            params=params,
            data=data,
            json=json,
            headers=headers,
            timeout=self.timeout if timeout is None else timeout,
            verify=self.verify if verify is None else verify,
            proxies=proxies,
        )

    def get_stream(self, url: str, start_byte: int = 0, **kwargs: Any) -> requests.Response:
        headers: Dict[str, str] = dict(kwargs.pop("headers", None) or {})
        if start_byte > 0:
            headers["Range"] = f"bytes={start_byte}-"
        return self.get(url, headers=headers, stream=True, **kwargs)


class TorrentClient(ABC):
    """Abstract torrent-engine contract driving a magnet download.

    Implementations must be responsive to ``stop()``/``abort()`` from other threads:
    a blocked ``read_progress()`` must unblock once ``stop()``/``abort()`` is called.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the underlying engine is usable right now."""

    @abstractmethod
    def start(self, magnet: str, out_dir: str) -> None:
        """Begin a download; raise on failure."""

    @abstractmethod
    def read_progress(self) -> Optional[Tuple[float, int, int]]:
        """Return the next progress tick ``(pct, downloaded, total)`` or ``None`` on stream end."""

    @abstractmethod
    def stop(self) -> None:
        """Suspend the download keeping its resumable state (pause)."""

    @abstractmethod
    def abort(self) -> None:
        """Stop and reap the engine (cancel)."""

    @abstractmethod
    def wait_exit(self) -> int:
        """Block until the engine exits and return its exit code."""


class Aria2TorrentClient(TorrentClient):
    """Torrent engine backed by an ``aria2c`` subprocess."""

    def __init__(self, logger: ImprovedLogger, aria2_path: Optional[str] = None) -> None:
        self.logger = logger
        self._aria2_path = aria2_path or Aria2Finder(logger).find()
        self._process: Optional[subprocess.Popen[str]] = None
        self._command: Optional[List[str]] = None
        self._out_dir: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "aria2"

    def is_available(self) -> bool:
        path = self._aria2_path
        if path is None:
            return False
        return os.path.exists(path)

    def _build_command(self, magnet: str, out_dir: str) -> List[str]:
        assert self._aria2_path is not None  # guaranteed by is_available() before start()
        cmd = [
            self._aria2_path,
            magnet,
            "--dir=" + out_dir,
            ARIA2_FLAG_SEED_TIME,
            f"{ARIA2_FLAG_BT_STOP_TIMEOUT}{TORRENT_STOP_TIMEOUT_SEC}",
            ARIA2_FLAG_CONTINUE,
            ARIA2_FLAG_ALLOW_OVERWRITE,
            ARIA2_FLAG_FILE_ALLOCATION,
            ARIA2_FLAG_CHECK_INTEGRITY,
        ]
        return cmd

    @staticmethod
    def _parse_size_as_bytes(s: str) -> int:
        s = s.strip()
        multipliers = {
            "KiB": KB,
            "MiB": MB,
            "GiB": GB,
            "B": 1,
        }

        for unit, mult in multipliers.items():
            if s.endswith(unit):
                try:
                    return int(float(s[: -len(unit)].strip()) * mult)
                except ValueError:
                    return 0
        try:
            return int(s)
        except ValueError:
            return 0

    @staticmethod
    def _parse_stdout_line(line: str) -> Tuple[Optional[float], int, int]:
        m = re.search(r"\[(\S+?)\s+(\S+?)/(\S+?)\((\d+)%\)", line)

        if not m:
            return None, 0, 0

        progress = float(m.group(4))
        downloaded = Aria2TorrentClient._parse_size_as_bytes(m.group(2))
        total = Aria2TorrentClient._parse_size_as_bytes(m.group(3))
        return progress, downloaded, total

    def start(self, magnet: str, out_dir: str) -> None:
        os.makedirs(out_dir, exist_ok=True)
        cmd = self._build_command(magnet, out_dir)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                **_popen_kwargs(),
            )
        except Exception as e:
            raise RuntimeError(str(e)) from e
        with self._lock:
            self._process = proc
            self._command = cmd
            self._out_dir = out_dir

    def read_progress(self) -> Optional[Tuple[float, int, int]]:
        with self._lock:
            proc = self._process
        if proc is None or proc.stdout is None:
            raise RuntimeError("aria2c did not provide stdout")

        while True:
            line = proc.stdout.readline()

            if not line:
                return None

            parsed = self._parse_stdout_line(line)

            if parsed[0] is not None:
                return parsed[0], parsed[1], parsed[2]

    def stop(self) -> None:
        with self._lock:
            proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def abort(self) -> None:
        with self._lock:
            proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=PROCESS_KILL_WAIT_SEC)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        proc.wait()
                    except Exception:
                        pass
            except Exception:
                pass

    def wait_exit(self) -> int:
        with self._lock:
            proc = self._process
        if proc is None:
            return 0
        return proc.wait()


def _build_aria2_client(logger: ImprovedLogger) -> TorrentClient:
    return Aria2TorrentClient(logger)


TORRENT_CLIENTS: Dict[str, Callable[[ImprovedLogger], TorrentClient]] = {
    "aria2": _build_aria2_client,
}


def create_torrent_client(logger: ImprovedLogger, client_name: str = "aria2") -> TorrentClient:
    builder = TORRENT_CLIENTS.get(client_name)
    if builder is None:
        raise ValueError(f"Unknown torrent client: {client_name}")
    return builder(logger)

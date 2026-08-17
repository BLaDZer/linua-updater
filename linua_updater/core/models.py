import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


class CheckSums:
    def __init__(self, sha256: Optional[str] = None, sha1: Optional[str] = None, md5: Optional[str] = None) -> None:
        self._sha256: Optional[str] = sha256
        self._sha1: Optional[str] = sha1
        self._md5: Optional[str] = md5

    @classmethod
    def from_dict(cls, raw: object) -> Optional["CheckSums"]:
        if not isinstance(raw, dict):
            return None
        return cls(sha256=raw.get("sha256") or None, sha1=raw.get("sha1") or None, md5=raw.get("md5") or None)

    def getSha256(self) -> Optional[str]:
        return self._sha256

    def getSha1(self) -> Optional[str]:
        return self._sha1

    def getMd5(self) -> Optional[str]:
        return self._md5

    def get(self, alg: str) -> Optional[str]:
        if alg == "sha256":
            return self._sha256
        if alg == "sha1":
            return self._sha1
        if alg == "md5":
            return self._md5
        return None


class DownloadSource:
    def __init__(
        self,
        source_type: Optional[str],
        source: Optional[str] = None,
        parts: Optional[List["DownloadSource"]] = None,
        checksums: Optional["CheckSums"] = None,
        priority: int = 0,
    ) -> None:
        self._type: Optional[str] = source_type
        self._source: Optional[str] = source
        self._parts: List[DownloadSource] = parts if parts is not None else []
        self._checksums: Optional[CheckSums] = checksums
        self._priority: int = priority

    @classmethod
    def from_dict(cls, raw: object) -> Optional["DownloadSource"]:
        if not isinstance(raw, dict):
            return None
        source_type: Optional[str] = raw.get("type")
        if source_type not in ("url", "parts", "magnet"):
            if "parts" in raw:
                source_type = "parts"
            elif "url" in raw:
                source_type = "url"
            elif "magnet" in raw:
                source_type = "magnet"
            else:
                source_type = None
        checksums = CheckSums.from_dict(raw.get("checksum"))
        priority: int = raw.get("priority", 0)
        if priority is None or isinstance(priority, bool):
            priority = 0
        elif not isinstance(priority, int):
            try:
                priority = int(priority)
            except (TypeError, ValueError):
                priority = 0
        if source_type == "parts":
            parts: List[DownloadSource] = []
            for part in raw.get("parts") or []:
                parsed = cls.from_dict(part)
                if parsed is not None:
                    parts.append(parsed)
            return cls("parts", parts=parts, checksums=checksums, priority=priority)
        if source_type == "url":
            return cls("url", source=raw.get("url"), checksums=checksums, priority=priority)
        if source_type == "magnet":
            return cls("magnet", source=raw.get("magnet"), checksums=checksums, priority=priority)
        return cls(source_type, checksums=checksums, priority=priority)

    @classmethod
    def url(cls, url: str, checksums: Optional["CheckSums"] = None, priority: int = 0) -> "DownloadSource":
        return cls("url", source=url, checksums=checksums, priority=priority)

    @classmethod
    def magnet(cls, magnet: str, checksums: Optional["CheckSums"] = None, priority: int = 0) -> "DownloadSource":
        return cls("magnet", source=magnet, checksums=checksums, priority=priority)

    @classmethod
    def parts(
        cls, part_sources: List["DownloadSource"], checksums: Optional["CheckSums"] = None, priority: int = 0
    ) -> "DownloadSource":
        return cls("parts", parts=part_sources, checksums=checksums, priority=priority)

    def getType(self) -> Optional[str]:
        return self._type

    def getSource(self) -> Optional[str]:
        return self._source

    def getParts(self) -> List["DownloadSource"]:
        return self._parts

    def getCheckSums(self) -> Optional["CheckSums"]:
        return self._checksums

    def getPriority(self) -> int:
        return self._priority


class DLCInfo:
    def __init__(
        self,
        dlc_id: str,
        name: str,
        size: Optional[int],
        main_source: Optional["DownloadSource"],
        mirrors: List["DownloadSource"],
    ) -> None:
        self._id: str = dlc_id
        self._name: str = name
        self._size: Optional[int] = size
        self._main: Optional[DownloadSource] = main_source
        self._mirrors: List[DownloadSource] = mirrors

    @classmethod
    def from_entry(cls, dlc_id: str, raw: Dict[str, Any]) -> "DLCInfo":
        entry_checksums = CheckSums.from_dict(raw.get("checksum"))
        main: Optional[DownloadSource] = None
        if raw.get("url"):
            main = DownloadSource.url(raw["url"], checksums=entry_checksums)
        mirrors: List[DownloadSource] = []
        if raw.get("magnet"):
            mirrors.append(DownloadSource.magnet(raw["magnet"], checksums=entry_checksums))
        if raw.get("parts"):
            part_sources: List[DownloadSource] = [DownloadSource.url(p) for p in raw["parts"]]
            mirrors.append(DownloadSource.parts(part_sources, checksums=entry_checksums))
        for mirror in raw.get("mirrors") or []:
            source = DownloadSource.from_dict(mirror)
            if source is None:
                continue
            if source.getCheckSums() is None and entry_checksums is not None:
                source._checksums = entry_checksums
            mirrors.append(source)
        mirrors.sort(key=lambda s: s.getPriority(), reverse=True)
        return cls(dlc_id, raw.get("name", "Unknown"), raw.get("size"), main, mirrors)

    def getId(self) -> str:
        return self._id

    def getName(self) -> str:
        return self._name

    def getSize(self) -> Optional[int]:
        return self._size

    def getMainDownloadSource(self) -> Optional["DownloadSource"]:
        return self._main

    def getMirrors(self) -> List["DownloadSource"]:
        return self._mirrors


class InstallationStats:
    def __init__(self) -> None:
        self.lock: threading.Lock = threading.Lock()
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.downloads: Dict[str, Dict[str, float]] = {}
        self.errors: List[Dict[str, str]] = []
        self.total_dlc: Optional[int] = None
        self.total_bytes: float = 0
        self.total_time: float = 0

    def start(self) -> None:
        self.start_time = time.time()

    def record_download(self, dlc_id: str, size_bytes: float, duration_sec: float) -> None:
        speed_mbps = (size_bytes / (1024 * 1024)) / duration_sec if duration_sec > 0 else 0
        with self.lock:
            self.downloads[dlc_id] = {
                "size_mb": size_bytes / (1024 * 1024),
                "duration_sec": duration_sec,
                "speed_mbps": speed_mbps,
            }
            self.total_bytes += size_bytes
            self.total_time += duration_sec

    def record_error(self, dlc_id: str, error_msg: str) -> None:
        with self.lock:
            self.errors.append({"dlc_id": dlc_id, "error": error_msg, "timestamp": datetime.now().isoformat()})

    def finish(self) -> None:
        with self.lock:
            self.end_time = time.time()

    def get_summary(self) -> Optional[Dict[str, object]]:
        with self.lock:
            if not self.start_time or not self.end_time:
                return None
            total_duration = self.end_time - self.start_time
            avg_speed = (self.total_bytes / (1024 * 1024)) / self.total_time if self.total_time > 0 else 0
            total_dlc = self.total_dlc if self.total_dlc is not None else len(self.downloads)
            successful = len(self.downloads)
            return {
                "total_dlc": total_dlc,
                "total_size_mb": self.total_bytes / (1024 * 1024),
                "total_duration_sec": total_duration,
                "avg_speed_mbps": avg_speed,
                "successful": successful,
                "failed": total_dlc - successful,
                "errors": self.errors,
            }

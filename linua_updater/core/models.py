import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from linua_updater.constants import (
    CHECKSUM_MD5,
    CHECKSUM_SHA1,
    CHECKSUM_SHA256,
    DATABASE_DLC_KEY_CHECKSUM,
    DATABASE_DLC_KEY_MAGNET,
    DATABASE_DLC_KEY_MIRRORS,
    DATABASE_DLC_KEY_NAME,
    DATABASE_DLC_KEY_PARTS,
    DATABASE_DLC_KEY_PRIORITY,
    DATABASE_DLC_KEY_SIZE,
    DATABASE_DLC_KEY_TYPE,
    DATABASE_DLC_KEY_URL,
    MB,
)

SOURCE_TYPE_URL = "url"
SOURCE_TYPE_PARTS = "parts"
SOURCE_TYPE_MAGNET = "magnet"


class CheckSums:
    def __init__(self, sha256: Optional[str] = None, sha1: Optional[str] = None, md5: Optional[str] = None) -> None:
        self._sha256: Optional[str] = sha256
        self._sha1: Optional[str] = sha1
        self._md5: Optional[str] = md5

    @classmethod
    def from_dict(cls, raw: object) -> Optional["CheckSums"]:
        if not isinstance(raw, dict):
            return None
        return cls(
            sha256=raw.get(CHECKSUM_SHA256) or None,
            sha1=raw.get(CHECKSUM_SHA1) or None,
            md5=raw.get(CHECKSUM_MD5) or None,
        )

    def getSha256(self) -> Optional[str]:
        return self._sha256

    def getSha1(self) -> Optional[str]:
        return self._sha1

    def getMd5(self) -> Optional[str]:
        return self._md5

    def get(self, alg: str) -> Optional[str]:
        if alg == CHECKSUM_SHA256:
            return self._sha256
        if alg == CHECKSUM_SHA1:
            return self._sha1
        if alg == CHECKSUM_MD5:
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

        source_type: Optional[str] = raw.get(DATABASE_DLC_KEY_TYPE)
        if source_type not in (SOURCE_TYPE_URL, SOURCE_TYPE_PARTS, SOURCE_TYPE_MAGNET):
            if DATABASE_DLC_KEY_PARTS in raw:
                source_type = SOURCE_TYPE_PARTS
            elif DATABASE_DLC_KEY_URL in raw:
                source_type = SOURCE_TYPE_URL
            elif DATABASE_DLC_KEY_MAGNET in raw:
                source_type = SOURCE_TYPE_MAGNET
            else:
                source_type = None

        checksums = CheckSums.from_dict(raw.get(DATABASE_DLC_KEY_CHECKSUM))
        priority_raw = raw.get(DATABASE_DLC_KEY_PRIORITY)
        if priority_raw is None or isinstance(priority_raw, bool):
            priority = 0
        elif isinstance(priority_raw, int):
            priority = priority_raw
        else:
            try:
                priority = int(priority_raw)
            except (TypeError, ValueError):
                priority = 0

        if source_type == SOURCE_TYPE_PARTS:
            parts: List[DownloadSource] = []
            for part in raw.get(DATABASE_DLC_KEY_PARTS) or []:
                parsed = cls.from_dict(part)
                if parsed is not None:
                    parts.append(parsed)
            return cls(SOURCE_TYPE_PARTS, parts=parts, checksums=checksums, priority=priority)

        if source_type == SOURCE_TYPE_URL:
            return cls(SOURCE_TYPE_URL, source=raw.get(DATABASE_DLC_KEY_URL), checksums=checksums, priority=priority)
        if source_type == SOURCE_TYPE_MAGNET:
            return cls(SOURCE_TYPE_MAGNET, source=raw.get(DATABASE_DLC_KEY_MAGNET), checksums=checksums, priority=priority)

        return cls(source_type, checksums=checksums, priority=priority)

    @classmethod
    def url(cls, url: str, checksums: Optional["CheckSums"] = None, priority: int = 0) -> "DownloadSource":
        return cls(SOURCE_TYPE_URL, source=url, checksums=checksums, priority=priority)

    @classmethod
    def magnet(cls, magnet: str, checksums: Optional["CheckSums"] = None, priority: int = 0) -> "DownloadSource":
        return cls(SOURCE_TYPE_MAGNET, source=magnet, checksums=checksums, priority=priority)

    @classmethod
    def parts(
        cls, part_sources: List["DownloadSource"], checksums: Optional["CheckSums"] = None, priority: int = 0
    ) -> "DownloadSource":
        return cls(SOURCE_TYPE_PARTS, parts=part_sources, checksums=checksums, priority=priority)

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
        entry_checksums = CheckSums.from_dict(raw.get(DATABASE_DLC_KEY_CHECKSUM))
        main: Optional[DownloadSource] = None

        if raw.get(DATABASE_DLC_KEY_URL):
            main = DownloadSource.url(raw[DATABASE_DLC_KEY_URL], checksums=entry_checksums)

        mirrors: List[DownloadSource] = []
        if raw.get(DATABASE_DLC_KEY_MAGNET):
            mirrors.append(DownloadSource.magnet(raw[DATABASE_DLC_KEY_MAGNET], checksums=entry_checksums))

        if raw.get(DATABASE_DLC_KEY_PARTS):
            part_sources: List[DownloadSource] = [DownloadSource.url(p) for p in raw[DATABASE_DLC_KEY_PARTS]]
            mirrors.append(DownloadSource.parts(part_sources, checksums=entry_checksums))

        for mirror in raw.get(DATABASE_DLC_KEY_MIRRORS) or []:
            source = DownloadSource.from_dict(mirror)
            if source is None:
                continue

            if source.getCheckSums() is None and entry_checksums is not None:
                source._checksums = entry_checksums
            mirrors.append(source)

        mirrors.sort(key=lambda s: s.getPriority(), reverse=True)
        return cls(dlc_id, raw.get(DATABASE_DLC_KEY_NAME, "Unknown"), raw.get(DATABASE_DLC_KEY_SIZE), main, mirrors)

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
        speed_mbps = (size_bytes / MB) / duration_sec if duration_sec > 0 else 0
        with self.lock:
            self.downloads[dlc_id] = {
                "size_mb": size_bytes / MB,
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
            avg_speed = (self.total_bytes / MB) / self.total_time if self.total_time > 0 else 0
            total_dlc = self.total_dlc if self.total_dlc is not None else len(self.downloads)
            successful = len(self.downloads)

            return {
                "total_dlc": total_dlc,
                "total_size_mb": self.total_bytes / MB,
                "total_duration_sec": total_duration,
                "avg_speed_mbps": avg_speed,
                "successful": successful,
                "failed": total_dlc - successful,
                "errors": self.errors,
            }

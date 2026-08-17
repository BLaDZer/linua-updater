import os
import shutil
import sys
from typing import Any, List, Optional


def _platform() -> str:
    return sys.platform


class SevenZipFinder:
    POSSIBLE_LOCATIONS = [
        "7z.exe",
        "7za.exe",
        r"tools\7z.exe",
        r"tools\7za.exe",
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files\7-Zip\7za.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7za.exe",
        "7z",
        "7za",
        "tools/7z",
        "tools/7za",
        "/usr/bin/7z",
        "/usr/bin/7za",
        "/usr/bin/7zz",
        "/usr/local/bin/7z",
        "/snap/bin/7z",
    ]

    def __init__(self, logger: Any) -> None:
        self.logger = logger

    def _executable_names(self) -> List[str]:
        if _platform() == "win32":
            return ["7z.exe", "7za.exe"]
        return ["7z", "7za", "7zz"]

    def find(self) -> Optional[str]:
        # 0. Check in PyInstaller bundle directory
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            for name in self._executable_names():
                local = os.path.join(meipass, name)
                if os.path.exists(local):
                    return local

        # 1. Check in same directory as executable
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        for name in self._executable_names():
            local = os.path.join(exe_dir, name)
            if os.path.exists(local):
                return local

        # 2. Check common installation paths
        for p in self.POSSIBLE_LOCATIONS:
            if os.path.exists(p):
                return p

        # 3. Check system PATH using shutil.which
        for name in self._executable_names():
            path = shutil.which(name)
            if path:
                return path

        # 4. Check PATH environment variable manually
        path_env = os.environ.get("PATH", "")
        for path_dir in path_env.split(os.pathsep):
            for exe_name in self._executable_names():
                candidate = os.path.join(path_dir, exe_name)
                if os.path.exists(candidate):
                    return candidate

        self.logger.log(
            "7-Zip not found. Install 7-Zip from https://www.7-zip.org/ and make sure the binary is on PATH", "WARNING"
        )
        return None

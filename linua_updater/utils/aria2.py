import os
import shutil
import sys


class Aria2Finder:
    POSSIBLE_LOCATIONS = [
        "aria2c.exe",
        r"tools\aria2c.exe",
        r"C:\Program Files\aria2\aria2c.exe",
        r"C:\Program Files (x86)\aria2\aria2c.exe",
        r"C:\msys64\mingw64\bin\aria2c.exe",
        "aria2c",
        "tools/aria2c",
        "/usr/bin/aria2c",
        "/usr/local/bin/aria2c",
        "/opt/local/bin/aria2c",
        "/snap/bin/aria2c",
    ]

    def __init__(self, logger):
        self.logger = logger

    def _executable_names(self):
        if sys.platform == "win32":
            return ["aria2c.exe"]
        return ["aria2c"]

    def find(self):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            for name in self._executable_names():
                local = os.path.join(meipass, name)
                if os.path.exists(local):
                    return local

        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        for name in self._executable_names():
            local = os.path.join(exe_dir, name)
            if os.path.exists(local):
                return local

        for p in self.POSSIBLE_LOCATIONS:
            if os.path.exists(p):
                return p

        for name in self._executable_names():
            path = shutil.which(name)
            if path:
                return path

        self.logger.log("Torrent download: aria2c not found. Torrent downloads will be skipped", "WARNING")
        return None

import ctypes
import ntpath
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List


def _platform() -> str:
    return sys.platform


WIN32_PROTECTED_PREFIXES = [
    r"c:\program files",
    r"c:\program files (x86)",
    r"c:\windows",
    r"c:\programdata",
]

POSIX_PROTECTED_PREFIXES = ["/usr", "/opt", "/etc", "/var"]


class AdminElevator:
    @staticmethod
    def is_admin() -> bool:
        try:
            if _platform() == "win32":
                return bool(ctypes.__dict__["windll"].shell32.IsUserAnAdmin())
            return getattr(os, "geteuid", lambda: 0)() == 0
        except:
            return False

    @staticmethod
    def _matches_win32_protected(path: str) -> bool:
        normalized = ntpath.normcase(str(path))
        for prefix in WIN32_PROTECTED_PREFIXES:
            if normalized == prefix or normalized.startswith(prefix + "\\"):
                return True
        return False

    @staticmethod
    def requires_admin(path: str) -> bool:
        if not path:
            return False
        path_str = str(path)
        if _platform() == "win32" and AdminElevator._matches_win32_protected(path_str):
            return True
        if _platform() != "win32":
            normalized = os.path.normpath(path_str)
            for prefix in POSIX_PROTECTED_PREFIXES:
                if normalized == prefix or normalized.startswith(prefix + os.sep):
                    return True
        tempname = f".linua_write_test_{os.getpid()}_{time.time_ns()}"
        test_file = Path(os.path.join(path_str, tempname))
        try:
            test_file.touch()
            return False
        except:
            return True
        finally:
            try:
                test_file.unlink()
            except:
                pass

    @staticmethod
    def _launch_args() -> List[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable] + list(sys.argv[1:])
        return [sys.executable, sys.argv[0]] + list(sys.argv[1:])

    @staticmethod
    def elevate() -> bool:
        try:
            if AdminElevator.is_admin():
                return True
            if _platform() == "win32":
                if getattr(sys, "frozen", False):
                    script = sys.executable
                    params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
                else:
                    script = sys.executable
                    params = f'"{sys.argv[0]}"'
                    if len(sys.argv) > 1:
                        params += " " + " ".join(f'"{arg}"' for arg in sys.argv[1:])
                ret = ctypes.__dict__["windll"].shell32.ShellExecuteW(None, "runas", script, params, None, 1)
                if ret > 32:
                    sys.exit(0)
                return False
            if _platform() == "darwin":
                if not shutil.which("osascript"):
                    return False
                launch_cmd = " ".join(shlex.quote(arg) for arg in AdminElevator._launch_args())
                proc = subprocess.run(
                    ["osascript", "-e", f'do shell script "{launch_cmd}" with administrator privileges']
                )
                if proc.returncode == 0:
                    sys.exit(0)
                return False
            for cmd in ("pkexec", "sudo", "gksudo"):
                if shutil.which(cmd):
                    base = [cmd]
                    if cmd == "sudo":
                        base.append("-A")
                    proc = subprocess.run(base + AdminElevator._launch_args())
                    if proc.returncode == 0:
                        sys.exit(0)
                    return False
            return False
        except Exception as e:
            print(f"Admin elevation failed: {e}")
            return False

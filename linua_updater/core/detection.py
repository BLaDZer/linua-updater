import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Set


class GameDetector:
    _EXE_REL = ("Game", "Bin", "TS4_x64.exe")
    _EXE_NAME = "TS4_x64.exe"

    @staticmethod
    def _has_valid_exe(path: str) -> bool:
        exe_check = os.path.join(path, *GameDetector._EXE_REL)
        return os.path.exists(exe_check)

    @staticmethod
    def find_from_registry() -> List[str]:
        if sys.platform != "win32":
            return []
        try:
            import winreg

            paths_to_check = []
            registry_keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Maxis\The Sims 4", "Install Dir"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Maxis\The Sims 4", "Install Dir"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\EA Games\The Sims 4", "Install Dir"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\EA Games\The Sims 4", "Install Dir"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Maxis\The Sims 4", "Install Dir"),
            ]
            for hkey, subkey, value_name in registry_keys:
                try:
                    key = winreg.OpenKey(hkey, subkey)
                    value, _ = winreg.QueryValueEx(key, value_name)
                    winreg.CloseKey(key)
                    if value and os.path.exists(value):
                        paths_to_check.append(value)
                except:
                    continue
            return paths_to_check
        except:
            return []

    @staticmethod
    def _steam_vdf_candidates(home: Path) -> List[Path]:
        if sys.platform == "darwin":
            return [home / "Library" / "Application Support" / "Steam" / "steamapps" / "libraryfolders.vdf"]
        return [
            home / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf",
            home / ".steam" / "steam" / "steamapps" / "libraryfolders.vdf",
        ]

    @staticmethod
    def _steam_home_guesses(home: Path) -> List[str]:
        if sys.platform == "darwin":
            return [str(home / "Library" / "Application Support" / "Steam" / "steamapps" / "common" / "The Sims 4")]
        return [
            str(home / ".local" / "share" / "Steam" / "steamapps" / "common" / "The Sims 4"),
            str(home / ".steam" / "steam" / "steamapps" / "common" / "The Sims 4"),
        ]

    @staticmethod
    def _parse_steam_library_paths(vdf_path: Path) -> List[str]:
        paths = []
        try:
            with open(vdf_path, "rb") as f:
                for line in f:
                    match = re.search(rb'"path"\s+"([^"]+)"', line)
                    if match:
                        value = match.group(1).decode("utf-8", errors="replace")
                        if value:
                            paths.append(value)
        except (OSError, ValueError):
            return []
        return paths

    @staticmethod
    def _find_proton_exe(game_folder: str) -> Optional[str]:
        game_dir = os.path.join(game_folder, "Game")
        if not os.path.isdir(game_dir):
            return None
        steamapps = os.path.abspath(os.path.join(game_folder, os.pardir, os.pardir))
        compatdata = os.path.join(steamapps, "compatdata")
        if not os.path.isdir(compatdata):
            return None
        max_depth = 12
        for root, dirs, files in os.walk(compatdata):
            depth = root[len(compatdata) :].count(os.sep)
            if depth >= max_depth:
                dirs[:] = []
                continue
            if GameDetector._EXE_NAME in files:
                parent = os.path.basename(root)
                grandparent = os.path.basename(os.path.dirname(root))
                if parent == "Bin" and grandparent == "Game":
                    return os.path.join(root, GameDetector._EXE_NAME)
        return None

    @staticmethod
    def find_from_steam() -> List[str]:
        if sys.platform == "win32":
            return []
        home = Path.home()
        found_paths: List[str] = []
        seen: Set[str] = set()
        for vdf in GameDetector._steam_vdf_candidates(home):
            if not vdf.is_file():
                continue
            for lib in GameDetector._parse_steam_library_paths(vdf):
                game_folder = os.path.join(lib, "steamapps", "common", "The Sims 4")
                if game_folder in seen:
                    continue
                seen.add(game_folder)
                if GameDetector._has_valid_exe(game_folder) or GameDetector._find_proton_exe(game_folder):
                    found_paths.append(game_folder)
        for guess in GameDetector._steam_home_guesses(home):
            if guess not in seen and GameDetector._has_valid_exe(guess):
                seen.add(guess)
                found_paths.append(guess)
        return found_paths

    @staticmethod
    def find_game() -> Optional[str]:
        found_paths: List[str] = []
        registry_paths = GameDetector.find_from_registry()
        for path in registry_paths:
            if path not in found_paths and GameDetector._has_valid_exe(path):
                found_paths.append(path)
        if sys.platform == "win32":
            drives = ["C", "D", "E", "F", "G", "H"]
            search_paths = [
                r"\Program Files (x86)\Steam\steamapps\common\The Sims 4",
                r"\Program Files\Steam\steamapps\common\The Sims 4",
                r"\SteamLibrary\steamapps\common\The Sims 4",
                r"\Program Files\EA Games\The Sims 4",
                r"\Program Files (x86)\EA Games\The Sims 4",
                r"\Program Files (x86)\Origin Games\The Sims 4",
                r"\Program Files\Origin Games\The Sims 4",
                r"\Games\The Sims 4",
                r"\EA Games\The Sims 4",
                r"\Origin Games\The Sims 4",
            ]
            for drive in drives:
                for path in search_paths:
                    full_path = f"{drive}:{path}"
                    if full_path not in found_paths and os.path.exists(full_path):
                        if GameDetector._has_valid_exe(full_path):
                            found_paths.append(full_path)
        for path in GameDetector.find_from_steam():
            if path not in found_paths:
                found_paths.append(path)
        return found_paths[0] if found_paths else None

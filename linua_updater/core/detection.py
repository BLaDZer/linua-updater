import os


class GameDetector:
    @staticmethod
    def find_from_registry():
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
    def find_game():
        found_paths = []
        registry_paths = GameDetector.find_from_registry()
        for path in registry_paths:
            exe_check = os.path.join(path, "Game", "Bin", "TS4_x64.exe")
            if os.path.exists(exe_check):
                found_paths.append(path)
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
                    exe_check = os.path.join(full_path, "Game", "Bin", "TS4_x64.exe")
                    if os.path.exists(exe_check):
                        found_paths.append(full_path)
        return found_paths[0] if found_paths else None
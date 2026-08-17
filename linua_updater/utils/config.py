import json

from linua_updater.constants import DEFAULT_MIRRORS, DEFAULT_PROXY_PORTS, DEFAULT_REGION_API, DEFAULT_VERSION_CHECK_URL
from linua_updater.paths import AppPaths


class ConfigManager:
    def __init__(self):
        self.path = AppPaths.CONFIG_FILE
        AppPaths.ensure()
        if not self.path.exists():
            self.data = {
                "game_path": "",
                "settings": {"max_threads": 3, "use_proxy": True, "resume_downloads": True, "cleanup_temp": True},
            }
            self.save()
        else:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                    if "settings" not in self.data:
                        self.data["settings"] = {
                            "max_threads": 3,
                            "use_proxy": True,
                            "resume_downloads": True,
                            "cleanup_temp": True,
                        }
            except:
                self.data = {
                    "game_path": "",
                    "settings": {"max_threads": 3, "use_proxy": True, "resume_downloads": True, "cleanup_temp": True},
                }
                self.save()

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def get_settings(self):
        return self.data.get("settings", {})

    def get_network(self):
        defaults = {
            "version_check_url": DEFAULT_VERSION_CHECK_URL,
            "region_api": DEFAULT_REGION_API,
            "proxy_ports": list(DEFAULT_PROXY_PORTS),
            "mirrors": dict(DEFAULT_MIRRORS),
        }
        net = self.data.get("network", {}) or {}
        merged = dict(defaults)
        for key, value in net.items():
            if value:
                merged[key] = value
        return merged

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Config save failed: {e}")

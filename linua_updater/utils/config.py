import json
from typing import Any, Dict, Optional, cast

from linua_updater.constants import (
    DEFAULT_MIRRORS,
    DEFAULT_PROXY_PORTS,
    DEFAULT_REGION_API_URL,
    DEFAULT_VERSION_CHECK_URL,
    JSON_INDENT,
)
from linua_updater.paths import AppPaths

DEFAULT_SETTINGS = {"max_threads": 3, "use_proxy": True, "resume_downloads": True, "cleanup_temp": True}

DEFAULT_NETWORK = {
    "version_check_url": DEFAULT_VERSION_CHECK_URL,
    "region_api": DEFAULT_REGION_API_URL,
    "proxy_ports": list(DEFAULT_PROXY_PORTS),
    "mirrors": dict(DEFAULT_MIRRORS),
}


class ConfigManager:
    def __init__(self) -> None:
        self.path = AppPaths.CONFIG_FILE
        self.data: Dict[str, Any] = {}
        AppPaths.ensure()
        if not self.path.exists():
            self.data = {
                "game_path": "",
                "settings": dict(DEFAULT_SETTINGS),
            }
            self.save()
        else:
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.data = json.load(f)
                    if "settings" not in self.data:
                        self.data["settings"] = dict(DEFAULT_SETTINGS)
            except:
                self.data = {
                    "game_path": "",
                    "settings": dict(DEFAULT_SETTINGS),
                }
                self.save()

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def get_settings(self) -> Dict[str, Any]:
        return cast(Dict[str, Any], self.data.get("settings", {}))

    def get_network(self) -> Dict[str, Any]:
        net = self.data.get("network", {}) or {}
        merged = dict(DEFAULT_NETWORK)
        for key, value in net.items():
            if value:
                merged[key] = value
        return merged

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=JSON_INDENT, ensure_ascii=False)
        except Exception as e:
            print(f"Config save failed: {e}")

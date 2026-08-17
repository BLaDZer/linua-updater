import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from linua_updater.constants import DEFAULT_PROXY_PORTS, DEFAULT_REGION_API


class NetworkDiagnostics:
    def __init__(
        self, logger: Optional[Any] = None, region_api: Optional[str] = None, proxy_ports: Optional[List[int]] = None
    ) -> None:
        self.logger: Optional[Any] = logger
        self.region_api: str = region_api or DEFAULT_REGION_API
        self.proxy_ports: List[int] = proxy_ports if proxy_ports else list(DEFAULT_PROXY_PORTS)
        self.can_reach_github: bool = False
        self.proxy_needed: bool = False
        self.working_proxies: List[Dict[str, str]] = []
        self.recommended_solution: str = "unknown"
        self.is_russia: bool = False

    def log(self, msg: str, level: str = "INFO") -> None:
        if self.logger:
            self.logger.log(msg, level)

    def detect_region(self) -> bool:
        try:
            response = requests.get(self.region_api, timeout=5)
            data = response.json()
            country_code = data.get("country_code", "")
            if country_code in ["RU", "UA", "BY"]:
                self.is_russia = True
                return True
        except:
            pass
        return False

    def test_connection(self, url: str, timeout: int = 5) -> bool:
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code < 400
        except:
            return False

    def test_proxy(self, proxy_dict: Dict[str, str]) -> Tuple[bool, float]:
        try:
            start = time.time()
            response = requests.get("https://github.com", proxies=proxy_dict, timeout=10, verify=True)
            elapsed = (time.time() - start) * 1000
            return response.status_code < 400, elapsed
        except:
            return False, 0

    def diagnose(self) -> None:
        self.detect_region()
        self.can_reach_github = self.test_connection("https://github.com")
        raw_ok = self.test_connection("https://raw.githubusercontent.com")

        if self.can_reach_github and raw_ok:
            self.log("Network check: OK (direct connection)")
            self.recommended_solution = "direct"
            self.proxy_needed = False
            return

        self.log("Network check: blocked, searching for proxy...")
        self.proxy_needed = True

        test_proxies = []
        for port in self.proxy_ports:
            scheme = "socks5" if port in (1080, 7890, 10808) else "http"
            test_proxies.append({"http": f"{scheme}://127.0.0.1:{port}", "https": f"{scheme}://127.0.0.1:{port}"})

        for proxy in test_proxies:
            is_working, speed = self.test_proxy(proxy)
            if is_working:
                self.working_proxies.append(proxy)
                self.log(f"Proxy found: {speed:.0f}ms")

        if self.working_proxies:
            self.recommended_solution = "proxy"
        else:
            self.recommended_solution = "vpn_needed"
            self.log("No proxies found. Install VPN or Cloudflare WARP", "WARNING")

    def get_recommendation(self) -> str:
        if self.recommended_solution == "direct":
            return "Direct connection working"
        elif self.recommended_solution == "proxy":
            return f"Using proxy ({len(self.working_proxies)} found)"
        else:
            return "Connection blocked. Install Cloudflare WARP: https://1.1.1.1/"

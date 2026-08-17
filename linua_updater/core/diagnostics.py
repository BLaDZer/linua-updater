import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from linua_updater.constants import (
    CLOUDFLARE_WARP_URL,
    DEFAULT_PROXY_PORTS,
    DEFAULT_REGION_API_URL,
    GITHUB_URL,
    GITHUB_USER_CONTENT_URL,
    HTTP_CLIENT_ERROR,
    HTTP_TIMEOUT_SEC,
    MILLISECONDS_IN_SECOND,
)

REGION_TIMEOUT_SEC = 5

RESTRICTED_COUNTRIES = ("RU", "UA", "BY")
SOCKS5_PORTS = {1080, 7890, 10808}
LOOPBACK = "127.0.0.1"

CONNECTION_DIRECT = "direct"
CONNECTION_PROXY = "proxy"
CONNECTION_VPN_NEEDED = "vpn_needed"
CONNECTION_UNKNOWN = "unknown"


class NetworkDiagnostics:
    def __init__(
        self, logger: Optional[Any] = None, region_api: Optional[str] = None, proxy_ports: Optional[List[int]] = None
    ) -> None:
        self.logger: Optional[Any] = logger
        self.region_api: str = region_api or DEFAULT_REGION_API_URL
        self.proxy_ports: List[int] = proxy_ports if proxy_ports else list(DEFAULT_PROXY_PORTS)
        self.can_reach_github: bool = False
        self.proxy_needed: bool = False
        self.working_proxies: List[Dict[str, str]] = []
        self.recommended_solution: str = CONNECTION_UNKNOWN
        self.is_restricted_region: bool = False

    def log(self, msg: str, level: str = "INFO") -> None:
        if self.logger:
            self.logger.log(msg, level)

    def detect_region(self) -> bool:
        try:
            response = requests.get(self.region_api, timeout=REGION_TIMEOUT_SEC)
            data = response.json()
            country_code = data.get("country_code", "")
            if country_code in RESTRICTED_COUNTRIES:
                self.is_restricted_region = True
                return True
        except:
            pass
        return False

    def test_connection(self, url: str, timeout: int = REGION_TIMEOUT_SEC) -> bool:
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code < HTTP_CLIENT_ERROR
        except:
            return False

    def test_proxy(self, proxy_dict: Dict[str, str]) -> Tuple[bool, float]:
        try:
            start = time.time()
            response = requests.get(GITHUB_URL, proxies=proxy_dict, timeout=HTTP_TIMEOUT_SEC, verify=True)
            elapsed = (time.time() - start) * MILLISECONDS_IN_SECOND
            return response.status_code < HTTP_CLIENT_ERROR, elapsed
        except:
            return False, 0

    def diagnose(self) -> None:
        self.detect_region()
        self.can_reach_github = self.test_connection(GITHUB_URL)
        raw_ok = self.test_connection(GITHUB_USER_CONTENT_URL)

        if self.can_reach_github and raw_ok:
            self.log("Network check: OK (direct connection)")
            self.recommended_solution = CONNECTION_DIRECT
            self.proxy_needed = False
            return

        self.log("Network check: blocked, searching for proxy...")
        self.proxy_needed = True

        test_proxies = []
        for port in self.proxy_ports:
            scheme = "socks5" if port in SOCKS5_PORTS else "http"
            test_proxies.append({"http": f"{scheme}://{LOOPBACK}:{port}", "https": f"{scheme}://{LOOPBACK}:{port}"})

        for proxy in test_proxies:
            is_working, speed = self.test_proxy(proxy)
            if is_working:
                self.working_proxies.append(proxy)
                self.log(f"Proxy found: {speed:.0f}ms")

        if self.working_proxies:
            self.recommended_solution = CONNECTION_PROXY
        else:
            self.recommended_solution = CONNECTION_VPN_NEEDED
            self.log("No proxies found. Install VPN or Cloudflare WARP", "WARNING")

    def get_recommendation(self) -> str:
        if self.recommended_solution == CONNECTION_DIRECT:
            return "Direct connection working"
        elif self.recommended_solution == CONNECTION_PROXY:
            return f"Using proxy ({len(self.working_proxies)} found)"
        else:
            return "Connection blocked. Install Cloudflare WARP: " + CLOUDFLARE_WARP_URL

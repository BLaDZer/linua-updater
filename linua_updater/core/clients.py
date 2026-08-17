from typing import Any, Dict, Optional

import requests

from linua_updater.constants import APP_VERSION, DEFAULT_DOWNLOAD_TIMEOUT_SEC


class HTTPClient:
    """Generic HTTP transport: owns the session, headers, proxy and request verbs."""

    def __init__(
        self,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT_SEC,
        verify: bool = True,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = timeout
        self.verify = verify
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "Linua-Updater/" + APP_VERSION})

    def set_proxy(self, proxy_dict: Optional[Dict[str, str]]) -> None:
        if proxy_dict:
            self.session.proxies = proxy_dict
        else:
            self.session.proxies = {}

    def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
        proxies: Optional[Dict[str, str]] = None,
        stream: bool = False,
    ) -> requests.Response:
        return self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=self.timeout if timeout is None else timeout,
            verify=self.verify if verify is None else verify,
            proxies=proxies,
            stream=stream,
        )

    def head(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        allow_redirects: bool = True,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
        proxies: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        return self.session.head(
            url,
            params=params,
            headers=headers,
            allow_redirects=allow_redirects,
            timeout=self.timeout if timeout is None else timeout,
            verify=self.verify if verify is None else verify,
            proxies=proxies,
        )

    def post(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
        proxies: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        return self.session.post(
            url,
            params=params,
            data=data,
            json=json,
            headers=headers,
            timeout=self.timeout if timeout is None else timeout,
            verify=self.verify if verify is None else verify,
            proxies=proxies,
        )

    def get_stream(self, url: str, start_byte: int = 0, **kwargs: Any) -> requests.Response:
        headers: Dict[str, str] = dict(kwargs.pop("headers", None) or {})
        if start_byte > 0:
            headers["Range"] = f"bytes={start_byte}-"
        return self.get(url, headers=headers, stream=True, **kwargs)

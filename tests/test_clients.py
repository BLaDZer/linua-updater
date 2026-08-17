import pytest

import requests

from linua_updater.constants import APP_VERSION, DEFAULT_DOWNLOAD_TIMEOUT_SEC
from linua_updater.core.clients import HTTPClient


class FakeResponse:
    pass


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.proxies = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()

    def head(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


class RaisingSession(FakeSession):
    def __init__(self, exc):
        super().__init__()
        self.exc = exc

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        raise self.exc


def test_default_session_sets_user_agent():
    client = HTTPClient()
    assert client.session.headers.get("User-Agent") == "Linua-Updater/" + APP_VERSION


def test_injected_session_used_and_gets_user_agent():
    session = FakeSession()
    client = HTTPClient(session=session)
    assert client.session is session
    assert client.session.headers.get("User-Agent") == "Linua-Updater/" + APP_VERSION


def test_set_proxy_sets_and_clears():
    session = FakeSession()
    client = HTTPClient(session=session)
    client.set_proxy({"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"})
    assert session.proxies
    client.set_proxy(None)
    assert session.proxies == {}


def test_get_stream_default_kwargs():
    session = FakeSession()
    client = HTTPClient(session=session)
    client.get_stream("https://example.com/file.zip")
    url, kwargs = session.calls[0]
    assert url == "https://example.com/file.zip"
    assert kwargs["stream"] is True
    assert kwargs["timeout"] == DEFAULT_DOWNLOAD_TIMEOUT_SEC
    assert kwargs["verify"] is True
    assert "Range" not in kwargs["headers"]


def test_get_stream_adds_range_header_for_resume():
    session = FakeSession()
    client = HTTPClient(session=session)
    client.get_stream("https://example.com/file.zip", start_byte=2048)
    _, kwargs = session.calls[0]
    assert kwargs["headers"]["Range"] == "bytes=2048-"


def test_get_stream_no_range_when_start_byte_zero():
    session = FakeSession()
    client = HTTPClient(session=session)
    client.get_stream("https://example.com/file.zip", start_byte=0)
    _, kwargs = session.calls[0]
    assert "Range" not in kwargs["headers"]


def test_get_stream_uses_custom_timeout():
    session = FakeSession()
    client = HTTPClient(session=session, timeout=5)
    client.get_stream("https://example.com/file.zip")
    _, kwargs = session.calls[0]
    assert kwargs["timeout"] == 5


def test_get_stream_uses_verify_flag():
    session = FakeSession()
    client = HTTPClient(session=session, verify=False)
    client.get_stream("https://example.com/file.zip")
    _, kwargs = session.calls[0]
    assert kwargs["verify"] is False


def test_timeout_propagates():
    client = HTTPClient(session=RaisingSession(requests.exceptions.Timeout()))
    with pytest.raises(requests.exceptions.Timeout):
        client.get_stream("https://example.com/file.zip")


def test_connection_error_propagates():
    client = HTTPClient(session=RaisingSession(requests.exceptions.ConnectionError()))
    with pytest.raises(requests.exceptions.ConnectionError):
        client.get_stream("https://example.com/file.zip")


def test_get_passes_params_headers_and_stream():
    session = FakeSession()
    client = HTTPClient(session=session)
    client.get("https://example.com", params={"a": "b"}, headers={"X-Foo": "bar"}, stream=True)
    url, kwargs = session.calls[0]
    assert url == "https://example.com"
    assert kwargs["params"] == {"a": "b"}
    assert kwargs["headers"] == {"X-Foo": "bar"}
    assert kwargs["stream"] is True
    assert kwargs["proxies"] is None


def test_get_per_call_timeout_and_verify_override_defaults():
    session = FakeSession()
    client = HTTPClient(session=session, timeout=5, verify=False)
    client.get("https://example.com", timeout=15, verify=True)
    _, kwargs = session.calls[0]
    assert kwargs["timeout"] == 15
    assert kwargs["verify"] is True


def test_get_uses_instance_defaults_when_not_overridden():
    session = FakeSession()
    client = HTTPClient(session=session, timeout=5, verify=False)
    client.get("https://example.com")
    _, kwargs = session.calls[0]
    assert kwargs["timeout"] == 5
    assert kwargs["verify"] is False


def test_get_passes_proxies_through_when_given():
    session = FakeSession()
    client = HTTPClient(session=session)
    proxies = {"http": "http://127.0.0.1:1080"}
    client.get("https://example.com", proxies=proxies)
    _, kwargs = session.calls[0]
    assert kwargs["proxies"] is proxies


def test_head_forwards_allow_redirects():
    session = FakeSession()
    client = HTTPClient(session=session)
    client.head("https://example.com", allow_redirects=False)
    url, kwargs = session.calls[0]
    assert url == "https://example.com"
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == DEFAULT_DOWNLOAD_TIMEOUT_SEC


def test_post_forwards_data_and_json():
    session = FakeSession()
    client = HTTPClient(session=session)
    client.post("https://example.com", data={"x": "1"}, json={"y": "2"})
    url, kwargs = session.calls[0]
    assert url == "https://example.com"
    assert kwargs["data"] == {"x": "1"}
    assert kwargs["json"] == {"y": "2"}


def test_get_stream_forwards_extra_kwargs_to_get():
    session = FakeSession()
    client = HTTPClient(session=session)
    client.get_stream("https://example.com/file.zip", start_byte=0, timeout=7, verify=False)
    _, kwargs = session.calls[0]
    assert kwargs["timeout"] == 7
    assert kwargs["verify"] is False
    assert kwargs["stream"] is True
    assert "Range" not in kwargs["headers"]


def test_get_stream_preserves_existing_headers_and_adds_range():
    session = FakeSession()
    client = HTTPClient(session=session)
    client.get_stream("https://example.com/file.zip", start_byte=2048, headers={"Accept-Encoding": "identity"})
    _, kwargs = session.calls[0]
    assert kwargs["headers"]["Accept-Encoding"] == "identity"
    assert kwargs["headers"]["Range"] == "bytes=2048-"
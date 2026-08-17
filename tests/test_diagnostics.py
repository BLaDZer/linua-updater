from linua_updater.core.diagnostics import NetworkDiagnostics


class FakeLogger:
    def log(self, *args, **kwargs):
        pass


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


class FakeHTTPClient:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def _next(self, url, method):
        self.calls.append((method, url))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, **kwargs):
        return self._next(url, "get")

    def head(self, url, **kwargs):
        return self._next(url, "head")


def test_detect_region_ru_marks_is_restricted_region():
    fake = FakeHTTPClient([FakeResponse(json_data={"country_code": "RU"})])
    d = NetworkDiagnostics(client=fake)
    assert d.detect_region() is True
    assert d.is_restricted_region is True


def test_detect_region_network_error_false():
    fake = FakeHTTPClient([Exception("network down")])
    d = NetworkDiagnostics(client=fake)
    assert d.detect_region() is False
    assert d.is_restricted_region is False


def test_test_connection_ok():
    fake = FakeHTTPClient([FakeResponse(status_code=200)])
    assert NetworkDiagnostics(client=fake).test_connection("https://example.com") is True


def test_test_connection_failure():
    fake = FakeHTTPClient([Exception("network down")])
    assert NetworkDiagnostics(client=fake).test_connection("https://example.com") is False


def test_test_proxy_returns_speed():
    fake = FakeHTTPClient([FakeResponse(status_code=200)])
    ok, ms = NetworkDiagnostics(client=fake).test_proxy({"http": "http://127.0.0.1:1080"})
    assert ok is True
    assert ms >= 0


def test_test_proxy_error_returns_zero():
    fake = FakeHTTPClient([Exception("network down")])
    ok, ms = NetworkDiagnostics(client=fake).test_proxy({"http": "http://127.0.0.1:1080"})
    assert ok is False
    assert ms == 0


def test_diagnose_direct():
    fake = FakeHTTPClient([
        FakeResponse(json_data={"country_code": "US"}),
        FakeResponse(status_code=200),
        FakeResponse(status_code=200),
    ])
    d = NetworkDiagnostics(FakeLogger(), client=fake)
    d.diagnose()
    assert d.recommended_solution == "direct"
    assert d.proxy_needed is False


def test_diagnose_proxy_found():
    fake = FakeHTTPClient([
        FakeResponse(json_data={"country_code": "US"}),
        FakeResponse(status_code=500),
        FakeResponse(status_code=500),
        FakeResponse(status_code=200),
        Exception("proxy down"),
        Exception("proxy down"),
        Exception("proxy down"),
        Exception("proxy down"),
        Exception("proxy down"),
    ])
    d = NetworkDiagnostics(FakeLogger(), client=fake)
    d.diagnose()
    assert d.recommended_solution == "proxy"
    assert d.proxy_needed is True
    assert len(d.working_proxies) == 1


def test_diagnose_vpn_needed():
    fake = FakeHTTPClient([
        FakeResponse(json_data={"country_code": "US"}),
        FakeResponse(status_code=500),
        FakeResponse(status_code=500),
        Exception("proxy down"),
        Exception("proxy down"),
        Exception("proxy down"),
        Exception("proxy down"),
        Exception("proxy down"),
        Exception("proxy down"),
    ])
    d = NetworkDiagnostics(FakeLogger(), client=fake)
    d.diagnose()
    assert d.recommended_solution == "vpn_needed"
    assert d.proxy_needed is True
    assert d.working_proxies == []


def test_get_recommendation_messages():
    d = NetworkDiagnostics()
    d.recommended_solution = "direct"
    assert d.get_recommendation() == "Direct connection working"
    d.recommended_solution = "proxy"
    d.working_proxies = [{"http": "http://127.0.0.1:1080"}]
    assert d.get_recommendation() == "Using proxy (1 found)"
    d.recommended_solution = "vpn_needed"
    assert "1.1.1.1" in d.get_recommendation()

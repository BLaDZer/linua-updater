import linua_updater.core.diagnostics as diag_mod
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


class FakeRequests:
    def __init__(self, responses=None):
        self.responses = list(responses or [])

    def _next(self):
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, *args, **kwargs):
        return self._next()

    def head(self, *args, **kwargs):
        return self._next()


def test_detect_region_ru_marks_is_russia(monkeypatch):
    fake = FakeRequests([FakeResponse(json_data={"country_code": "RU"})])
    monkeypatch.setattr(diag_mod, "requests", fake)
    d = NetworkDiagnostics()
    assert d.detect_region() is True
    assert d.is_russia is True


def test_detect_region_network_error_false(monkeypatch):
    fake = FakeRequests([Exception("network down")])
    monkeypatch.setattr(diag_mod, "requests", fake)
    d = NetworkDiagnostics()
    assert d.detect_region() is False
    assert d.is_russia is False


def test_test_connection_ok(monkeypatch):
    fake = FakeRequests([FakeResponse(status_code=200)])
    monkeypatch.setattr(diag_mod, "requests", fake)
    assert NetworkDiagnostics().test_connection("https://example.com") is True


def test_test_connection_failure(monkeypatch):
    fake = FakeRequests([Exception("network down")])
    monkeypatch.setattr(diag_mod, "requests", fake)
    assert NetworkDiagnostics().test_connection("https://example.com") is False


def test_test_proxy_returns_speed(monkeypatch):
    fake = FakeRequests([FakeResponse(status_code=200)])
    monkeypatch.setattr(diag_mod, "requests", fake)
    ok, ms = NetworkDiagnostics().test_proxy({"http": "http://127.0.0.1:1080"})
    assert ok is True
    assert ms >= 0


def test_test_proxy_error_returns_zero(monkeypatch):
    fake = FakeRequests([Exception("network down")])
    monkeypatch.setattr(diag_mod, "requests", fake)
    ok, ms = NetworkDiagnostics().test_proxy({"http": "http://127.0.0.1:1080"})
    assert ok is False
    assert ms == 0


def test_diagnose_direct(monkeypatch):
    fake = FakeRequests([
        FakeResponse(json_data={"country_code": "US"}),
        FakeResponse(status_code=200),
        FakeResponse(status_code=200),
    ])
    monkeypatch.setattr(diag_mod, "requests", fake)
    d = NetworkDiagnostics(FakeLogger())
    d.diagnose()
    assert d.recommended_solution == "direct"
    assert d.proxy_needed is False


def test_diagnose_proxy_found(monkeypatch):
    fake = FakeRequests([
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
    monkeypatch.setattr(diag_mod, "requests", fake)
    d = NetworkDiagnostics(FakeLogger())
    d.diagnose()
    assert d.recommended_solution == "proxy"
    assert d.proxy_needed is True
    assert len(d.working_proxies) == 1


def test_diagnose_vpn_needed(monkeypatch):
    fake = FakeRequests([
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
    monkeypatch.setattr(diag_mod, "requests", fake)
    d = NetworkDiagnostics(FakeLogger())
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

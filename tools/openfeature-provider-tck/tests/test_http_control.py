"""What the Gherkin cannot assert about the HTTP control path.

Every scenario's isolation rests on :meth:`HttpControl.prepare_scenario` doing
the right thing against a backend that implements only part of the control API,
and on a disconnect being remembered. Both are invisible from inside a scenario:
a control that silently did nothing would leave each scenario running against
whatever state the previous one left behind, and the suite would report those
results as conformance.

So the control API is stubbed with :mod:`http.server` -- no Docker, no network
beyond loopback -- and the requests it actually made are asserted.
"""

from __future__ import annotations

import threading
import typing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from openfeature.contrib.tools.provider_tck import (
    ControlApiError,
    HttpControl,
)


class _StubControlApi:
    """A control API that records every request and answers a scripted status."""

    def __init__(self, statuses: dict[str, int] | None = None) -> None:
        self.requests: list[tuple[str, str, str]] = []
        """(method, path, query) of every request, in order."""

        self.statuses = statuses or {}
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                path, _, query = self.path.partition("?")
                stub.requests.append(("POST", path, query))
                status = stub.statuses.get(path, 200)
                body = b'{"status":"stub"}'
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: typing.Any) -> None:
                """Silence the default stderr logging."""

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host!s}:{port}"

    @property
    def paths(self) -> list[str]:
        return [path for _, path, _ in self.requests]

    def __enter__(self) -> _StubControlApi:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def stub() -> typing.Iterator[_StubControlApi]:
    with _StubControlApi() as api:
        yield api


def test_prepare_scenario_prefers_reset_when_the_backend_implements_it(
    stub: _StubControlApi,
) -> None:
    """The preferred primitive, because it causes no availability blip.

    A ``/start`` between scenarios restarts the backend process, which a
    provider observes as an outage and may report as a lifecycle event in the
    scenario that follows.
    """
    control = HttpControl(stub.base_url)

    control.prepare_scenario()
    control.prepare_scenario()

    assert stub.paths == ["/reset", "/reset"]


def test_prepare_scenario_falls_back_to_start_and_remembers_the_answer() -> None:
    """The path flagd-testbed actually takes: its launchpad has no ``/reset``.

    The fallback must be probed once rather than once per scenario -- a wasted
    404 before every scenario is a slow suite, and hiding the probe entirely
    would mean a backend that grows ``/reset`` never gets used properly.
    """
    with _StubControlApi({"/reset": 404}) as stub:
        control = HttpControl(stub.base_url)

        control.prepare_scenario()
        control.prepare_scenario()
        control.prepare_scenario()

        assert stub.paths == ["/reset", "/start", "/start", "/start"]


@pytest.mark.parametrize("status", [404, 501])
def test_both_documented_not_implemented_statuses_trigger_the_fallback(
    status: int,
) -> None:
    """The OpenAPI document permits either, so neither may be treated as a failure."""
    with _StubControlApi({"/reset": status}) as stub:
        HttpControl(stub.base_url).prepare_scenario()

        assert stub.paths == ["/reset", "/start"]


def test_the_scenario_after_a_disconnect_starts_the_backend(
    stub: _StubControlApi,
) -> None:
    """``/reset`` restores flag state; it is not specified to start a stopped backend.

    Without this the scenario following a disconnect would prepare a backend
    that is still down, register a provider against it, and report the failure
    as a provider defect.
    """
    control = HttpControl(stub.base_url)
    control.prepare_scenario()  # settles on /reset, which this stub supports
    stub.requests.clear()

    control.disconnect()
    control.prepare_scenario()

    assert stub.paths == ["/stop", "/start"]


def test_reconnect_starts_the_backend_and_clears_the_disconnect(
    stub: _StubControlApi,
) -> None:
    """A scenario that ended its own outage leaves the backend up, so ``/reset`` is fine again."""
    control = HttpControl(stub.base_url)
    control.prepare_scenario()
    control.disconnect()
    control.reconnect()
    stub.requests.clear()

    control.prepare_scenario()

    assert stub.paths == ["/reset"]


def test_start_names_the_configuration_under_test() -> None:
    """``default`` is the only name every backend must support, and it serves the canonical set."""
    with _StubControlApi({"/reset": 404}) as stub:
        HttpControl(stub.base_url).prepare_scenario()

        assert ("POST", "/start", "config=default") in stub.requests


def test_a_custom_configuration_is_carried_through() -> None:
    with _StubControlApi({"/reset": 404}) as stub:
        HttpControl(stub.base_url, configuration="ssl").prepare_scenario()

        assert ("POST", "/start", "config=ssl") in stub.requests


def test_restart_carries_the_outage_duration(stub: _StubControlApi) -> None:
    HttpControl(stub.base_url).restart(7)

    assert ("POST", "/restart", "seconds=7") in stub.requests


def test_change_flag_posts_to_change(stub: _StubControlApi) -> None:
    HttpControl(stub.base_url).change_flag()

    assert stub.paths == ["/change"]


def test_a_failed_control_call_raises_rather_than_passing_silently() -> None:
    """A control call that did nothing would leave the next scenario in an unknown state."""
    with (
        _StubControlApi({"/change": 500}) as stub,
        pytest.raises(ControlApiError, match="500"),
    ):
        HttpControl(stub.base_url).change_flag()


def test_an_unreachable_control_api_raises_with_the_reason() -> None:
    """The control API must stay up even while the backend is deliberately down."""
    # Bound and immediately closed, so the port is almost certainly free.
    with _StubControlApi() as stub:
        base_url = stub.base_url
    control = HttpControl(base_url, timeout=2.0)

    with pytest.raises(ControlApiError, match="control request POST"):
        control.change_flag()


@pytest.mark.parametrize(
    "base_url",
    ["", "localhost:8080", "file:///etc/passwd", "ftp://localhost:8080"],
)
def test_a_base_url_that_is_not_an_http_url_is_rejected_at_construction(
    base_url: str,
) -> None:
    """Rejected early, and by scheme, so no other URL scheme can reach ``urlopen``."""
    with pytest.raises(ValueError, match="not an http"):
        HttpControl(base_url)


def test_a_trailing_slash_does_not_produce_a_double_slash_path() -> None:
    with _StubControlApi() as stub:
        HttpControl(stub.base_url + "/").change_flag()

        assert stub.paths == ["/change"]


def test_the_control_reports_which_api_it_drives_the_backend_through() -> None:
    """The optional property ``BackendControl`` documents, answered here.

    A control that stays quiet has the field omitted from its report, which puts
    the normative HTTP path on the same footing as one that declined to say. This
    control can say, so it does.
    """
    with _StubControlApi() as stub:
        assert HttpControl(stub.base_url).control_api == "http"

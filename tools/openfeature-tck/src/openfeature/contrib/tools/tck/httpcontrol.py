"""HTTP backend control: the normative control path for a provider with a real backend."""

from __future__ import annotations

import threading
import time
import typing
import urllib.error
import urllib.parse
import urllib.request

from .control import BackendControl, BackendType, ConnectionControl

__all__ = [
    "DEFAULT_CONFIGURATION",
    "DEFAULT_STARTUP_TIMEOUT",
    "ControlApiError",
    "HttpControl",
]

DEFAULT_CONFIGURATION = "default"
"""The configuration name every backend under test must support.

It is the one that serves the canonical flag set the feature files assume.
"""

DEFAULT_TIMEOUT = 30.0
"""Seconds bounding a single control-API request.

Control calls are local HTTP to a container on the same host; anything slower
than this is a wedged backend rather than a slow one.
"""

DEFAULT_STARTUP_TIMEOUT = 60.0
"""Seconds to wait for a stack and its control API to become reachable.

The same default every language's TCK uses.
"""

_NOT_IMPLEMENTED = frozenset({404, 501})
"""How a backend that does not implement ``/reset`` answers it, per the OpenAPI document."""

_SUPPORTED_SCHEMES = frozenset({"http", "https"})

_READY_PROBE_TIMEOUT = 5.0
"""Seconds bounding a single readiness probe, so one wedged probe is not the whole wait."""

_READY_POLL_INTERVAL = 0.2
"""Seconds between readiness probes."""


class ControlApiError(RuntimeError):
    """Raised when a control-API call fails or answers with an unexpected status.

    Always a defect in the stack under test or in its wiring, never a provider
    defect -- so it is raised rather than swallowed. A control call that quietly
    did nothing would leave the next scenario running against an unknown backend
    state and reporting whatever it found as a conformance result.
    """


class HttpControl:
    """Drives a backend under test over the HTTP control API in ``control-api.yaml``.

    The normative control path for any provider with a real backend -- see
    :class:`~.control.BackendControl`.

    Built on :mod:`urllib.request` alone, so adopting the TCK pulls in no HTTP
    client and no container library.

    **What it never does.** It never stops, kills or recreates a container:
    unavailability is simulated inside the running stack, through ``POST /stop``,
    for the reason :mod:`~.compose` gives. Starting and stopping the stack itself
    belongs to the adopting suite, once per session.

    **Scenario isolation.** :meth:`prepare_scenario` prefers ``POST /reset``,
    which restores the flag baseline with no availability blip and therefore
    cannot inject a spurious lifecycle event into the next scenario. That
    operation is optional, and a backend that does not implement it answers 404
    or 501; the TCK then falls back to ``POST /start?config=...``. The fallback
    is probed once and remembered for the rest of the suite.

    **No settle after a control call, ever.** Every state-changing endpoint --
    ``/start``, ``/change``, ``/reset`` -- owes the caller that the new state is
    being served before it returns. A fixed delay here is un-tunable, because the
    window it covers is a property of the backend and not of this client, and it
    hides the defect from the one consumer positioned to notice. Where an adopter
    is stuck with a backend that breaks the promise, the wait belongs in *that
    adoption*, set explicitly and citing the defect.

    **After a disconnect, ``/start`` rather than ``/reset``.** ``/reset`` is
    specified to restore flag state, not to bring a stopped backend back up, so
    a disconnect is recorded and the scenario that follows one is prepared with
    ``/start``.

    **And after a served configuration, ``/start`` on this suite's own.** For the
    same half of the same reason: ``/reset`` restores flag state and says nothing
    about *which* configuration is being served, so a scenario that asked for
    another one has to be taken off it explicitly -- see
    :meth:`serve_configuration`.

    Safe to share between suites, and it should be shared whenever they drive the
    same backend: the disconnect bookkeeping is only correct if every operation
    against one backend goes through one instance of this class.
    """

    def __init__(
        self,
        base_url: str,
        *,
        backend_configuration: str = DEFAULT_CONFIGURATION,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Build a control for the backend whose control API is rooted at ``base_url``.

        :param base_url: root of the control API, for example
            ``http://localhost:32768``. It must be built from the dynamically
            mapped host port of the control service, discovered after the stack
            is up -- a stack under test must not pin host ports.
        :param backend_configuration: the named flag configuration the backend
            under test seeds. Defaults to :data:`DEFAULT_CONFIGURATION`, the
            only name every backend must support. Named for the backend because
            a report's ``provider.configuration`` is a different thing -- which
            mode of the provider was tested.
        :param timeout: seconds bounding a single control-API request.
        """
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in _SUPPORTED_SCHEMES or not parsed.netloc:
            msg = (
                f"base_url {base_url!r} is not an http(s) URL. It is the root of the "
                f"control API, built from the dynamically mapped host port of the "
                f"control service, for example 'http://localhost:32768'"
            )
            raise ValueError(msg)

        self._base_url = base_url.rstrip("/")
        self._backend_configuration = backend_configuration
        self._timeout = timeout

        self._lock = threading.Lock()
        # None until the first /reset call tells us which way it went.
        self._reset_supported: bool | None = None
        # Set by any operation that may have left the backend down, so the next
        # prepare_scenario starts it rather than merely resetting flag state.
        self._backend_maybe_down = False
        # A configuration one scenario asked for, which the next scenario has to
        # be taken off again. None while this suite's own is what is served.
        self._scenario_configuration: str | None = None

    @property
    def backend_type(self) -> BackendType:
        """Report that this control drives its backend over the HTTP control API.

        Stated although :class:`~.control.BackendControl` does not require it:
        every operation on this class is a request to the normative control API,
        so leaving it to default to ``"custom"`` would understate a run that
        took the one path a conformance claim is portable across.
        """
        return "http"

    @property
    def description(self) -> str:
        return f"the backend at {self._base_url}, driven over the control API"

    @property
    def base_url(self) -> str:
        """The root of the control API this client drives."""
        return self._base_url

    def await_ready(self, timeout: float = DEFAULT_STARTUP_TIMEOUT) -> None:
        """Block until the control API is ready to accept commands.

        A real readiness check against the control API itself rather than a
        fixed pause, and the only wait in this class. ``GET /healthz`` is the
        optional readiness path in ``control-api.yaml``; a backend that does not
        implement it answers 404, which the document states *is* ready. A 503 is
        the control API saying "not yet" and is retried.

        Called once, before the first command, by whatever brought the stack up.
        There is deliberately no counterpart *after* a command: a pause there
        would cover a window the control API is specified to close on its own,
        and a suite that sleeps instead of holding the API to that promise stops
        being able to detect when the promise breaks.

        :param timeout: seconds to keep probing before giving up.
        :raises ControlApiError: if the control API is still not ready when the
            timeout expires, quoting the last thing the probe saw.
        """
        deadline = time.monotonic() + timeout
        last = "no probe completed"
        while True:
            try:
                status = self._probe_health()
            except OSError as error:
                last = f"not reachable: {error}"
            else:
                # 404 is "not implemented", which the document defines as ready.
                if self._is_success(status) or status == 404:
                    return
                last = f"answered HTTP {status}"

            if time.monotonic() >= deadline:
                msg = (
                    f"the control API at {self._base_url} was not ready within "
                    f"{timeout:g}s: GET /healthz {last}. The control API must be "
                    f"reachable before the first scenario and must stay reachable "
                    f"even while the backend is deliberately down"
                )
                raise ControlApiError(msg)
            time.sleep(_READY_POLL_INTERVAL)

    def _probe_health(self) -> int:
        target = self._base_url + "/healthz"
        # S310: __init__ rejects any base_url that is not http(s), and target is
        # that validated base URL plus a literal path.
        request = urllib.request.Request(target, method="GET")  # noqa: S310
        try:
            opened = urllib.request.urlopen(request, timeout=_READY_PROBE_TIMEOUT)  # noqa: S310
            with opened as response:
                response.read()
                return int(response.status)
        except urllib.error.HTTPError as error:
            with error:
                error.read()
            return int(error.code)

    def prepare_scenario(self) -> None:
        """Bring the backend to the state every scenario starts from.

        Prefers ``/reset`` and falls back to ``/start`` -- see the class
        documentation for why, and for why a disconnect or a served configuration
        forces ``/start``.
        """
        with self._lock:
            served = self._scenario_configuration
            must_start = self._backend_maybe_down or self._reset_supported is False

        if served is not None:
            # This suite's configuration, not the last scenario's: that is what
            # preparing means. `/reset` would leave the served one in place.
            self._start_configuration(self._backend_configuration)
            with self._lock:
                # Cleared only now the start has succeeded, so a failure is
                # retried by the next scenario rather than downgraded to
                # `/reset`, which does not change what is being served.
                self._scenario_configuration = None
            return

        if must_start:
            self._start()
            return

        status = self._call("/reset")

        if status in _NOT_IMPLEMENTED:
            # The documented fallback. Remembered so the probe costs one request
            # per suite rather than one per scenario.
            with self._lock:
                self._reset_supported = False
            self._start()
            return

        if not self._is_success(status):
            msg = f"POST /reset on {self._base_url} returned {status}"
            raise ControlApiError(msg)

        with self._lock:
            self._reset_supported = True

    def change_flag(self) -> None:
        """Mutate flag configuration so a conforming provider observes a change.

        ``/change`` must not return until the new value is actually being
        served, and that promise is about the **backend**. How long the
        *provider under test* takes to notice is what the suite's event timeout
        is for. There is deliberately no wait here: a backend that returns
        before it serves the new value makes the provider's detection latency
        unmeasurable, because the clock would start before there is anything to
        detect.
        """
        self._require("/change")

    def disconnect(self) -> None:
        """Make the backend unreachable, without touching any container.

        The backend *process* inside the still-running container is stopped --
        see the class documentation for why that distinction is a requirement.
        """
        with self._lock:
            self._backend_maybe_down = True
        self._require("/stop")

    def reconnect(self) -> None:
        """Make the backend reachable again, preserving flag state.

        Starting with the configuration already in effect restores the same
        baseline, so the provider observes a change in availability and never a
        change in flag values. "In effect" includes a configuration this scenario
        served: losing the connection is not how a scenario changes what the
        backend serves.
        """
        self._start()

    def serve_configuration(self, configuration: str) -> None:
        """Restart the backend on one of its own named flag configurations.

        Optional on a backend control and absent from the protocol -- see
        :func:`~.control.serve_configuration`, which is how a step reaches it.

        ``POST /start?config=...`` with the name given, which also seeds that
        configuration's flag state. It takes effect before the provider connects,
        because the step that names a configuration is the step that creates the
        provider; :meth:`reconnect` brings this configuration back rather than the
        suite's, and :meth:`prepare_scenario` takes the next scenario off it.
        """
        self._require("/start", {"config": configuration})
        with self._lock:
            self._scenario_configuration = configuration
            self._backend_maybe_down = False

    # No binding for `POST /restart`: no shipped scenario reaches it, and a
    # binding nothing can call misreports the contract by implying every backend
    # under test owes the endpoint. A `@caching` scenario asserting what a stale
    # provider serves *during* an outage would bring it back, needing the
    # flag-state preservation `/restart` has and `/stop` + `/start` does not.

    def _start(self) -> None:
        """Start the backend on the configuration in effect: the scenario's, else this suite's."""
        with self._lock:
            configuration = self._scenario_configuration or self._backend_configuration
        self._start_configuration(configuration)

    def _start_configuration(self, configuration: str) -> None:
        self._require("/start", {"config": configuration})
        with self._lock:
            self._backend_maybe_down = False

    def _require(self, path: str, query: dict[str, str] | None = None) -> None:
        """Perform a control call and fail on any non-2xx response."""
        status = self._call(path, query)
        if not self._is_success(status):
            msg = f"POST {path} on {self._base_url} returned {status}"
            raise ControlApiError(msg)

    def _call(self, path: str, query: dict[str, str] | None = None) -> int:
        """Perform one control-API request and return its status code.

        The response body is read and discarded: the control API's bodies are
        human-readable messages the TCK is specified never to interpret, and
        reading them lets the connection be released cleanly.
        """
        target = self._base_url + path
        if query:
            target += "?" + urllib.parse.urlencode(query)

        # An empty body rather than none, so the request carries Content-Length
        # even where a proxy in the stack insists on one. S310: __init__ rejects
        # any base_url that is not http(s), and target is that validated base URL
        # plus a literal path.
        request = urllib.request.Request(target, data=b"", method="POST")  # noqa: S310

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                response.read()
                return int(response.status)
        except urllib.error.HTTPError as error:
            # A status the server chose to report as an error is still an answer,
            # and /reset answering 404 is the documented "not implemented" -- so
            # this is a return, not a raise.
            with error:
                error.read()
            return int(error.code)
        except OSError as error:
            msg = (
                f"control request POST {target} failed: {error}. The control API must "
                f"stay reachable even while the backend is deliberately down, "
                f"otherwise an outage cannot be ended"
            )
            raise ControlApiError(msg) from error

    @staticmethod
    def _is_success(status: int) -> bool:
        return 200 <= status < 300


if typing.TYPE_CHECKING:
    # Static assertion, erased at runtime: a method renamed out of either control
    # protocol fails type-checking rather than at the first scenario that needs it.
    def _implements(
        control: HttpControl,
    ) -> tuple[BackendControl, ConnectionControl]:
        return control, control

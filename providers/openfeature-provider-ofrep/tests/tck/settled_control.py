"""``HttpControl``, plus a wait for a backend that returns before it serves.

**A named workaround for one backend's defect, in the adoption rather than in
the shared harness**, which is the shape Appendix F prescribes for exactly this
situation -- see "The control API" there for why a delay in the harness would be
the wrong instrument.

**The defect.** ``control-api.yaml`` requires ``POST /start`` not to return until
the state it reseeded is actually being served. flagd-testbed's launchpad returns
as soon as flagd answers ``/readyz``, which flagd does before its file sources
have reached the flag store.
`flagd-testbed#394 <https://github.com/open-feature/flagd-testbed/pull/394>`_
explains the mechanism, measures the window and closes it; it is open and
unmerged, so the window is still there.

**Why this suite is the one that found it.** Both flagd resolvers block inside
``initialize`` until their stream or ruleset is up, so their initialisation
absorbs the window before any scenario evaluates. A stateless provider has no
initialisation to hide behind: its first evaluation lands directly in the gap and
the suite reports FLAG_NOT_FOUND for every flag, which reads as a
catastrophically broken provider. This wait goes away the day the testbed does.

**Why it is not cheating.** It manipulates nothing. It is a readiness probe over
the same public OFREP endpoint the provider uses, on a canonical flag, asserting
only that the backend finished what ``/start`` already promised. No scenario is
weakened and no side channel into the backend is opened -- the normative control
path is still ``HttpControl``, which this delegates to unchanged.

Deliberately not a :class:`ConnectionControl`: it has no ``disconnect`` or
``reconnect``, matching a suite that declares neither ``STALE`` nor
``UNAVAILABLE_INIT``. The two omissions keep each other honest.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from openfeature.contrib.tools.tck import ControlApi, HttpControl

__all__ = ["SettledControl"]

PROBE_FLAG_KEY = "boolean-flag"
"""A canonical flag, used only to ask whether the flag set is being served yet."""

SETTLE_TIMEOUT_SECONDS = 15.0
"""How long to wait for the backend to serve the flag set after ``/start``.

Two orders of magnitude above the ~40ms observed, because the cost of being
generous is nothing -- the loop exits on the first success -- while the cost of
being tight is a suite that fails intermittently on a loaded CI runner and gets
diagnosed as a provider bug.
"""

SETTLE_POLL_SECONDS = 0.02


class SettledControl:
    """Delegates to :class:`HttpControl`, then waits for the flags to appear."""

    def __init__(
        self,
        control: HttpControl,
        ofrep_url: str,
        *,
        timeout: float = SETTLE_TIMEOUT_SECONDS,
    ) -> None:
        self._control = control
        self._probe_url = (
            f"{ofrep_url.rstrip('/')}/ofrep/v1/evaluate/flags/{PROBE_FLAG_KEY}"
        )
        self._timeout = timeout

    @property
    def description(self) -> str:
        return f"{self._control.description}, awaited through the OFREP endpoint"

    @property
    def control_api(self) -> ControlApi:
        """Whatever the control being delegated to says, which is ``"http"``.

        Forwarded rather than answered, because this class adds a readiness
        probe and manipulates nothing: the normative control path is still the
        HTTP control API, and a report that said otherwise would understate what
        was exercised.
        """
        return self._control.control_api

    def prepare_scenario(self) -> None:
        self._control.prepare_scenario()
        self._await_flags()

    def change_flag(self) -> None:
        self._control.change_flag()

    def _await_flags(self) -> None:
        """Block until the probe flag resolves, or fail saying what was seen.

        Raising rather than proceeding is deliberate. A scenario allowed to run
        against a backend that is not serving its flag set does not report a
        harness problem; it reports FLAG_NOT_FOUND as a conformance result,
        which is the one outcome a conformance suite must never produce.
        """
        deadline = time.monotonic() + self._timeout
        last = "no response"

        while time.monotonic() < deadline:
            status, body = self._probe()
            if status == 200:
                return
            last = f"HTTP {status}: {body}"
            time.sleep(SETTLE_POLL_SECONDS)

        msg = (
            f"the backend did not serve {PROBE_FLAG_KEY!r} within {self._timeout}s of "
            f"a successful control-API reseed. Last response from {self._probe_url}: "
            f"{last}. This is a problem with the stack under test or its control API, "
            f"not with the provider"
        )
        raise RuntimeError(msg)

    def _probe(self) -> tuple[int, str]:
        request = urllib.request.Request(  # noqa: S310
            self._probe_url,
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5.0) as response:  # noqa: S310
                return int(response.status), ""
        except urllib.error.HTTPError as err:
            return int(err.code), err.read().decode("utf-8", "replace")[:200]
        except (urllib.error.URLError, OSError) as err:
            return 0, str(err)

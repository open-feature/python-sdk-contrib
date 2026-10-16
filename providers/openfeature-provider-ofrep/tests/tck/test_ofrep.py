"""The OpenFeature provider conformance suite, run against the OFREP provider.

OFREP is the vendor-neutral remote evaluation protocol, so what is under test
here is a pure mapping: one HTTP request per evaluation, and the translation of
its JSON response -- or its error status -- into typed resolution details. There
is no cache, no stream and no local ruleset.

The backend is flagd, which serves OFREP on port 8016 alongside its own
protocols, driven through the same launchpad control API and seeded with the
same canonical flag set as the flagd conformance suites -- so a difference in
the results is a difference an application would see when it switches provider.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.provider.ofrep import OFREPProvider
from openfeature.contrib.tools.tck import (
    BackendControl,
    Capability,
    TckConfig,
    feature_paths,
)
from openfeature.provider import FeatureProvider

TIMEOUT_SECONDS = 10.0
"""Bounds a single OFREP request.

Generous, because every scenario is preceded by a control-API ``/start`` that
restarts the flagd process. It is the only timing knob this provider has
(``ofrep/__init__.py:52``).
"""

# Every capability below was declared, the suite run, and its scenarios seen to
# pass -- bar the one row named under VARIANTS. The code references say where the
# behaviour lives, so a reader can check the claim.
#
#   OBJECT      ofrep/__init__.py:105-113, and the type check at
#               ofrep/__init__.py:248 admits `(dict, list)` -- so a JSON object
#               comes back as one rather than rejected or flattened.
#   VARIANTS    ofrep/__init__.py:160 carries the response's `variant` into the
#               details. Seven of the outline's eight rows pass; the eighth asks
#               for `large-integer-flag`, which no released flagd-testbed seeds
#               (see conftest.py). Withholding over it would say this provider
#               does not name variants, which the other seven rows show is false.
#   TARGETING   ofrep/__init__.py:229-230 puts the targeting key into the request
#               body's `context`, so flagd evaluates the rule against it. All
#               three scenarios pass, and for a protocol with no types on the
#               wire that is the whole of what passthrough can verify: the key
#               reached flagd.
#   STANDARD_REASONS
#               Eight of the file's nine scenarios run here and all eight pass.
#               The ninth composes with @disabled-flags, withheld below, so it
#               skips with that reason.
#
#   STRING_TYPING and FULLY_TYPED_VALUES
#     Both declared, on a run: all four scenarios pass. **"Untyped protocol" is
#     not the same claim as "untyped backend"**, and this is the tag where the
#     two come apart. OFREP carries no *requested* type on the wire -- which is
#     exactly why boolean-flag satisfies an Integer request here and is xfailed
#     in conftest.py -- but the response body is JSON, and JSON distinguishes
#     `true` from `"true"` and `10` from `"10"`. ofrep/__init__.py:249-256 maps
#     FlagType.STRING to the bare `str`, so a bool, a number or a structure
#     fails that isinstance and becomes TYPE_MISMATCH; `str` is not in bool's
#     ancestry, so the subclass hazard behind the xfail has no counterpart here.
#     Both tags rest on a run rather than on the protocol, because what they ask
#     about is the backend's storage: flagd holds typed variants, and the same
#     provider over a string-storing backend would withhold one or both.
#
# Not declared, and why.
#
#   NUMERIC_COERCION
#     Withheld, because this provider does not coerce at all -- and a declarer
#     must satisfy all three scenarios. json.loads yields `int` for 10 and
#     `float` for 0.5, and ofrep/__init__.py:249-256 admits a value only on an
#     exact isinstance against one of them, so float-flag as an Integer is a
#     TYPE_MISMATCH rather than a silent 0, and integer-flag as a Float fails.
#     No KnownDeviation: nothing requires numeric coercion.
#
#   DISABLED_FLAGS
#     Withheld, and **this is the one declaration here that should change
#     shape**: the provider attempts the behaviour and fails on one
#     unconditional index, which is the declare-and-deviate case. Declaring the
#     tag fails all four rows on the error code rather than the value. flagd
#     answers a disabled flag with a reason and no `value` and no `variant`; the
#     absent value is not the obstacle, because ofrep/__init__.py:153 already
#     reads `data.get("value", default_value)`. What fails is
#     ofrep/__init__.py:160, indexing `data["variant"]` unconditionally where
#     types.md types the field optional -- so **the whole difference between
#     passing and failing these four rows is one `.get`**, and the same index
#     breaks on any variant-less OFREP response. open-feature/python-sdk-contrib
#     #418; the next change here declares the tag and records the deviation.
#
#   Everything below follows from the provider being stateless: it holds a
#   requests.Session and a rate-limit timestamp, and nothing else survives
#   between evaluations.
#
#   LIFECYCLE
#     `initialize` is inherited from AbstractProvider and is `pass`, so nothing
#     contacts the backend before the first evaluation and initialisation has no
#     outcome to observe.
#
#   EVENTS
#     `_on_emit` is never called anywhere in ofrep/__init__.py: no stream, no
#     poll, no background thread. Declaring it would make the readiness scenario
#     pass without demonstrating anything, because the SDK's registry dispatches
#     PROVIDER_READY around `initialize` for any provider (python-sdk
#     openfeature/provider/_registry.py:73-77).
#
#   STALE, CONFIGURATION_CHANGE
#     Both follow from EVENTS: every evaluation is an independent HTTP request,
#     so no state between them can go stale and nothing watches the backend. A
#     *change* is nonetheless visible to an application -- the next evaluation
#     returns the new value -- but the signal is not.
#
#   UNAVAILABLE_INIT
#     A provider pointed at a closed port reaches READY, because `initialize`
#     does nothing and the registry dispatches PROVIDER_READY unconditionally.
#     The failure surfaces on the first evaluation as GeneralError from
#     ofrep/__init__.py:167 rather than as PROVIDER_ERROR, so the scenario's
#     premise does not hold -- and no `new_unavailable_provider` is supplied.
#
#   REINITIALIZATION
#     Reuse would in fact work -- nothing to release and nothing to rebuild --
#     but the scenario inherits @lifecycle from its feature, withheld above, so
#     declaring this would leave the claim unexamined.
#
#   LARGE_INTEGERS
#     The one withholding here that is about the backend rather than the
#     provider: the tag's one scenario asks for `huge-integer-flag` and no
#     released flagd-testbed seeds it. Nothing in this path would narrow the
#     value -- a JSON number decodes into an unbounded Python `int` and the type
#     check admits it unchanged -- and the suite cannot show that, which is the
#     point. Declare the tag once open-feature/flagd-testbed#392 is in the
#     image, or the withholding starts reading as a claim about the provider.
#
#   CACHING
#     No scenario carries the tag.
CAPABILITIES = frozenset(
    {
        Capability.OBJECT,
        Capability.VARIANTS,
        Capability.STRING_TYPING,
        Capability.FULLY_TYPED_VALUES,
        Capability.TARGETING,
        Capability.STANDARD_REASONS,
    }
)


@pytest.fixture(scope="session")
def tck_config(
    ofrep_base_url: str,
    ofrep_control: BackendControl,
) -> TckConfig:
    """Wire the provider up to the running testbed.

    Both fixtures come from ``tests/tck/conftest.py`` and both resolve after the
    TCK has started the stack, which is when the mapped host port exists.
    """
    base_url = ofrep_base_url

    def new_provider() -> FeatureProvider:
        return OFREPProvider(base_url, timeout=TIMEOUT_SECONDS)

    return TckConfig(
        name="ofrep",
        control=ofrep_control,
        new_provider=new_provider,
        capabilities=CAPABILITIES,
    )


scenarios(*feature_paths())

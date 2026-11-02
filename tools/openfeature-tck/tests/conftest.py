"""Known deviations of the Python SDK, recorded rather than hidden.

A conformance suite that quietly goes green on scenarios it did not run is worse
than no suite at all -- and the same is true of one that quietly goes green on a
scenario it *did* run and fail. So the one scenario the Python SDK cannot
currently satisfy is recorded twice, in two forms that answer different
questions.

``xfail(strict=True)`` keeps the *run* honest: the scenario is expected to fail,
and the suite fails if it ever passes, so the marker is removed the moment the
SDK is fixed rather than lingering as a lie.

:class:`KnownDeviation` keeps the *report* honest. The results payload reports
the scenario as failed regardless of the marker -- an expected failure is still a
failure, and softening it there would hide exactly what the marker exists to keep
visible -- and the envelope carries the acknowledgement beside it, with the issue
it is tracked under. That is what lets a consumer tell a known and tracked gap
from a surprise without the result itself being weakened.

The two are declared together here so they cannot drift: the reason on the marker
and the summary in the report are the same sentence.
"""

from __future__ import annotations

import pytest

from openfeature.contrib.tools.tck import KnownDeviation

# The Scenario Outline row that asks for boolean-flag as an Integer.
_BOOL_AS_INT = (
    "test_requesting_the_wrong_type_returns_the_code_default[boolean-flag-Integer-1]"
)

_ISSUE = "https://github.com/open-feature/python-sdk/issues/619"

_REASON = (
    "python-sdk: a boolean satisfies an Integer request. The client type-checks with "
    "isinstance(value, int) and bool is a subclass of int in Python, so boolean-flag "
    "requested as an Integer returns True with reason STATIC and no error code, where "
    "the specification requires the code default and TYPE_MISMATCH. "
    f"See {_ISSUE}"
)

KNOWN_DEVIATIONS = (KnownDeviation(issue=_ISSUE, summary=_REASON),)
"""What the report acknowledges.

No ``capability``: the scenario carries no capability tag, because returning the
code default on a type mismatch is mandatory. ``@numeric-coercion`` is a
neighbouring question -- whether 0.5 satisfies an integer request -- and this
provider answers *that* one the way the tag asks, by refusing it, so attributing
the deviation there would be wrong twice over.

Which is not the same as satisfying the capability, and the distinction matters
now that Appendix F has corrected its note on it. The tag is withheld here
because this provider does not coerce at all: it passes the lossy row by
rejecting every float, which is the shortcut the two lossless rows exist to
catch, and it fails both of those. That is the withholding the appendix still
calls right -- a provider that cannot attempt the behaviour -- rather than the
one it now rules out, where a provider attempts it and gets a direction wrong.
The boolean-as-Integer gap is a third thing again: mandatory, ungated, and the
reason this entry names no capability.
"""


@pytest.fixture(scope="session")
def tck_known_deviations() -> tuple[KnownDeviation, ...]:
    """The deviations a suite in this package declares.

    A fixture rather than an import so that the marker below and the report's
    acknowledgement are written down once, in one place, and a suite picks it up
    the same way it picks up everything else it is given.
    """
    return KNOWN_DEVIATIONS


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.name == _BOOL_AS_INT:
            item.add_marker(pytest.mark.xfail(reason=_REASON, strict=True))

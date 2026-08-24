"""Known deviations of the Python SDK, recorded rather than hidden.

A conformance suite that quietly goes green on scenarios it did not run is worse
than no suite at all -- and the same is true of one that quietly goes green on a
scenario it *did* run and fail. So the one scenario the Python SDK cannot
currently satisfy is marked ``xfail(strict=True)`` here, which:

* keeps it visible in the report, as XFAIL with the reason attached;
* fails the suite if it ever *passes*, so the marker is removed the moment the
  SDK is fixed rather than lingering as a lie.

This lives in the TCK's own self-test rather than in the shared package. It is a
fact about the SDK under test, not part of the conformance definition, and
Appendix F deliberately leaves a general "known deviations" concept as an open
question (spec#417, Q4). If that concept lands, this moves into it.
"""

from __future__ import annotations

import pytest

# The Scenario Outline row that asks for boolean-flag as an Integer.
_BOOL_AS_INT = "test_requesting_the_wrong_type_returns_the_code_default[boolean-flag-Integer-1]"

_REASON = (
    "python-sdk: a boolean satisfies an Integer request. The client type-checks with "
    "isinstance(value, int) and bool is a subclass of int in Python, so boolean-flag "
    "requested as an Integer returns True with reason STATIC and no error code, where "
    "the specification requires the code default and TYPE_MISMATCH. "
    "See https://github.com/open-feature/python-sdk/issues/619"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.name == _BOOL_AS_INT:
            item.add_marker(pytest.mark.xfail(reason=_REASON, strict=True))

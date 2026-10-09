"""The canonical scenario set, and whether a run actually executed it.

A conformance suite that goes green on scenarios it did not run is worse than no
suite. The capability gate already rules out the loud version of that -- an
undeclared capability is reported as skipped, with its reason, never as passed --
but it says nothing about the quiet version, where the scenarios were never asked
for in the first place. A ``-k`` expression, a ``-m`` filter, a ``--deselect``, a
test module that stopped calling ``scenarios()`` on the canonical path: each of
those runs less of the suite and none of them is an error. The Go implementation
measured it. ``-run`` on a single scenario passed green and emitted a well-formed
report covering one scenario out of the whole canonical set, and nothing in the
document said so.

So the run is checked against what this distribution *ships* rather than against
what it was asked to run. The expectation is compiled from the packaged feature
files with the same Gherkin compiler that produces the results payload, which
means it is one entry per Scenario Outline row -- the granularity the runner
generates and therefore the only one a comparison can be made at.

Two properties this has to have, and both are about what may close a gap.

**A skip counts; an absence does not.** A scenario the capability gate skipped
did run: it was asked, and the report accounts for it with a reason. A scenario
that was never collected is missing, and no declaration makes it otherwise.

**An extension cannot close a gap.** An adopter's own scenarios are matched by
neither uri nor path against the packaged set, and the executed side of the
comparison is filtered to files that are genuinely inside this distribution --
not merely to files reported under the canonical prefix, so that the check does
not rest on the same derivation it is meant to corroborate.
"""

from __future__ import annotations

import functools
import os
import typing

from .extensions import canonical_root, is_canonical, uri_for
from .messages import FeatureCatalog, ScenarioKey, ScenarioRun

__all__ = [
    "PARTIAL_ENV",
    "canonical_scenarios",
    "describe",
    "missing_canonical",
    "partial_run_allowed",
]

PARTIAL_ENV = "TCK_PARTIAL"
"""Set to acknowledge that a run is deliberately not a conformance run.

For working on one scenario with ``-k`` without the guard failing the run. It
never makes a partial run publishable: no report is written for a suite that did
not execute the canonical set, with or without it. The Java TCK spells the same
escape hatch the same way, so the two are one thing to know rather than two.
"""

_TRUTHY = {"1", "true", "yes", "on"}


def partial_run_allowed(environment: typing.Mapping[str, str] | None = None) -> bool:
    """Whether the run has declared itself partial."""
    source = os.environ if environment is None else environment
    return source.get(PARTIAL_ENV, "").strip().lower() in _TRUTHY


@functools.cache
def canonical_scenarios() -> frozenset[ScenarioKey]:
    """Every scenario the packaged feature files define, row by row.

    Empty when the assets are not reachable as files -- an installation from a
    zipimport, say. Everything built on this then degrades to "cannot tell",
    which is the honest answer and never a false accusation.

    Cached because it is the same answer for the whole process and parsing it is
    the same work the results payload already does.
    """
    root = canonical_root()
    if root is None or not root.is_dir():
        return frozenset()

    catalog = FeatureCatalog()
    for path in sorted(root.rglob("*.feature")):
        uri = uri_for(path)
        if uri is not None:
            catalog.load_file(uri, path)
    return catalog.scenario_keys


def missing_canonical(runs: typing.Iterable[ScenarioRun]) -> tuple[ScenarioKey, ...]:
    """The canonical scenarios this suite did not execute, in reporting order.

    ``runs`` is everything the suite accounted for, extensions included; only
    the ones whose feature file is genuinely one of the packaged assets are
    counted, so an adopter's scenario can neither fill a gap nor be blamed for
    one.
    """
    expected = canonical_scenarios()
    if not expected:
        return ()
    executed = {
        (run.identity.uri, run.identity.name, run.identity.example)
        for run in runs
        if is_canonical(run.identity.path)
    }
    return tuple(sorted(expected - executed))


def describe(key: ScenarioKey) -> str:
    """One missing scenario, named the way a failure message should name it."""
    uri, name, row = key
    if not row:
        return f"{uri}: {name}"
    cells = " ".join(f"{header}={cell}" for header, cell in row)
    return f"{uri}: {name} [{cells}]"

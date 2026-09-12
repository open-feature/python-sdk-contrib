"""What an adoption may declare about its provider, and what it may not.

A ``TckConfig`` is two things at once. It is the configuration a run needs, and
it is a *declaration*: the set of claims an adopter makes about the provider,
which is what turns a skipped scenario from a hole in the run into a recorded
answer. Everything checked here belongs to the second role, so none of it is
observable in the pass/fail of a suite -- which is exactly why it is pinned by
tests of its own rather than by the conformance suites.

The declaration vocabulary is public because something outside this package has
to read it back. A reporter deciding whether a skip was legitimate needs the tag
lookup and the reserved set; a comparison page needs to tell a declined
capability from an impossible one. None of those consumers is here, and the API
is complete for them anyway -- a follow-up that adds one should widen nothing.

The one property that makes "reserved" mean anything is checked against the
packaged assets rather than asserted: a reserved tag is reserved because no
canonical scenario carries it, and that stops being true the moment the spec
adds one.
"""

from __future__ import annotations

import re
import typing

import pytest

from openfeature.contrib.tools.tck import (
    DECLARABLE_CAPABILITIES,
    RESERVED_CAPABILITIES,
    BackendControl,
    Capability,
    ControlApi,
    InProcessControl,
    KnownDeviation,
    TckConfig,
    canonical_root,
)
from openfeature.contrib.tools.tck.capability import (
    capability_for_marker,
    capability_for_tag,
)


class _StubControl:
    """A control that says nothing it is not obliged to say.

    Which no longer includes ``control_api``: it is a required member of
    ``BackendControl``, so even a stub has to answer it.
    """

    def prepare_scenario(self) -> None: ...

    def change_flag(self) -> None: ...

    @property
    def description(self) -> str:
        return "a stub"

    @property
    def control_api(self) -> ControlApi:
        return "in-process"


def _config(**overrides: typing.Any) -> TckConfig:
    """A configuration that is valid but declares nothing in particular."""
    settings: dict[str, typing.Any] = {
        "name": "stub",
        "control": _StubControl(),
        "new_provider": lambda: None,
        "capabilities": frozenset(),
    }
    settings.update(overrides)
    return TckConfig(**settings)


def _canonical_tags() -> set[str]:
    """Every tag the packaged feature files carry, at any level.

    Read off tag lines only. A tag is the whole of the line it appears on in
    Gherkin, which is what tells one apart from the same word written in a
    comment -- ``events.feature`` mentions ``@caching`` in prose, saying where
    those scenarios will go once they exist.
    """
    tags: set[str] = set()
    root = canonical_root()
    assert root is not None, "the packaged canonical features are not on a filesystem"
    for feature in sorted(root.glob("*.feature")):
        for line in feature.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("@"):
                tags.update(re.findall(r"@[\w-]+", stripped))
    return tags


# -- the vocabulary ----------------------------------------------------------


def test_every_capability_is_either_declarable_or_reserved() -> None:
    """Two sets, one enum, and no member in both or neither.

    ``DECLARABLE_CAPABILITIES`` is derived from ``RESERVED_CAPABILITIES`` rather
    than listed beside it, so this is really a check that the derivation is the
    one the documentation promises.
    """
    assert frozenset(Capability) == DECLARABLE_CAPABILITIES | RESERVED_CAPABILITIES
    assert not DECLARABLE_CAPABILITIES & RESERVED_CAPABILITIES
    assert RESERVED_CAPABILITIES, "the whole rule is vacuous if nothing is reserved"

    for capability in Capability:
        assert capability.reserved is (capability in RESERVED_CAPABILITIES)


def test_a_reserved_capability_is_one_no_canonical_scenario_carries() -> None:
    """The fact the rule rests on, read off the assets rather than asserted.

    "Reserved" claims that nothing carries the tag, so declaring it cannot be
    verified. When the specification gives a reserved tag a scenario, that stops
    being true and this fails -- which is the moment the capability should become
    declarable, and the moment somebody has to notice. It has already happened
    once: ``@targeting`` gained three scenarios at spec revision ``26362f85``
    and moved out of the reserved set, which is what this half is for.

    The other half is the converse, and it is the half that catches a tag added
    to the enum and never wired to anything: every declarable capability must be
    carried by some canonical scenario, or declaring it examines nothing.
    """
    carried = _canonical_tags()
    for capability in RESERVED_CAPABILITIES:
        assert capability.tag not in carried, (
            f"{capability.tag} is no longer reserved: the canonical assets now "
            f"carry it, so it can be verified and should be declarable"
        )
    for capability in DECLARABLE_CAPABILITIES:
        assert capability.tag in carried, (
            f"{capability.tag} is declarable but no canonical scenario carries "
            f"it, so declaring it would be a claim nothing examines"
        )


def test_a_tag_maps_onto_the_capability_it_gates() -> None:
    """The lookup a reporter outside this package needs, in the tag form.

    The tag form rather than the marker form, because that is the form a
    scenario's tags are recorded in: deciding whether a skip was legitimate
    means reading them back as the feature files spell them. Nothing in this
    package calls it -- it is exported for the consumer that does.
    """
    for capability in Capability:
        assert capability_for_tag(capability.tag) is capability
        assert capability_for_marker(capability.value) is capability

    # An organisational tag gates nothing, and must not be mistaken for a
    # capability: the feature files carry them freely.
    assert capability_for_tag("@smoke") is None
    assert capability_for_tag("events") is None, "the at-sign is part of the tag"


# -- declaring a capability set ----------------------------------------------


def test_the_default_is_every_declarable_capability() -> None:
    """And so cannot pick up a reserved tag on the way past.

    "Declare everything, then narrow it" is the advice, which makes the default
    the one place a reserved tag would otherwise get declared by accident. One
    implementation's published report asserts ``@targeting`` and ``@caching``
    for precisely that reason -- back when both were reserved.
    """
    # Not routed through ``_config``, which narrows the set: the field default is
    # the whole point of this one. It needs an unavailable-provider factory
    # because ``@unavailable`` is declarable, so the default declares it.
    settings: dict[str, typing.Any] = {
        "name": "stub",
        "control": _StubControl(),
        "new_provider": lambda: None,
        "new_unavailable_provider": lambda: None,
    }
    declared = TckConfig(**settings).capabilities
    assert declared == DECLARABLE_CAPABILITIES
    for capability in RESERVED_CAPABILITIES:
        assert capability not in declared


def test_a_capability_set_is_normalised_however_it_was_written() -> None:
    """A list, a set or a generator all arrive as the same frozenset."""
    expected = frozenset({Capability.EVENTS, Capability.OBJECT})
    written = [
        [Capability.EVENTS, Capability.OBJECT, Capability.EVENTS],
        {Capability.EVENTS, Capability.OBJECT},
        (c for c in (Capability.EVENTS, Capability.OBJECT)),
    ]
    for capabilities in written:
        assert _config(capabilities=capabilities).capabilities == expected


def test_something_that_is_not_a_capability_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown capabilities"):
        _config(capabilities={"events"})


def test_a_reserved_capability_cannot_be_declared() -> None:
    """A tag no scenario carries is a claim nothing can check, so it is refused.

    At construction rather than at the point something reads the declaration:
    the adopter wrote it down and meant something by it, so a configuration
    silently different from the one they wrote is worse than one that will not
    build -- and construction is where their own code is still on the stack to
    say which line to fix.
    """
    for reserved in RESERVED_CAPABILITIES:
        with pytest.raises(ValueError, match=f"reserved capabilities {reserved.tag}"):
            _config(capabilities={Capability.EVENTS, reserved})


def test_the_refusal_says_what_may_be_declared_instead() -> None:
    """A message that names the rule and not just the violation.

    The offending capability is taken from ``RESERVED_CAPABILITIES`` rather than
    named, because naming one is how this test went stale: it asked about
    ``@targeting``, which stopped being reserved the moment the specification
    gave it scenarios, and the refusal it was asserting became correct
    behaviour's absence.
    """
    reserved = next(iter(sorted(RESERVED_CAPABILITIES, key=lambda c: c.tag)))
    with pytest.raises(ValueError) as raised:
        _config(capabilities={reserved})
    message = str(raised.value)
    assert "DECLARABLE_CAPABILITIES" in message
    for capability in DECLARABLE_CAPABILITIES:
        assert capability.tag in message


# -- acknowledging a gap -----------------------------------------------------


ISSUE = "https://github.com/open-feature/python-sdk/issues/619"


def test_a_known_deviation_carries_its_capability_only_when_it_has_one() -> None:
    """A deviation against a mandatory, ungated scenario belongs to no capability.

    Omitted rather than null, because the field is the answer to "which
    capability does this concern" and there is not always one.
    """
    mandatory = KnownDeviation.tracked(
        summary="a boolean satisfies an Integer", issue=ISSUE
    )
    assert mandatory.as_json() == {"issue": ISSUE, "summary": mandatory.summary}

    attributed = KnownDeviation.tracked(
        summary="a lossy float satisfies an Integer",
        issue=ISSUE,
        capability=Capability.NUMERIC_COERCION,
    )
    assert attributed.as_json() == {
        "issue": ISSUE,
        "summary": attributed.summary,
        "capability": Capability.NUMERIC_COERCION.tag,
    }


def test_an_untracked_deviation_is_a_form_of_its_own() -> None:
    """Because a gap with nowhere to point at is still worth naming.

    Naming the defect is what separates it from a capability the provider chose
    to withhold; a declaration that merely omits the tag cannot say which of the
    two happened. This suite had no way to record one until now -- ``issue`` was
    required -- and was the only one of the four that had not.

    ``issue`` is left out of the payload rather than sent as null: the report
    schema types it as a uri-formatted string when present, and requires only
    ``summary``.
    """
    untracked = KnownDeviation.untracked(
        summary="the lossy half of the coercion rule is not enforced",
        capability=Capability.NUMERIC_COERCION,
    )

    assert not untracked.is_tracked
    assert untracked.issue is None
    assert untracked.as_json() == {
        "summary": untracked.summary,
        "capability": Capability.NUMERIC_COERCION.tag,
    }

    assert KnownDeviation.tracked(summary="a gap", issue=ISSUE).is_tracked


def test_a_deviation_with_no_summary_is_refused() -> None:
    """It records that something is wrong without saying what.

    Which leaves a reader worse off than the bare skip or failure it
    accompanies, and it is the one field the report schema requires. Refused at
    construction, where the adopter's own code is still on the stack to say
    which line to fix.
    """
    with pytest.raises(ValueError, match="known_deviations\\[0\\] has no summary"):
        _config(known_deviations=[KnownDeviation.untracked(summary="   ")])


def test_a_deviation_may_not_name_a_reserved_capability() -> None:
    """No scenario carries the tag, so there is nothing to deviate from.

    The same reason declaring one is refused: there is no failure and no skip
    for the deviation to explain, so the entry would tell a reader only that
    something was claimed about something nothing examined.
    """
    reserved = next(iter(RESERVED_CAPABILITIES))
    with pytest.raises(ValueError) as raised:
        _config(
            known_deviations=[
                KnownDeviation.untracked(summary="a gap", capability=reserved)
            ]
        )

    message = str(raised.value)
    assert f"names the reserved capability {reserved.tag}" in message
    assert "nothing was failed or skipped" in message


def test_known_deviations_are_normalised_and_change_nothing_about_the_run() -> None:
    """Declared as any sequence; read as a tuple.

    And that is all they do. A deviation is an acknowledgement, not a licence:
    nothing here makes a scenario pass, skip, or be collected differently, which
    is why a suite declaring one still fails on it.
    """
    deviation = KnownDeviation.tracked(
        summary="a gap", issue="https://example.invalid/1"
    )
    config = _config(known_deviations=[deviation])
    assert config.known_deviations == (deviation,)
    assert _config().known_deviations == ()
    assert _config(known_deviations=[deviation]).capabilities == _config().capabilities


# -- saying how the backend is driven ----------------------------------------


def test_a_control_that_does_not_say_is_not_a_backend_control() -> None:
    """``control_api`` is required, and the protocol is where that is enforced.

    Nothing outside a control can tell whether it spoke the normative HTTP API
    or reached into this process, which is the argument for making the control
    say rather than for letting the field be absent: every run is one or the
    other, so an omitted value is not "no claim made" but an unfalsifiable one.

    ``BackendControl`` is runtime-checkable, so this is checked at the seam as
    well as by the type checker -- which matters for an adopter who writes a
    custom control in an untyped test module.
    """

    class _Quiet:
        def prepare_scenario(self) -> None: ...

        def change_flag(self) -> None: ...

        @property
        def description(self) -> str:
            return "a control that will not say"

    assert not isinstance(_Quiet(), BackendControl)
    assert isinstance(_StubControl(), BackendControl)


def test_in_process_control_says_it_is_in_process() -> None:
    """The narrow allowance, and the control that exists to take it.

    A provider that does have a backend and reports this is claiming something
    it should not, which is only detectable if the honest case says so plainly.
    """
    control = InProcessControl()
    assert isinstance(control, BackendControl)
    assert control.control_api == "in-process"


def test_the_control_api_type_is_closed_to_the_two_values_the_schema_allows() -> None:
    """Closed, so a third value is a type error rather than an invalid report.

    ``ControlApi`` is exported for exactly this: a custom control annotates its
    own property with it and the type checker refuses ``"HTTP"`` or ``"grpc"``
    before either becomes a report that fails schema validation with nothing to
    point at locally.
    """
    assert typing.get_args(ControlApi) == ("http", "in-process")

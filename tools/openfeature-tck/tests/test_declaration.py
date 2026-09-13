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

import types
import typing
from pathlib import Path

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
    plugin,
)
from openfeature.contrib.tools.tck.capability import (
    capability_for_marker,
    capability_for_tag,
    expired_reservations,
)
from openfeature.contrib.tools.tck.extensions import canonical_tags


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

    This half is now also enforced on every adoption's run, by the plugin, and
    not only here -- a self-test of this package is read by whoever changes this
    package, and the reservation expires somewhere else. What stays here is the
    converse, which is the half that catches a tag added to the enum and never
    wired to anything: every declarable capability must be carried by some
    canonical scenario, or declaring it examines nothing.
    """
    carried = canonical_tags()
    assert not expired_reservations(carried), (
        "the canonical assets now carry a reserved tag, so it can be verified "
        "and should be declarable"
    )
    for capability in DECLARABLE_CAPABILITIES:
        assert capability.tag in carried, (
            f"{capability.tag} is declarable but no canonical scenario carries "
            f"it, so declaring it would be a claim nothing examines"
        )


def test_the_packaged_tags_are_read_off_tag_lines_and_not_out_of_prose() -> None:
    """The one way this scan can be wrong, pinned against the real assets.

    ``events.feature`` mentions ``@caching`` in a comment, saying where those
    scenarios will go once they exist. A scan that read the whole file rather
    than its tag lines would call the reservation expired on the strength of
    that sentence, and since the plugin fails a run over an expiry, every
    adoption would fail over a sentence.

    The second assertion is what keeps the first from being vacuous: it checks
    that the prose mention is still there to be mis-read.
    """
    tags = canonical_tags()
    assert "@events" in tags, "a tag line is read"
    assert "@caching" not in tags, "prose is not"

    root = canonical_root()
    assert root is not None, "the packaged canonical features are not on a filesystem"
    mentions = [
        feature
        for feature in sorted(root.rglob("*.feature"))
        if "@caching" in feature.read_text(encoding="utf-8")
    ]
    assert mentions, "nothing mentions @caching any more, so this proves nothing"


def test_a_reservation_expires_when_a_scenario_carries_it() -> None:
    """The detection itself, which is all the plugin adds to it.

    Deduplicated, because the tags arrive from every scenario of every feature
    file and one carried twice is not two expiries.
    """
    reserved = sorted(RESERVED_CAPABILITIES, key=lambda c: c.tag)

    assert expired_reservations(["@events", "@object"]) == ()
    assert expired_reservations(c.tag for c in reserved) == tuple(reserved)

    first = reserved[0]
    assert expired_reservations([first.tag, first.tag, "@events"]) == (first,)


def _scenario_item(filename: str, *tags: str) -> typing.Any:
    """A collected node shaped the way pytest-bdd shapes one.

    ``__scenario__`` on the generated function, carrying the feature it came
    from, and the tags as the markers pytest-bdd turns them into. Those two are
    the whole of what the check reads off a node.

    Markers rather than the scenario's own ``tags``, which is the same choice
    the capability gate makes and for the same reason: pytest-bdd applies a
    marker for every tag on the scenario, on its feature *and* on its rule, so
    a feature-level tag is absent from ``Scenario.tags`` and gates every
    scenario in the file regardless. Reading what the gate reads is what keeps
    the two from disagreeing about which scenarios are unclaimable.
    """
    feature = types.SimpleNamespace(filename=filename)
    function = types.SimpleNamespace()
    function.__scenario__ = types.SimpleNamespace(feature=feature)
    markers = [types.SimpleNamespace(name=tag.lstrip("@")) for tag in tags]
    return types.SimpleNamespace(function=function, iter_markers=lambda: iter(markers))


def _a_canonical_feature() -> str:
    root = canonical_root()
    assert root is not None, "the packaged canonical features are not on a filesystem"
    features = sorted(root.rglob("*.feature"))
    assert features, "the packaged canonical features are missing"
    return str(features[0])


def test_the_plugin_fails_a_run_over_an_expired_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An adopter's run, not merely this package's own tests.

    The self-test above is read by whoever changes this package, and a
    reservation expires in the specification repository instead -- so an
    adoption that re-pinned the assets and ran the suite would see the new
    scenarios skipped, for a capability it is refused permission to declare,
    and nothing would say so. This is what says so.

    The upstream half of the check: the tags come off the packaged files, so
    nothing an adopter's run does to its selection gets past it. The half that
    arrives from the adopter's own side is below.
    """
    items = [_scenario_item(_a_canonical_feature())]

    # Nothing has expired, which is the state every real run is in, and the
    # hook is then silent.
    plugin.pytest_collection_modifyitems(items)

    reserved = sorted(RESERVED_CAPABILITIES, key=lambda c: c.tag)
    monkeypatch.setattr(
        plugin, "canonical_tags", lambda: frozenset(c.tag for c in reserved)
    )

    with pytest.raises(pytest.UsageError) as raised:
        plugin.pytest_collection_modifyitems(items)

    message = str(raised.value)
    for capability in reserved:
        assert capability.tag in message
    # Named, because the fix is to edit that set against the specification and
    # nothing the run can do stands in for it.
    assert "RESERVED_CAPABILITIES" in message


def test_the_plugin_fails_a_run_over_an_adopters_own_reserved_tag(
    tmp_path: Path,
) -> None:
    """The same failure, arriving from the adopter's side instead of upstream.

    A reserved capability cannot be declared, so the capability gate skips
    every scenario carrying its tag -- an extension's included. That scenario
    can never run and can never be claimed, which is precisely what this check
    exists to surface, so where the tag came from changes the remedy and not
    the consequence. The check used to read the canonical set alone and let
    this one through.

    Nothing is monkeypatched here: the tag is reserved for real and it is the
    adopter's own scenario carrying it, which is the whole of the case.
    """
    reserved = sorted(RESERVED_CAPABILITIES, key=lambda c: c.tag)
    items = [
        _scenario_item(_a_canonical_feature()),
        _scenario_item(
            str(tmp_path / "extensions" / "vendor.feature"),
            *(capability.tag for capability in reserved),
        ),
    ]

    with pytest.raises(pytest.UsageError) as raised:
        plugin.pytest_collection_modifyitems(items)

    message = str(raised.value)
    for capability in reserved:
        assert capability.tag in message
    # Both remedies, because the check cannot tell which mistake it caught.
    assert "RESERVED_CAPABILITIES" in message, "the upstream remedy is named"
    assert "extensions/" in message, "so is the adopter's"


def test_a_scenario_this_suite_does_not_run_is_not_read(tmp_path: Path) -> None:
    """One pytest session can hold more than this suite.

    A project adopting the TCK may have a pytest-bdd suite of its own, and it
    is collected into the same session. Its tags are not this suite's business:
    a scenario of theirs tagged ``@caching`` is gated by nothing here, runs
    normally, and is claimed by nobody -- so failing their run over it would be
    an accusation about a file this package has no say in.

    The discriminator is the uri derivation, which answers for the canonical
    assets and for an ``extensions`` directory and for nothing else.
    """
    items = [
        _scenario_item(_a_canonical_feature()),
        _scenario_item(
            str(tmp_path / "features" / "billing.feature"),
            *(capability.tag for capability in RESERVED_CAPABILITIES),
        ),
    ]

    plugin.pytest_collection_modifyitems(items)


def test_the_plugin_leaves_a_session_that_is_not_running_the_suite_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The plugin is installed for every pytest run in the environment.

    Which makes the check's trigger part of its correctness: an unrelated test
    suite in a project that happens to depend on this package has no business
    failing over the contents of these feature files. So the check waits for a
    canonical scenario to be collected, and nothing but ``feature_paths()``
    produces one of those. A node that is not a scenario at all is not one.

    Neither is an adopter's extension, and that is the one asymmetry worth
    stating: an extension's tags are read, but an extension is not what says
    the suite is running. Nothing an adopter selects reaches that distinction
    anyway -- the hook is handed the whole collection before anything is
    deselected -- so this is about a session that genuinely collected no
    canonical scenario: somebody else's pytest-bdd suite, in an environment
    that merely has this package installed.
    """
    monkeypatch.setattr(
        plugin,
        "canonical_tags",
        lambda: frozenset(c.tag for c in RESERVED_CAPABILITIES),
    )

    not_a_scenario: typing.Any = types.SimpleNamespace()

    plugin.pytest_collection_modifyitems([])
    plugin.pytest_collection_modifyitems([not_a_scenario])
    plugin.pytest_collection_modifyitems([_scenario_item(__file__)])
    plugin.pytest_collection_modifyitems(
        [_scenario_item(str(tmp_path / "extensions" / "vendor.feature"))]
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

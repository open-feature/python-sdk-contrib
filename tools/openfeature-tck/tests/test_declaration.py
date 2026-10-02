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
    INEXPRESSIBLE_CAPABILITIES,
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
from openfeature.contrib.tools.tck import capability as capability_module
from openfeature.contrib.tools.tck import config as config_module
from openfeature.contrib.tools.tck.capability import (
    capability_for_marker,
    capability_for_tag,
    expired_reservations,
    unknown_capabilities,
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


def test_every_capability_is_declarable_reserved_or_inexpressible() -> None:
    """Three sets, one enum, and no member in two of them or in none.

    ``DECLARABLE_CAPABILITIES`` is derived from the other two rather than listed
    beside them, so this is really a check that the derivation is the one the
    documentation promises. It is worth pinning precisely because the third set
    is empty here: a derivation that quietly dropped it would look right in
    Python forever and be wrong the day an entry is added.

    Nothing may be both reserved and inexpressible. A reservation says no
    scenario anywhere carries the tag; inexpressibility says the scenarios exist
    and this SDK cannot put their question. The second presupposes what the first
    denies.
    """
    inexpressible = frozenset(INEXPRESSIBLE_CAPABILITIES)
    assert frozenset(Capability) == (
        DECLARABLE_CAPABILITIES | RESERVED_CAPABILITIES | inexpressible
    )
    assert not DECLARABLE_CAPABILITIES & RESERVED_CAPABILITIES
    assert not DECLARABLE_CAPABILITIES & inexpressible
    assert not RESERVED_CAPABILITIES & inexpressible
    assert RESERVED_CAPABILITIES, "the whole rule is vacuous if nothing is reserved"

    for capability in Capability:
        assert capability.reserved is (capability in RESERVED_CAPABILITIES)
        assert capability.inexpressible is (capability in inexpressible)


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


def test_the_canonical_assets_carry_no_tag_this_package_cannot_resolve() -> None:
    """The forward direction of the same fact, against the real assets.

    Every tag the specification puts on a canonical scenario is a capability,
    and Appendix F's capability table is the vocabulary the enum tracks. So a
    canonical tag that resolves to nothing means this package is behind the
    assets -- and unlike a reservation, which skips, an unknown tag leaves its
    scenarios mandatory for everybody.

    Enforced on every adoption's run too, by the plugin, for the reason the
    reserved check is: the assets move in the specification repository and a
    self-test here is read only by whoever changes this package.

    The detection itself is deduplicated and sorted, because the tags arrive
    from every scenario of every feature file.
    """
    assert unknown_capabilities(canonical_tags()) == ()

    assert unknown_capabilities(["@events", Capability.CACHING.tag]) == ()
    assert unknown_capabilities(["@nope", "@events", "@nope", "@also-nope"]) == (
        "@also-nope",
        "@nope",
    )


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


def test_the_plugin_fails_a_run_over_a_canonical_tag_it_cannot_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reserved check's own direction reversed, and the easier one to omit.

    A reserved tag is one this package knows and holds shut, and its scenarios
    skip. An *unknown* tag is one it has never heard of, and its scenarios do
    the opposite: an unknown tag gates nothing, so they stay mandatory for
    every adopter, and a provider that legitimately withholds the new
    capability goes red with no reason recorded anywhere.

    This is not hypothetical here. Spec revision ``bda599f1`` split
    ``@string-typing`` and put ``@fully-typed-values`` in the canonical assets;
    re-pinning without adding the enum member left the float and object
    scenarios mandatory, and this check is what said so rather than two
    adoptions failing them.

    Monkeypatched rather than measured against the real assets, for the same
    reason the expired-reservation test is: the state being checked for is one
    the package must never actually be in, so it has to be simulated.
    """
    items = [_scenario_item(_a_canonical_feature())]

    # The real assets resolve, which is the state every run is in, and the
    # hook is then silent.
    plugin.pytest_collection_modifyitems(items)

    monkeypatch.setattr(
        plugin, "canonical_tags", lambda: frozenset({"@events", "@teleportation"})
    )

    with pytest.raises(pytest.UsageError) as raised:
        plugin.pytest_collection_modifyitems(items)

    message = str(raised.value)
    assert "@teleportation" in message
    assert "@events" not in message, "a tag that resolves is not reported"
    # The remedy is upstream of any run: nothing an adoption does substitutes.
    assert "Capability enum" in message
    assert "mandatory" in message, "why an unknown tag is worse than a known one"


def test_an_adopters_own_tags_are_not_the_capability_vocabulary(
    tmp_path: Path,
) -> None:
    """Which is the whole reason the unknown-tag check reads canonical tags only.

    An extension tags its scenarios for its own purposes -- to group them, to
    mark the slow ones -- and those tags gate nothing by design: see
    ``capability_for_marker``. Reading them as a capability vocabulary would
    turn every adopter with an extension into a failing run.

    The asymmetry with the reserved check, which *does* read an extension's
    tags, is not an inconsistency. "Is this one of my reserved names" is
    answerable about any tag; "is this a capability I do not know" is not.
    """
    items = [
        _scenario_item(_a_canonical_feature()),
        _scenario_item(
            str(tmp_path / "extensions" / "vendor.feature"),
            "@fractional",
            "@vendor-specific",
        ),
    ]

    plugin.pytest_collection_modifyitems(items)


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


# -- what this SDK cannot express --------------------------------------------
#
# INEXPRESSIBLE_CAPABILITIES is empty in Python, and that was measured: `int` is
# arbitrary-precision and `get_integer_details` and `get_float_details` are
# separate accessors reaching separate provider methods, so all four questions
# the two tagged groups ask can be put, and were. The machinery is here anyway,
# because the rule belongs to Appendix F rather than to this package and the next
# capability may hit it -- and a mechanism nothing exercises is indistinguishable
# from a mechanism that does not work. So these tests supply an entry rather than
# skipping for want of one, and the fabricated entry is Java's real case.


_AS_IN_JAVA = (
    "the integer accessor is a 32-bit Integer, so 2^53 - 1 cannot be asked for"
)


@pytest.fixture
def one_inexpressible(monkeypatch: pytest.MonkeyPatch) -> Capability:
    """Pretend, for one test, that this SDK cannot express ``@large-integers``.

    Patched on the module rather than injected, because the production code
    reads the mapping through the module global at call time and an injected
    copy would test a seam nothing else uses.
    """
    monkeypatch.setattr(
        capability_module,
        "INEXPRESSIBLE_CAPABILITIES",
        types.MappingProxyType({Capability.LARGE_INTEGERS: _AS_IN_JAVA}),
    )
    return Capability.LARGE_INTEGERS


def test_an_inexpressible_capability_is_one_whose_scenarios_exist() -> None:
    """The property that tells it from a reservation, read off the assets.

    A capability nothing carries is reserved, whatever any SDK could express
    about it -- so an entry here whose tag no canonical scenario carries is
    misfiled, and the two would then differ only in their wording. Every entry
    also has to say *which* property of the SDK puts the question out of reach,
    because that is the half of the message an adopter could not have worked out.

    Vacuous while the mapping is empty, and kept for the pass where it is not.
    """
    carried = canonical_tags()
    for capability, reason in INEXPRESSIBLE_CAPABILITIES.items():
        assert capability.tag in carried, (
            f"{capability.tag} is recorded as inexpressible but no canonical "
            f"scenario carries it, which makes it a reservation instead"
        )
        assert reason.strip(), (
            f"{capability.tag} does not say what puts it out of reach"
        )


def test_a_capability_this_sdk_cannot_express_cannot_be_declared(
    one_inexpressible: Capability,
) -> None:
    """Refused by the implementation, rather than left for adopters to remember.

    Which is the whole change: the fact is about the language, so an adopter
    should not have to know it, and three suites each remembering it separately
    is three chances to put an unverifiable claim in a report.
    """
    with pytest.raises(ValueError) as raised:
        _config(capabilities={Capability.EVENTS, one_inexpressible})

    message = str(raised.value)
    assert f"{one_inexpressible.tag} cannot be declared in this language" in message
    # The property of the SDK, not the rule. An adopter reaching this has done
    # nothing wrong and needs to be told something they could not have known.
    assert _AS_IN_JAVA in message
    assert "nothing for you to fix" in message


def test_the_two_refusals_do_not_read_the_same(one_inexpressible: Capability) -> None:
    """A reader has to be able to tell a reservation from an impossibility.

    Reserved: global, temporary, expires when the specification writes a
    scenario. Inexpressible: one language's, permanent, and the scenarios
    already exist and pass elsewhere. Both end in a refusal and nothing else
    about them is the same, so neither message may be reachable from the other's
    predicate.
    """
    reserved = next(iter(sorted(RESERVED_CAPABILITIES, key=lambda c: c.tag)))

    with pytest.raises(ValueError) as raised:
        _config(capabilities={reserved})
    reserved_message = str(raised.value)

    with pytest.raises(ValueError) as raised:
        _config(capabilities={one_inexpressible})
    inexpressible_message = str(raised.value)

    assert "no scenario carries them" in reserved_message
    assert "no scenario carries" not in inexpressible_message, (
        "its scenarios do exist -- that is what makes it not a reservation"
    )
    assert "is not a reservation" in inexpressible_message
    assert _AS_IN_JAVA not in reserved_message

    # And they are produced by separate predicates, so neither can start
    # answering for the other.
    assert config_module.reserved_problems([one_inexpressible]) == []
    assert config_module.inexpressible_problems([reserved]) == []


def test_a_deviation_may_not_name_a_capability_this_sdk_cannot_express(
    one_inexpressible: Capability,
) -> None:
    """A deviation is about this provider; this gap belongs to the language.

    Refused for the opposite reason a reserved one is. There the scenarios do
    not exist, so there is nothing to deviate from; here they exist and no
    provider in this SDK can attempt them, so the entry would attribute to one
    provider something none of them could have done.
    """
    with pytest.raises(ValueError) as raised:
        _config(
            known_deviations=[
                KnownDeviation.untracked(summary="a gap", capability=one_inexpressible)
            ]
        )

    message = str(raised.value)
    assert f"names {one_inexpressible.tag}, which cannot be expressed" in message
    assert _AS_IN_JAVA in message
    assert "belongs to the language" in message


def test_the_skip_reason_says_no_provider_here_could_have_been_asked(
    one_inexpressible: Capability,
) -> None:
    """The second half, and the one a report's reader actually sees.

    Refusing the declaration is not enough on its own: the scenarios are skipped
    either way, and a skip reading "provider does not declare capability
    @large-integers" describes a decision no provider in this language had the
    chance to make.
    """
    reason = plugin.inexpressible_skip_reason([one_inexpressible])
    assert reason is not None
    assert _AS_IN_JAVA in reason
    assert "no provider in this language can be asked" in reason
    assert "Nothing about the provider under test follows" in reason

    declined = plugin.undeclared_skip_reason(
        [Capability.EVENTS], _config(capabilities=frozenset())
    )
    assert declined is not None
    assert "provider does not declare capability @events" in declined
    assert declined != reason


def test_the_gate_prefers_the_language_reason_over_the_declaration_one(
    one_inexpressible: Capability,
) -> None:
    """A scenario gated by both kinds reports the permanent one.

    ``@large-integers`` and ``@events`` on one scenario, neither declared: the
    marker iterator decides which comes first, and the message must not. The
    language-wide reason is the true one -- the provider's declaration could not
    have made this scenario run.
    """
    node = types.SimpleNamespace(
        iter_markers=lambda: iter(
            [
                types.SimpleNamespace(name=Capability.EVENTS.value),
                types.SimpleNamespace(name=one_inexpressible.value),
            ]
        )
    )
    request = types.SimpleNamespace(
        node=node,
        getfixturevalue=lambda name: _config(capabilities=frozenset()),
    )

    with pytest.raises(pytest.skip.Exception) as raised:
        plugin.capability_gate(typing.cast("pytest.FixtureRequest", request))

    assert _AS_IN_JAVA in str(raised.value)


def test_the_gate_still_skips_for_a_declaration_nobody_made() -> None:
    """The unchanged half, checked here because the branch above is new.

    Nothing is patched: ``@events`` is expressible and undeclared, which is the
    ordinary case and the one that must keep its own wording.
    """
    node = types.SimpleNamespace(
        iter_markers=lambda: iter([types.SimpleNamespace(name=Capability.EVENTS.value)])
    )
    request = types.SimpleNamespace(
        node=node,
        getfixturevalue=lambda name: _config(capabilities={Capability.OBJECT}),
    )

    with pytest.raises(pytest.skip.Exception) as raised:
        plugin.capability_gate(typing.cast("pytest.FixtureRequest", request))

    message = str(raised.value)
    assert "provider does not declare capability @events" in message
    assert "Declared: @object" in message


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

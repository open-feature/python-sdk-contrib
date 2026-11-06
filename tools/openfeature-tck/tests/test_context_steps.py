"""What a context table does to the evaluation context, and what its types mean.

No canonical scenario uses the table form -- the shipped feature files target
``targeting-key-flag``, whose rule keys on the one entry a single step can set --
so it first runs in an adopter's extension, where a defect reads like a provider
that ignores context. It is driven directly here instead.

The rebuild is the part worth pinning. ``EvaluationContext.attributes`` is typed
as a mapping, so the step builds a new context rather than adding to one, and
rebuilding is where an earlier statement can be lost or a later one ignored.
"""

from __future__ import annotations

import pytest

from openfeature.contrib.tools.tck import (
    BackendType,
    Capability,
    ControllableInMemoryProvider,
    TckConfig,
    TckState,
    canonical_flag_set,
)
from openfeature.contrib.tools.tck.steps.flag_steps import (
    a_context_containing_a_targeting_key,
    a_context_with_the_following_keys,
)
from openfeature.contrib.tools.tck.values import parse_table_value

_HEADER = ["key", "type", "value"]


class _NoControl:
    """A control that brings nothing up; no step here reaches the backend."""

    @property
    def description(self) -> str:
        return "nothing"

    @property
    def backend_type(self) -> BackendType:
        return "in-process"

    def prepare_scenario(self) -> None: ...

    def change_flag(self) -> None: ...


@pytest.fixture
def state() -> TckState:
    config = TckConfig(
        name="context-steps",
        control=_NoControl(),
        new_provider=lambda: ControllableInMemoryProvider(canonical_flag_set()),
        capabilities={Capability.EVENTS},
    )
    return TckState(config=config)


def _table(*rows: list[str]) -> list[list[str]]:
    return [_HEADER, *rows]


# -- the rebuild --------------------------------------------------------------


def test_a_targeting_key_set_earlier_survives_a_table_that_omits_it(
    state: TckState,
) -> None:
    """The table said nothing about it, so it is still the targeting key."""
    a_context_containing_a_targeting_key(state, "tim")

    a_context_with_the_following_keys(state, _table(["region", "String", "eu"]))

    assert state.evaluation_context is not None
    assert state.evaluation_context.targeting_key == "tim"
    assert state.evaluation_context.attributes["region"] == "eu"


def test_a_table_row_may_set_the_targeting_key(state: TckState) -> None:
    """A row is the later statement about it, so it is the one that holds.

    And it lands on ``targeting_key`` rather than in the attributes: a provider
    reads the field, so an attribute of that name would be a context the
    targeting rule never sees.
    """
    a_context_containing_a_targeting_key(state, "tim")

    a_context_with_the_following_keys(state, _table(["targetingKey", "String", "ada"]))

    assert state.evaluation_context is not None
    assert state.evaluation_context.targeting_key == "ada"
    assert "targetingKey" not in state.evaluation_context.attributes


def test_entries_from_two_tables_add_up(state: TckState) -> None:
    a_context_with_the_following_keys(state, _table(["region", "String", "eu"]))
    a_context_with_the_following_keys(state, _table(["tier", "String", "gold"]))

    assert state.evaluation_context is not None
    assert state.evaluation_context.attributes == {"region": "eu", "tier": "gold"}


def test_a_rows_type_decides_what_the_context_carries(state: TckState) -> None:
    a_context_with_the_following_keys(
        state,
        _table(
            ["region", "String", "eu"],
            ["editions", "StringList", "one, two"],
            ["seats", "Integer", "3"],
            ["fresh", "Boolean", "true"],
        ),
    )

    assert state.evaluation_context is not None
    attributes = state.evaluation_context.attributes
    assert attributes["region"] == "eu"
    assert attributes["editions"] == ["one", "two"], (
        "a StringList is a list, not one comma-joined string"
    )
    assert attributes["seats"] == 3
    assert attributes["fresh"] is True


def test_the_columns_the_step_reads_are_the_columns_it_demands(
    state: TckState,
) -> None:
    """A mistyped header is a feature-file mistake, and silently reading the
    rows positionally would attribute it to the provider."""
    with pytest.raises(AssertionError, match="columns key, type, value"):
        a_context_with_the_following_keys(
            state, [["key", "metadata_type", "value"], ["region", "String", "eu"]]
        )


def test_a_context_step_does_not_leave_the_context_unset(state: TckState) -> None:
    """An unset context is passed to the SDK as ``None``, which is load-bearing
    for the scenario about a rule that cannot match. A table is a statement that
    there is a context, so it must stop being ``None``."""
    assert state.evaluation_context is None

    a_context_with_the_following_keys(state, _table(["region", "String", "eu"]))

    assert state.evaluation_context is not None


# -- the table's type vocabulary ---------------------------------------------


@pytest.mark.parametrize(
    ("type_name", "raw", "expected"),
    [
        ("Boolean", "true", True),
        ("String", "eu", "eu"),
        ("Integer", "3", 3),
        ("Long", "3", 3),
        ("Float", "0.1", 0.1),
        ("StringList", "one, two", ["one", "two"]),
        ("StringList", "", []),
        ("Object", '{"a": 1}', {"a": 1}),
    ],
)
def test_the_table_vocabulary_converts_by_the_name_a_row_wrote(
    type_name: str, raw: str, expected: object
) -> None:
    assert parse_table_value(type_name, raw) == expected


def test_long_and_integer_agree_on_a_value_no_32_bit_integer_holds() -> None:
    """Java and Go need two converters here; Python needs one.

    There an ``Integer`` wider than 32 bits is refused for a flag default and
    widened for a context entry, because the accessor that reads a default back
    is bounded and nothing reads a context entry back. Python's ``int`` is
    arbitrary-precision, so there is no width to refuse and nothing to widen --
    but ``Long`` has to stay in the vocabulary, or a feature file written against
    one of those bindings stops running here.
    """
    wide = str(2**40)

    assert parse_table_value("Integer", wide) == 2**40
    assert parse_table_value("Long", wide) == parse_table_value("Integer", wide)


def test_a_type_no_table_can_declare_is_refused() -> None:
    """Named so the message says what to write instead; a row silently read as a
    string would compare a value no provider ever sent."""
    with pytest.raises(ValueError, match="unknown value type 'Duration'"):
        parse_table_value("Duration", "5s")

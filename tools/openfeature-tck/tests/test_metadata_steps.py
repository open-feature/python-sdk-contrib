"""The flag-metadata assertions, whose wording and columns are the specification's own.

They come from ``assets/gherkin/metadata.feature``, which the provider suite does
not ship -- it needs a ``metadata-flag`` the canonical flag set does not carry --
so nothing here runs them from Gherkin. They are driven directly instead, each
case written so the opposite implementation would fail it: a value that matches
and one that does not, metadata that is empty and metadata that is not.
"""

from __future__ import annotations

import typing

import pytest

from openfeature.client import OpenFeatureClient
from openfeature.contrib.tools.tck import (
    BackendType,
    Capability,
    ControllableInMemoryProvider,
    TckConfig,
    TckState,
    canonical_flag_set,
)
from openfeature.contrib.tools.tck.state import EvaluationRecord
from openfeature.contrib.tools.tck.steps.flag_steps import (
    a_flag_with_key_and_default,
    the_flag_was_evaluated_with_details,
    the_resolved_metadata_is_empty,
    the_resolved_metadata_should_contain,
)
from openfeature.flag_evaluation import FlagEvaluationDetails, FlagMetadata

_HEADER = ["key", "metadata_type", "value"]


class _NoControl:
    @property
    def description(self) -> str:
        return "nothing"

    @property
    def backend_type(self) -> BackendType:
        return "in-process"

    def prepare_scenario(self) -> None: ...

    def change_flag(self) -> None: ...


def _state(metadata: FlagMetadata | None = None) -> TckState:
    """A scenario that has evaluated a flag, carrying the metadata given."""
    config = TckConfig(
        name="metadata-steps",
        control=_NoControl(),
        new_provider=lambda: ControllableInMemoryProvider(canonical_flag_set()),
        capabilities={Capability.EVENTS},
    )
    state = TckState(config=config)
    state.flag_key = "metadata-flag"
    state.last = EvaluationRecord(value=True, flag_metadata=metadata)
    return state


def _table(*rows: list[str]) -> list[list[str]]:
    return [_HEADER, *rows]


def test_every_type_the_specifications_table_uses_is_compared_by_that_type() -> None:
    """The exact table from ``metadata.feature``'s "Returns metadata" scenario."""
    state = _state(
        {"string": "1.0.2", "integer": 2, "float": 0.1, "boolean": True},
    )

    the_resolved_metadata_should_contain(
        state,
        _table(
            ["string", "String", "1.0.2"],
            ["integer", "Integer", "2"],
            ["float", "Float", "0.1"],
            ["boolean", "Boolean", "true"],
        ),
    )


def test_a_value_that_differs_fails_naming_the_key_and_what_arrived() -> None:
    state = _state({"integer": 2})

    with pytest.raises(AssertionError, match=r"metadata entry 'integer' \(Integer\)"):
        the_resolved_metadata_should_contain(state, _table(["integer", "Integer", "3"]))


def test_an_entry_the_table_does_not_list_is_not_checked() -> None:
    """A provider is free to carry more than a scenario is interested in."""
    state = _state({"listed": "yes", "unlisted": "whatever"})

    the_resolved_metadata_should_contain(state, _table(["listed", "String", "yes"]))


def test_an_entry_the_provider_did_not_send_fails_rather_than_being_skipped() -> None:
    state = _state({"other": "yes"})

    with pytest.raises(AssertionError, match="no entry 'listed'"):
        the_resolved_metadata_should_contain(state, _table(["listed", "String", "yes"]))


def test_a_stringified_value_does_not_satisfy_an_integer_row() -> None:
    """A provider that stringified its metadata sends ``"2"`` where the table says
    ``Integer``, and the application reading it back as a number gets nothing."""
    state = _state({"integer": "2"})

    with pytest.raises(AssertionError, match="metadata entry 'integer'"):
        the_resolved_metadata_should_contain(state, _table(["integer", "Integer", "2"]))


@pytest.mark.parametrize(
    ("sent", "row"),
    [(2.0, ["integer", "Integer", "2"]), (2, ["float", "Float", "2"])],
    ids=["float-for-integer", "integer-for-float"],
)
def test_a_number_of_the_other_kind_fails_although_it_compares_equal(
    sent: int | float, row: list[str]
) -> None:
    """The case only the declared type catches, and the reason the column exists.

    Numbers are compared numerically everywhere else in this suite, deliberately:
    a provider that deserialises its backend's JSON hands back ``float`` for every
    number, and a structured member arriving as ``100.0`` rather than ``100`` is
    not a defect. Metadata is where the distinction is the question -- the table
    says which primitive the entry is, and Java's typed accessors answer nothing
    at all for the other one -- so here the type is checked as well as the value.
    """
    state = _state({row[0]: sent})

    with pytest.raises(AssertionError, match=f"metadata entry '{row[0]}'"):
        the_resolved_metadata_should_contain(state, _table(row))


def test_a_boolean_does_not_satisfy_an_integer_row() -> None:
    """Python makes ``bool`` a subclass of ``int``, so this needs saying."""
    state = _state({"flagged": True})

    with pytest.raises(AssertionError, match="metadata entry 'flagged'"):
        the_resolved_metadata_should_contain(state, _table(["flagged", "Integer", "1"]))


def test_a_metadata_type_flag_metadata_cannot_carry_is_refused() -> None:
    """Not silently compared: a structured value cannot travel in metadata, so a
    table asking for one is asking the wrong question."""
    state = _state({"a": "b"})

    with pytest.raises(ValueError, match="flag metadata is String, Boolean"):
        the_resolved_metadata_should_contain(state, _table(["a", "Object", "{}"]))


def test_the_columns_the_step_reads_are_the_columns_it_demands() -> None:
    state = _state({"a": "b"})

    with pytest.raises(AssertionError, match="columns key, metadata_type, value"):
        the_resolved_metadata_should_contain(
            state, [["key", "type", "value"], ["a", "String", "b"]]
        )


# -- the empty assertion ------------------------------------------------------


def test_empty_metadata_satisfies_the_empty_assertion() -> None:
    the_resolved_metadata_is_empty(_state({}))


def test_anything_at_all_fails_the_empty_assertion() -> None:
    """The half that catches a provider inventing entries, which the positive
    assertion cannot: an unlisted entry is deliberately not checked there."""
    with pytest.raises(AssertionError, match="expected none"):
        the_resolved_metadata_is_empty(_state({"a": "b"}))


def test_metadata_absent_altogether_is_not_read_as_empty() -> None:
    """The specification types the field as a map. A provider answering with
    nothing at all is a different finding from one answering with no entries."""
    with pytest.raises(AssertionError, match="no flag metadata at all"):
        the_resolved_metadata_is_empty(_state(None))


def test_asserting_metadata_before_any_evaluation_says_which_step_is_missing() -> None:
    state = _state({})
    state.last = None

    with pytest.raises(AssertionError, match="the flag was evaluated with details"):
        the_resolved_metadata_is_empty(state)


class _ClientWithMetadata:
    """A client whose every typed getter answers with metadata attached.

    A real registration would add a provider and a domain to a test about one
    assignment. What is being checked is that the evaluation step copies the
    details' metadata into its record, which is true of whatever details it is
    handed. All five getters, because the step builds its dispatch table from
    every one of them before it calls the one it wants.
    """

    def _details(self, key: str) -> FlagEvaluationDetails[typing.Any]:
        return FlagEvaluationDetails(
            flag_key=key, value=True, flag_metadata={"scope": "seeded"}
        )

    def get_boolean_details(
        self, key: str, default: typing.Any, context: typing.Any = None
    ) -> FlagEvaluationDetails[typing.Any]:
        return self._details(key)

    get_string_details = get_boolean_details
    get_integer_details = get_boolean_details
    get_float_details = get_boolean_details
    get_object_details = get_boolean_details


def test_the_metadata_of_an_evaluation_reaches_the_step() -> None:
    """The capture, not the assertion.

    The assertions read what the evaluation step recorded, so details whose
    metadata was never copied across would make every metadata scenario pass as
    empty -- the one way this pair could go quietly green.
    """
    state = _state({})
    state.last = None
    state.client = typing.cast("OpenFeatureClient", _ClientWithMetadata())

    a_flag_with_key_and_default(state, "Boolean", "boolean-flag", "false")
    the_flag_was_evaluated_with_details(state)

    the_resolved_metadata_should_contain(state, _table(["scope", "String", "seeded"]))

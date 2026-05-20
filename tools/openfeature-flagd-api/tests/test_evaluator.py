from collections.abc import Mapping, Sequence

from openfeature.contrib.tools.flagd.api import Evaluator, FlagStoreError
from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType


class MockEvaluator:
    """A mock implementation of the Evaluator protocol for testing."""

    def set_flags(self, flag_configuration_json: str) -> None:
        pass

    def set_flags_and_get_changed_keys(self, flag_configuration_json: str) -> list[str]:
        return []

    def get_flag_set_metadata(self) -> Mapping[str, float | int | str | bool]:
        return {}

    def resolve_boolean_value(
        self, flag_key: str, default_value: bool, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[bool]:
        return FlagResolutionDetails(value=default_value)

    def resolve_string_value(
        self, flag_key: str, default_value: str, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[str]:
        return FlagResolutionDetails(value=default_value)

    def resolve_integer_value(
        self, flag_key: str, default_value: int, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[int]:
        return FlagResolutionDetails(value=default_value)

    def resolve_float_value(
        self, flag_key: str, default_value: float, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[float]:
        return FlagResolutionDetails(value=default_value)

    def resolve_object_value(
        self,
        flag_key: str,
        default_value: Sequence[FlagValueType] | Mapping[str, FlagValueType],
        ctx: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[Sequence[FlagValueType] | Mapping[str, FlagValueType]]:
        return FlagResolutionDetails(value=default_value)


def test_mock_evaluator_implements_protocol() -> None:
    """Verify that MockEvaluator satisfies the Evaluator protocol."""
    evaluator: Evaluator = MockEvaluator()
    assert evaluator is not None


def test_mock_evaluator_set_flags() -> None:
    evaluator = MockEvaluator()
    evaluator.set_flags('{"flags": {}}')


def test_mock_evaluator_set_flags_and_get_changed_keys() -> None:
    evaluator = MockEvaluator()
    result = evaluator.set_flags_and_get_changed_keys('{"flags": {}}')
    assert result == []


def test_mock_evaluator_get_flag_set_metadata() -> None:
    evaluator = MockEvaluator()
    result = evaluator.get_flag_set_metadata()
    assert result == {}


def test_mock_evaluator_resolve_boolean_value() -> None:
    evaluator = MockEvaluator()
    result = evaluator.resolve_boolean_value("flag1", True)
    assert result.value is True


def test_mock_evaluator_resolve_string_value() -> None:
    evaluator = MockEvaluator()
    result = evaluator.resolve_string_value("flag1", "default")
    assert result.value == "default"


def test_mock_evaluator_resolve_integer_value() -> None:
    evaluator = MockEvaluator()
    result = evaluator.resolve_integer_value("flag1", 42)
    assert result.value == 42


def test_mock_evaluator_resolve_float_value() -> None:
    evaluator = MockEvaluator()
    result = evaluator.resolve_float_value("flag1", 3.14)
    assert result.value == 3.14


def test_mock_evaluator_resolve_object_value() -> None:
    evaluator = MockEvaluator()
    result = evaluator.resolve_object_value("flag1", {"key": "value"})
    assert result.value == {"key": "value"}


def test_flag_store_error() -> None:
    """Verify FlagStoreError can be raised and caught."""
    with_message = FlagStoreError("something went wrong")
    assert str(with_message) == "something went wrong"
    assert isinstance(with_message, Exception)

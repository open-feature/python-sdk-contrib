import typing

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType

from openfeature.contrib.tools.flagd.api import Evaluator, FlagStoreException


class MockEvaluator:
    """A mock implementation of the Evaluator protocol for testing."""

    def set_flags(self, flag_configuration_json: str) -> None:
        pass

    def set_flags_and_get_changed_keys(self, flag_configuration_json: str) -> typing.List[str]:
        return []

    def get_flag_set_metadata(self) -> typing.Mapping[str, typing.Union[float, int, str, bool]]:
        return {}

    def resolve_boolean_value(
        self, flag_key: str, default_value: bool, ctx: typing.Optional[EvaluationContext] = None
    ) -> FlagResolutionDetails[bool]:
        return FlagResolutionDetails(value=default_value)

    def resolve_string_value(
        self, flag_key: str, default_value: str, ctx: typing.Optional[EvaluationContext] = None
    ) -> FlagResolutionDetails[str]:
        return FlagResolutionDetails(value=default_value)

    def resolve_integer_value(
        self, flag_key: str, default_value: int, ctx: typing.Optional[EvaluationContext] = None
    ) -> FlagResolutionDetails[int]:
        return FlagResolutionDetails(value=default_value)

    def resolve_float_value(
        self, flag_key: str, default_value: float, ctx: typing.Optional[EvaluationContext] = None
    ) -> FlagResolutionDetails[float]:
        return FlagResolutionDetails(value=default_value)

    def resolve_object_value(
        self,
        flag_key: str,
        default_value: typing.Union[typing.Sequence[FlagValueType], typing.Mapping[str, FlagValueType]],
        ctx: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[typing.Union[typing.Sequence[FlagValueType], typing.Mapping[str, FlagValueType]]]:
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


def test_flag_store_exception() -> None:
    """Verify FlagStoreException can be raised and caught."""
    with_message = FlagStoreException("something went wrong")
    assert str(with_message) == "something went wrong"
    assert isinstance(with_message, Exception)

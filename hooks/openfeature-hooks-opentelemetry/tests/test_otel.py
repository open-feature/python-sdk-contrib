from unittest.mock import Mock

import pytest
from opentelemetry import trace
from opentelemetry.trace import Span

from openfeature.contrib.hook.opentelemetry import TracingHook
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import FlagEvaluationDetails, FlagType, Reason
from openfeature.hook import HookContext
from openfeature.provider.metadata import Metadata


@pytest.fixture
def mock_get_current_span(monkeypatch):
    monkeypatch.setattr(trace, "get_current_span", Mock())


def test_finally_after(mock_get_current_span):
    # Given
    hook = TracingHook()
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext("123"),
        provider_metadata=Metadata(name="test-provider"),
    )
    details = FlagEvaluationDetails(
        flag_key="flag_key",
        value=True,
        variant="enabled",
        reason=Reason.TARGETING_MATCH,
        error_code=None,
        error_message=None,
    )

    mock_span = Mock(spec=Span)
    trace.get_current_span.return_value = mock_span

    # When
    hook.finally_after(hook_context, details, hints={})

    # Then
    mock_span.add_event.assert_called_once_with(
        "feature_flag.evaluation",
        {
            "feature_flag.key": "flag_key",
            "feature_flag.result.value": "true",
            "feature_flag.result.variant": "enabled",
            "feature_flag.result.reason": "targeting_match",
            "feature_flag.context.id": "123",
            "feature_flag.provider.name": "test-provider",
        },
    )


def test_after_evaluation_error(mock_get_current_span):
    # Given
    hook = TracingHook()
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext(),
        provider_metadata=None,
    )
    details = FlagEvaluationDetails(
        flag_key="flag_key",
        value=False,
        variant=None,
        reason=Reason.ERROR,
        error_code=ErrorCode.FLAG_NOT_FOUND,
        error_message="Flag not found: flag_key",
    )

    mock_span = Mock(spec=Span)
    trace.get_current_span.return_value = mock_span

    # When
    hook.finally_after(hook_context, details, hints={})

    # Then
    mock_span.add_event.assert_called_once_with(
        "feature_flag.evaluation",
        {
            "feature_flag.key": "flag_key",
            "feature_flag.result.value": "false",
            "feature_flag.result.reason": "error",
            "error.type": "flag_not_found",
            "error.message": "Flag not found: flag_key",
        },
    )


def test_error(mock_get_current_span):
    # Given
    hook = TracingHook()
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext(),
        provider_metadata=Metadata(name="test-provider"),
    )
    exception = Exception()
    attributes = {
        "feature_flag.key": "flag_key",
        "feature_flag.result.value": "false",
        "feature_flag.provider.name": "test-provider",
    }

    mock_span = Mock(spec=Span)
    trace.get_current_span.return_value = mock_span

    # When
    hook.error(hook_context, exception, hints={})

    # Then
    mock_span.record_exception.assert_called_once_with(exception, attributes)


def test_error_exclude_exceptions(mock_get_current_span):
    # Given
    hook = TracingHook(exclude_exceptions=True)
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext(),
    )
    exception = Exception()

    mock_span = Mock(spec=Span)
    trace.get_current_span.return_value = mock_span

    # When
    hook.error(hook_context, exception, hints={})
    # Then
    mock_span.record_exception.assert_not_called()


def test_error_no_provider_metadata(mock_get_current_span):
    # Given
    hook = TracingHook()
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext(),
    )
    exception = Exception()
    attributes = {
        "feature_flag.key": "flag_key",
        "feature_flag.result.value": "false",
    }

    mock_span = Mock(spec=Span)
    trace.get_current_span.return_value = mock_span

    # When
    hook.error(hook_context, exception, hints={})
    # Then
    mock_span.record_exception.assert_called_once_with(exception, attributes)

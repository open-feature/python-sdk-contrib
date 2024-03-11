from unittest.mock import Mock

import pytest
from opentelemetry import trace
from opentelemetry.trace import Span

from openfeature.contrib.hook.opentelemetry import TracingHook
from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagEvaluationDetails, FlagType
from openfeature.hook import HookContext


@pytest.fixture
def mock_get_current_span(monkeypatch):
    monkeypatch.setattr(trace, "get_current_span", Mock())


def test_before(mock_get_current_span):
    # Given
    hook = TracingHook()
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext(),
    )
    details = FlagEvaluationDetails(
        flag_key="flag_key",
        value=True,
        variant="enabled",
        reason=None,
        error_code=None,
        error_message=None,
    )

    mock_span = Mock(spec=Span)
    trace.get_current_span.return_value = mock_span

    # When
    hook.after(hook_context, details, hints={})

    # Then
    mock_span.add_event.assert_called_once_with(
        "feature_flag",
        {
            "feature_flag.key": "flag_key",
            "feature_flag.variant": "enabled",
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
    )
    exception = Exception()

    mock_span = Mock(spec=Span)
    trace.get_current_span.return_value = mock_span

    # When
    hook.error(hook_context, exception, hints={})

    # Then
    mock_span.record_exception.assert_called_once_with(exception)

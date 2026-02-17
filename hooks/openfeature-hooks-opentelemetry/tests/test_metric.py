from unittest.mock import Mock

import pytest
from opentelemetry import metrics

from openfeature.contrib.hook.opentelemetry import MetricsHook
from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import Reason
from openfeature.hook import FlagEvaluationDetails, FlagType, HookContext
from openfeature.provider.metadata import Metadata


@pytest.fixture
def mock_get_meter(monkeypatch):
    mock_counters = {
        "feature_flag.evaluation.active_total": Mock(spec=metrics.UpDownCounter),
        "feature_flag.evaluation.error_total": Mock(spec=metrics.Counter),
        "feature_flag.evaluation.success_total": Mock(spec=metrics.Counter),
        "feature_flag.evaluation.request_total": Mock(spec=metrics.Counter),
    }

    def side_effect(*args, **kwargs):
        return mock_counters[args[0]]

    mock_meter = Mock(
        spec=metrics.Meter,
        create_up_down_counter=side_effect,
        create_counter=side_effect,
    )
    monkeypatch.setattr(metrics, "get_meter", lambda name: mock_meter)

    return mock_meter, mock_counters


def test_metric_before(mock_get_meter):
    _, mock_counters = mock_get_meter
    hook = MetricsHook()
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext(),
        provider_metadata=Metadata(name="test-provider"),
    )

    hook.before(hook_context, hints={})
    mock_counters["feature_flag.evaluation.active_total"].add.assert_called_once_with(
        1,
        {
            "feature_flag.key": "flag_key",
            "feature_flag.provider.name": "test-provider",
        },
    )
    mock_counters["feature_flag.evaluation.request_total"].add.assert_called_once_with(
        1,
        {
            "feature_flag.key": "flag_key",
            "feature_flag.provider.name": "test-provider",
        },
    )
    mock_counters["feature_flag.evaluation.error_total"].add.assert_not_called()
    mock_counters["feature_flag.evaluation.success_total"].add.assert_not_called()


def test_metric_after(mock_get_meter):
    _, mock_counters = mock_get_meter
    hook = MetricsHook()
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext(),
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
    hook.after(hook_context, details, hints={})
    mock_counters["feature_flag.evaluation.success_total"].add.assert_called_once_with(
        1,
        {
            "feature_flag.key": "flag_key",
            "feature_flag.result.variant": "enabled",
            "feature_flag.provider.name": "test-provider",
        },
    )
    mock_counters["feature_flag.evaluation.error_total"].add.assert_not_called()
    mock_counters["feature_flag.evaluation.request_total"].add.assert_not_called()
    mock_counters["feature_flag.evaluation.active_total"].add.assert_not_called()


def test_metric_error(mock_get_meter):
    _, mock_counters = mock_get_meter
    hook = MetricsHook()
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext(),
        provider_metadata=Metadata(name="test-provider"),
    )
    hook.error(hook_context, Exception("test error"), hints={})
    mock_counters["feature_flag.evaluation.error_total"].add.assert_called_once_with(
        1,
        {
            "feature_flag.key": "flag_key",
            "feature_flag.provider.name": "test-provider",
            "exception": "test error",
        },
    )
    mock_counters["feature_flag.evaluation.success_total"].add.assert_not_called()
    mock_counters["feature_flag.evaluation.request_total"].add.assert_not_called()
    mock_counters["feature_flag.evaluation.active_total"].add.assert_not_called()


def test_metric_finally_after(mock_get_meter):
    _, mock_counters = mock_get_meter
    hook = MetricsHook()
    hook_context = HookContext(
        flag_key="flag_key",
        flag_type=FlagType.BOOLEAN,
        default_value=False,
        evaluation_context=EvaluationContext(),
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
    hook.finally_after(hook_context, details, hints={})
    mock_counters["feature_flag.evaluation.active_total"].add.assert_called_once_with(
        -1,
        {
            "feature_flag.key": "flag_key",
            "feature_flag.provider.name": "test-provider",
        },
    )
    mock_counters["feature_flag.evaluation.success_total"].add.assert_not_called()
    mock_counters["feature_flag.evaluation.request_total"].add.assert_not_called()
    mock_counters["feature_flag.evaluation.error_total"].add.assert_not_called()

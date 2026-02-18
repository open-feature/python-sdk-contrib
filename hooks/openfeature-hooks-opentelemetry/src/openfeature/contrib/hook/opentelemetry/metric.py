from openfeature.flag_evaluation import FlagEvaluationDetails, Reason
from openfeature.hook import Hook, HookContext, HookHints
from opentelemetry import metrics

from .constants import Attributes, Metrics


class MetricsHook(Hook):
    def __init__(self) -> None:
        meter: metrics.Meter = metrics.get_meter("openfeature.hooks.opentelemetry")
        self.evaluation_active_total = meter.create_up_down_counter(
            Metrics.ACTIVE_TOTAL, "active flag evaluations"
        )
        self.evaluation_error_total = meter.create_counter(
            Metrics.ERROR_TOTAL, "error flag evaluations"
        )
        self.evaluation_success_total = meter.create_counter(
            Metrics.SUCCESS_TOTAL, "success flag evaluations"
        )
        self.evaluation_request_total = meter.create_counter(
            Metrics.REQUEST_TOTAL, "request flag evaluations"
        )

    def before(self, hook_context: HookContext, hints: HookHints) -> None:
        attributes = {
            Attributes.OTEL_FLAG_KEY: hook_context.flag_key,
        }
        if hook_context.provider_metadata:
            attributes[Attributes.OTEL_PROVIDER_NAME] = (
                hook_context.provider_metadata.name
            )
        self.evaluation_active_total.add(1, attributes)
        self.evaluation_request_total.add(1, attributes)

    def after(
        self,
        hook_context: HookContext,
        details: FlagEvaluationDetails,
        hints: HookHints,
    ) -> None:
        attributes = {
            Attributes.OTEL_FLAG_KEY: details.flag_key,
            Attributes.OTEL_RESULT_REASON: str(
                details.reason or Reason.UNKNOWN
            ).lower(),
        }
        if details.variant:
            attributes[Attributes.OTEL_FLAG_VARIANT] = details.variant
        if hook_context.provider_metadata:
            attributes[Attributes.OTEL_PROVIDER_NAME] = (
                hook_context.provider_metadata.name
            )
        self.evaluation_success_total.add(1, attributes)

    def error(
        self, hook_context: HookContext, exception: Exception, hints: HookHints
    ) -> None:
        attributes = {
            Attributes.OTEL_FLAG_KEY: hook_context.flag_key,
            "exception": str(exception).lower(),
        }
        if hook_context.provider_metadata:
            attributes[Attributes.OTEL_PROVIDER_NAME] = (
                hook_context.provider_metadata.name
            )
        self.evaluation_error_total.add(1, attributes)

    def finally_after(
        self,
        hook_context: HookContext,
        details: FlagEvaluationDetails,
        hints: HookHints,
    ) -> None:
        attributes = {
            Attributes.OTEL_FLAG_KEY: hook_context.flag_key,
        }
        if hook_context.provider_metadata:
            attributes[Attributes.OTEL_PROVIDER_NAME] = (
                hook_context.provider_metadata.name
            )
        self.evaluation_active_total.add(-1, attributes)

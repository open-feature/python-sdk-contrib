import typing

from openfeature.flag_evaluation import FlagEvaluationDetails, FlagMetadata, Reason
from openfeature.hook import Hook, HookContext, HookHints
from opentelemetry import metrics
from opentelemetry.util.types import AttributeValue

from .constants import Attributes, Metrics


class MetricsHook(Hook):
    def __init__(self, extra_attributes: typing.Optional[list[str]] = None) -> None:
        self.extra_attributes = extra_attributes or []
        meter: metrics.Meter = metrics.get_meter("openfeature.hooks.opentelemetry")
        self.evaluation_active_count = meter.create_up_down_counter(
            Metrics.ACTIVE_COUNT, "active flag evaluations"
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
        attributes: dict[str, AttributeValue] = {
            Attributes.OTEL_FLAG_KEY: hook_context.flag_key,
        }
        if hook_context.provider_metadata:
            attributes[Attributes.OTEL_PROVIDER_NAME] = (
                hook_context.provider_metadata.name
            )
        self.evaluation_active_count.add(1, attributes)
        self.evaluation_request_total.add(1, attributes)

    def after(
        self,
        hook_context: HookContext,
        details: FlagEvaluationDetails,
        hints: HookHints,
    ) -> None:
        attributes: dict[str, AttributeValue] = {
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
        attributes = attributes | attributes_from_dimensions(
            self.extra_attributes, details.flag_metadata
        )
        self.evaluation_success_total.add(1, attributes)

    def error(
        self, hook_context: HookContext, exception: Exception, hints: HookHints
    ) -> None:
        attributes: dict[str, AttributeValue] = {
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
        attributes: dict[str, AttributeValue] = {
            Attributes.OTEL_FLAG_KEY: hook_context.flag_key,
        }
        if hook_context.provider_metadata:
            attributes[Attributes.OTEL_PROVIDER_NAME] = (
                hook_context.provider_metadata.name
            )
        self.evaluation_active_count.add(-1, attributes)


def attributes_from_dimensions(
    extra_attributes: list[str], metadata: FlagMetadata
) -> dict[str, AttributeValue]:
    attributes: dict[str, AttributeValue] = {}
    for attribute in extra_attributes:
        if (attr := metadata.get(attribute)) is not None:
            attributes[attribute] = attr
    return attributes

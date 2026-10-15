import json

from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import FlagEvaluationDetails, Reason
from openfeature.hook import Hook, HookContext, HookHints
from opentelemetry import trace

from .constants import Attributes


class TracingHook(Hook):
    def __init__(self, exclude_exceptions: bool = False):
        self.exclude_exceptions = exclude_exceptions

    def finally_after(
        self,
        hook_context: HookContext,
        details: FlagEvaluationDetails,
        hints: HookHints,
    ) -> None:
        current_span = trace.get_current_span()

        event_attributes = {
            Attributes.OTEL_FLAG_KEY: details.flag_key,
            Attributes.OTEL_RESULT_VALUE: json.dumps(details.value),
            Attributes.OTEL_RESULT_REASON: str(
                details.reason or Reason.UNKNOWN
            ).lower(),
        }

        if details.variant:
            event_attributes[Attributes.OTEL_FLAG_VARIANT] = details.variant

        if details.reason == Reason.ERROR:
            error_type = str(details.error_code or ErrorCode.GENERAL).lower()
            event_attributes[Attributes.OTEL_ERROR_TYPE] = error_type
            if details.error_message:
                event_attributes[Attributes.OTEL_ERROR_MESSAGE] = details.error_message

        context = hook_context.evaluation_context
        if context.targeting_key:
            event_attributes[Attributes.OTEL_CONTEXT_ID] = context.targeting_key

        if hook_context.provider_metadata:
            event_attributes[Attributes.OTEL_PROVIDER_NAME] = (
                hook_context.provider_metadata.name
            )

        current_span.add_event(Attributes.OTEL_EVENT_NAME, event_attributes)

    def error(
        self, hook_context: HookContext, exception: Exception, hints: HookHints
    ) -> None:
        if self.exclude_exceptions:
            return
        attributes = {
            Attributes.OTEL_FLAG_KEY: hook_context.flag_key,
            Attributes.OTEL_RESULT_VALUE: json.dumps(hook_context.default_value),
        }
        if hook_context.provider_metadata:
            attributes[Attributes.OTEL_PROVIDER_NAME] = (
                hook_context.provider_metadata.name
            )
        current_span = trace.get_current_span()
        current_span.record_exception(exception, attributes)

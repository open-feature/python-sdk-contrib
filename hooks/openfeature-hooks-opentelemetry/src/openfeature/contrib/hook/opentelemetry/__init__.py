import json

from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import FlagEvaluationDetails, Reason
from openfeature.hook import Hook, HookContext, HookHints
from opentelemetry import trace
from opentelemetry.semconv.attributes.error_attributes import ERROR_TYPE

OTEL_EVENT_NAME = "feature_flag.evaluation"


class EventAttributes:
    KEY = "feature_flag.key"
    RESULT_VALUE = "feature_flag.result.value"
    RESULT_VARIANT = "feature_flag.result.variant"
    CONTEXT_ID = "feature_flag.context.id"
    PROVIDER_NAME = "feature_flag.provider.name"
    RESULT_REASON = "feature_flag.result.reason"
    SET_ID = "feature_flag.set.id"
    VERSION = "feature_flag.version"


class TracingHook(Hook):
    def after(
        self,
        hook_context: HookContext,
        details: FlagEvaluationDetails,
        hints: HookHints,
    ) -> None:
        current_span = trace.get_current_span()

        event_attributes = {
            EventAttributes.KEY: details.flag_key,
            EventAttributes.RESULT_VALUE: json.dumps(details.value),
            EventAttributes.RESULT_REASON: str(
                details.reason or Reason.UNKNOWN
            ).lower(),
        }

        if details.variant:
            event_attributes[EventAttributes.RESULT_VARIANT] = details.variant

        if details.reason == Reason.ERROR:
            error_type = str(details.error_code or ErrorCode.GENERAL).lower()
            event_attributes[ERROR_TYPE] = error_type
            if details.error_message:
                event_attributes["error.message"] = details.error_message

        context = hook_context.evaluation_context
        if context.targeting_key:
            event_attributes[EventAttributes.CONTEXT_ID] = context.targeting_key

        if hook_context.provider_metadata:
            event_attributes[EventAttributes.PROVIDER_NAME] = (
                hook_context.provider_metadata.name
            )

        current_span.add_event(OTEL_EVENT_NAME, event_attributes)

    def error(
        self, hook_context: HookContext, exception: Exception, hints: HookHints
    ) -> None:
        current_span = trace.get_current_span()
        current_span.record_exception(exception)

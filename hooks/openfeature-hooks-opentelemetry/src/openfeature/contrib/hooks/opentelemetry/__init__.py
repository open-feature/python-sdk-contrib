import json

from openfeature.flag_evaluation import FlagEvaluationDetails
from openfeature.hook import Hook, HookContext
from opentelemetry import trace

OTEL_EVENT_NAME = "feature_flag"


class EventAttributes:
    FLAG_KEY = f"{OTEL_EVENT_NAME}.key"
    FLAG_VARIANT = f"{OTEL_EVENT_NAME}.variant"
    PROVIDER_NAME = f"{OTEL_EVENT_NAME}.provider_name"


class TracingHook(Hook):
    def after(
        self, hook_context: HookContext, details: FlagEvaluationDetails, hints: dict
    ):
        current_span = trace.get_current_span()

        variant = details.variant
        if variant is None:
            if isinstance(details.value, str):
                variant = str(details.value)
            else:
                variant = json.dumps(details.value)

        event_attributes = {
            EventAttributes.FLAG_KEY: details.flag_key,
            EventAttributes.FLAG_VARIANT: variant,
        }

        if hook_context.provider_metadata:
            event_attributes[
                EventAttributes.PROVIDER_NAME
            ] = hook_context.provider_metadata.name

        current_span.add_event(OTEL_EVENT_NAME, event_attributes)

    def error(self, hook_context: HookContext, exception: Exception, hints: dict):
        current_span = trace.get_current_span()
        current_span.record_exception(exception)

class Attributes:
    OTEL_CONTEXT_ID = "feature_flag.context.id"
    OTEL_EVENT_NAME = "feature_flag.evaluation"
    OTEL_ERROR_TYPE = "error.type"
    OTEL_ERROR_MESSAGE = "error.message"
    OTEL_FLAG_KEY = "feature_flag.key"
    OTEL_FLAG_VARIANT = "feature_flag.result.variant"
    OTEL_PROVIDER_NAME = "feature_flag.provider.name"
    OTEL_RESULT_VALUE = "feature_flag.result.value"
    OTEL_RESULT_REASON = "feature_flag.result.reason"
    OTEL_SET_ID = "feature_flag.set.id"
    OTEL_VERSION = "feature_flag.version"


class Metrics:
    ACTIVE_TOTAL = "feature_flag.evaluation.active_total"
    SUCCESS_TOTAL = "feature_flag.evaluation.success_total"
    REQUEST_TOTAL = "feature_flag.evaluation.request_total"
    ERROR_TOTAL = "feature_flag.evaluation.error_total"

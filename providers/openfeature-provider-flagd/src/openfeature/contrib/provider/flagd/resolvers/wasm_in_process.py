"""
WASM-based (Native Rust) In-Process Resolver.

This resolver uses the native flagd-evaluator (PyO3 bindings) for high-performance
flag evaluation. All evaluation logic and state management happens in Rust.
"""
import typing

from flagd_evaluator import FlagEvaluator
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEventDetails
from openfeature.exception import ErrorCode, FlagNotFoundError
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType, Reason

from ..config import Config
from .process.connector import FlagStateConnector
from .process.connector.file_watcher import FileWatcher
from .process.connector.grpc_watcher import GrpcWatcher

T = typing.TypeVar("T")


class WasmInProcessResolver:
    """
    In-process flag resolver using native Rust evaluator.

    This resolver uses the flagd-evaluator Python bindings (PyO3/Rust) for
    high-performance flag evaluation. All flag state and evaluation logic
    is managed by the Rust implementation.
    """

    def __init__(
        self,
        config: Config,
        emit_provider_ready: typing.Callable[[ProviderEventDetails, dict], None],
        emit_provider_error: typing.Callable[[ProviderEventDetails], None],
        emit_provider_stale: typing.Callable[[ProviderEventDetails], None],
        emit_provider_configuration_changed: typing.Callable[
            [ProviderEventDetails], None
        ],
    ):
        self.config = config
        self.emit_configuration_changed = emit_provider_configuration_changed

        # Create native evaluator (Rust-backed) with permissive validation mode
        # to match Python InProcessResolver behavior
        self.evaluator = FlagEvaluator(permissive=True)

        # Setup connector (FileWatcher or GrpcWatcher)
        # Connectors will call self.update_flags() when flags change
        self.connector: FlagStateConnector = (
            FileWatcher(
                self.config,
                self,  # Pass self instead of FlagStore
                emit_provider_ready,
                emit_provider_error,
            )
            if self.config.offline_flag_source_path
            else GrpcWatcher(
                self.config,
                self,  # Pass self instead of FlagStore
                emit_provider_ready,
                emit_provider_error,
                emit_provider_stale,
            )
        )

    def initialize(self, evaluation_context: EvaluationContext) -> None:
        """Initialize the connector to start receiving flag updates."""
        self.connector.initialize(evaluation_context)

    def shutdown(self) -> None:
        """Shutdown the connector."""
        self.connector.shutdown()

    def update(self, flags_config: dict) -> None:
        """
        Update the flag configuration in the Rust evaluator.

        This is called by connectors (FileWatcher, GrpcWatcher) when
        flag configuration changes. Method name matches FlagStore interface.

        Args:
            flags_config: Flag configuration in flagd format
        """
        try:
            self.evaluator.update_state(flags_config)
            # Extract flag keys and metadata for event
            flags = flags_config.get("flags", {})
            metadata = flags_config.get("metadata", {})
            # Emit configuration changed event with flag keys
            self.emit_configuration_changed(
                ProviderEventDetails(
                    flags_changed=list(flags.keys()),
                    metadata=metadata
                )
            )
        except Exception as e:
            # Log error but don't crash
            import logging
            logger = logging.getLogger("openfeature.contrib")
            logger.error(f"Failed to update flags in Rust evaluator: {e}")

    def _resolve_flag(
        self,
        key: str,
        default_value: T,
        evaluation_context: typing.Optional[EvaluationContext],
        type_validator: typing.Callable[[typing.Any], typing.Optional[T]],
    ) -> FlagResolutionDetails[T]:
        """
        Generic flag resolution logic shared by all resolve methods.

        Args:
            key: Flag key
            default_value: Default value to return if evaluation fails or type mismatches
            evaluation_context: Evaluation context
            type_validator: Function that validates and optionally converts the value.
                           Returns the validated value or None if invalid.
        """
        context = self._build_context(evaluation_context)
        try:
            result = self.evaluator.evaluate(key, context)
            value = result.get("value")

            # Validate and convert value using the provided validator
            validated_value = type_validator(value)
            if validated_value is None:
                validated_value = default_value

            return FlagResolutionDetails(
                value=validated_value,
                variant=result.get("variant"),
                reason=self._map_reason(result.get("reason")),
                error_code=self._map_error_code(result.get("errorCode")),
                flag_metadata=result.get("flagMetadata", {}),
            )
        except KeyError:
            raise FlagNotFoundError(f"Flag with key {key} not found")
        except RuntimeError as e:
            raise FlagNotFoundError(f"Flag evaluation failed: {e}")

    def resolve_boolean_details(
        self,
        key: str,
        default_value: bool,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        """Resolve a boolean flag using the native Rust evaluator."""
        return self._resolve_flag(
            key,
            default_value,
            evaluation_context,
            lambda v: v if isinstance(v, bool) else None,
        )

    def resolve_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        """Resolve a string flag using the native Rust evaluator."""
        return self._resolve_flag(
            key,
            default_value,
            evaluation_context,
            lambda v: v if isinstance(v, str) else None,
        )

    def resolve_integer_details(
        self,
        key: str,
        default_value: int,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        """Resolve an integer flag using the native Rust evaluator."""
        return self._resolve_flag(
            key,
            default_value,
            evaluation_context,
            lambda v: v if isinstance(v, int) else None,
        )

    def resolve_float_details(
        self,
        key: str,
        default_value: float,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        """Resolve a float flag using the native Rust evaluator."""
        def validate_float(v: typing.Any) -> typing.Optional[float]:
            # Allow int to float conversion
            if isinstance(v, (int, float)):
                return float(v)
            return None

        return self._resolve_flag(key, default_value, evaluation_context, validate_float)

    def resolve_object_details(
        self,
        key: str,
        default_value: typing.Union[
            typing.Sequence[FlagValueType], typing.Mapping[str, FlagValueType]
        ],
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[
        typing.Union[typing.Sequence[FlagValueType], typing.Mapping[str, FlagValueType]]
    ]:
        """Resolve an object flag using the native Rust evaluator."""
        return self._resolve_flag(
            key,
            default_value,
            evaluation_context,
            lambda v: v if isinstance(v, (dict, list)) else None,
        )

    def _build_context(
        self, evaluation_context: typing.Optional[EvaluationContext]
    ) -> dict:
        """
        Build context dict for Rust evaluator from EvaluationContext.

        The Rust evaluator expects a flat dict with all context attributes.
        """
        if not evaluation_context:
            return {}

        context = dict(evaluation_context.attributes) if evaluation_context.attributes else {}

        # Add targeting key if present
        if evaluation_context.targeting_key:
            context["targetingKey"] = evaluation_context.targeting_key

        return context

    def _map_reason(self, rust_reason: typing.Optional[str]) -> Reason:
        """Map Rust evaluator reason strings to OpenFeature Reason enum."""
        if not rust_reason:
            return Reason.UNKNOWN

        reason_map = {
            "STATIC": Reason.STATIC,
            "DEFAULT": Reason.DEFAULT,
            "TARGETING_MATCH": Reason.TARGETING_MATCH,
            "DISABLED": Reason.DISABLED,
            "ERROR": Reason.ERROR,
            "FLAG_NOT_FOUND": Reason.ERROR,
            "FALLBACK": Reason.ERROR,  # Fallback to default when variant is null/undefined
        }
        return reason_map.get(rust_reason, Reason.UNKNOWN)

    def _map_error_code(self, rust_error_code: typing.Optional[str]) -> typing.Optional[ErrorCode]:
        """Map Rust evaluator error code strings to OpenFeature ErrorCode enum."""
        if not rust_error_code:
            return None

        error_code_map = {
            "FLAG_NOT_FOUND": ErrorCode.FLAG_NOT_FOUND,
            "PARSE_ERROR": ErrorCode.PARSE_ERROR,
            "TYPE_MISMATCH": ErrorCode.TYPE_MISMATCH,
            "GENERAL": ErrorCode.GENERAL,
        }
        return error_code_map.get(rust_error_code)

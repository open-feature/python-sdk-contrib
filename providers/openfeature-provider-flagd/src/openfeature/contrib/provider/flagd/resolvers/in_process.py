import typing

from openfeature.contrib.tools.flagd.core import FlagdCore
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEventDetails
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType

from ..config import Config
from .process.connector import FlagStateConnector
from .process.connector.file_watcher import FileWatcher
from .process.connector.grpc_watcher import GrpcWatcher

T = typing.TypeVar("T")


class _FlagStoreAdapter:
    """Bridges FlagdCore with connectors that expect a FlagStore-like update() interface."""

    def __init__(
        self,
        evaluator: FlagdCore,
        emit_provider_configuration_changed: typing.Callable[
            [ProviderEventDetails], None
        ],
    ):
        self.evaluator = evaluator
        self.emit_provider_configuration_changed = emit_provider_configuration_changed

    def update(self, flags_data: dict) -> None:
        changed_keys = self.evaluator.set_flags_and_get_changed_keys(flags_data)
        metadata = self.evaluator.get_flag_set_metadata()
        self.emit_provider_configuration_changed(
            ProviderEventDetails(flags_changed=changed_keys, metadata=dict(metadata))
        )


class InProcessResolver:
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
        self.evaluator = FlagdCore()

        # Adapter lets connectors push flag data to FlagdCore via the
        # same .update(dict) interface they used with the old FlagStore.
        flag_store_adapter = _FlagStoreAdapter(
            self.evaluator, emit_provider_configuration_changed
        )

        self.connector: FlagStateConnector = (
            FileWatcher(
                self.config,
                flag_store_adapter,  # type: ignore[arg-type]
                emit_provider_ready,
                emit_provider_error,
            )
            if self.config.offline_flag_source_path
            else GrpcWatcher(
                self.config,
                flag_store_adapter,  # type: ignore[arg-type]
                emit_provider_ready,
                emit_provider_error,
                emit_provider_stale,
            )
        )

    def initialize(self, evaluation_context: EvaluationContext) -> None:
        self.connector.initialize(evaluation_context)

    def shutdown(self) -> None:
        self.connector.shutdown()

    def resolve_boolean_details(
        self,
        key: str,
        default_value: bool,
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[bool]:
        return self.evaluator.resolve_boolean_value(
            key, default_value, evaluation_context
        )

    def resolve_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[str]:
        return self.evaluator.resolve_string_value(
            key, default_value, evaluation_context
        )

    def resolve_float_details(
        self,
        key: str,
        default_value: float,
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[float]:
        return self.evaluator.resolve_float_value(
            key, default_value, evaluation_context
        )

    def resolve_integer_details(
        self,
        key: str,
        default_value: int,
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[int]:
        return self.evaluator.resolve_integer_value(
            key, default_value, evaluation_context
        )

    def resolve_object_details(
        self,
        key: str,
        default_value: typing.Sequence[FlagValueType]
        | typing.Mapping[str, FlagValueType],
        evaluation_context: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[
        typing.Sequence[FlagValueType] | typing.Mapping[str, FlagValueType]
    ]:
        return self.evaluator.resolve_object_value(
            key, default_value, evaluation_context
        )

import typing

from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEventDetails
from openfeature.exception import FlagNotFoundError, ParseError
from openfeature.flag_evaluation import FlagResolutionDetails, Reason

from ..config import Config
from .process.connector import FlagStateConnector
from .process.connector.file_watcher import FileWatcher
from .process.connector.grpc_watcher import GrpcWatcher
from .process.flags import FlagStore
from .process.targeting import targeting

T = typing.TypeVar("T")


class InProcessResolver:
    def __init__(
        self,
        config: Config,
        emit_provider_ready: typing.Callable[[ProviderEventDetails], None],
        emit_provider_error: typing.Callable[[ProviderEventDetails], None],
        emit_provider_configuration_changed: typing.Callable[
            [ProviderEventDetails], None
        ],
    ):
        self.config = config
        self.flag_store = FlagStore(emit_provider_configuration_changed)
        self.connector: FlagStateConnector = (
            FileWatcher(
                self.config, self.flag_store, emit_provider_ready, emit_provider_error
            )
            if self.config.offline_flag_source_path
            else GrpcWatcher(
                self.config, self.flag_store, emit_provider_ready, emit_provider_error
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
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        return self._resolve(key, default_value, evaluation_context)

    def resolve_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        return self._resolve(key, default_value, evaluation_context)

    def resolve_float_details(
        self,
        key: str,
        default_value: float,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        result = self._resolve(key, default_value, evaluation_context)
        if isinstance(result.value, int):
            result.value = float(result.value)
        return result

    def resolve_integer_details(
        self,
        key: str,
        default_value: int,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        result = self._resolve(key, default_value, evaluation_context)
        return result

    def resolve_object_details(
        self,
        key: str,
        default_value: typing.Union[dict, list],
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[typing.Union[dict, list]]:
        return self._resolve(key, default_value, evaluation_context)

    def _resolve(
        self,
        key: str,
        default_value: T,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[T]:
        flag = self.flag_store.get_flag(key)
        if not flag:
            raise FlagNotFoundError(f"Flag with key {key} not present in flag store.")

        if flag.state == "DISABLED":
            return FlagResolutionDetails(default_value, reason=Reason.DISABLED)

        if not flag.targeting:
            variant, value = flag.default
            return FlagResolutionDetails(value, variant=variant, reason=Reason.STATIC)

        variant = targeting(flag.key, flag.targeting, evaluation_context)

        if variant is None:
            variant, value = flag.default
            return FlagResolutionDetails(value, variant=variant, reason=Reason.DEFAULT)
        if not isinstance(variant, (str, bool)):
            raise ParseError(
                "Parsed JSONLogic targeting did not return a string or bool"
            )

        variant, value = flag.get_variant(variant)
        if not value:
            raise ParseError(f"Resolved variant {variant} not in variants config.")

        return FlagResolutionDetails(
            value,
            variant=variant,
            reason=Reason.TARGETING_MATCH,
        )

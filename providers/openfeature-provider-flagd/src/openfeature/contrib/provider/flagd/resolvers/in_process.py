import time
import typing

from json_logic import builtins, jsonLogic  # type: ignore[import-untyped]

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import FlagNotFoundError, ParseError
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
from openfeature.provider.provider import AbstractProvider

from ..config import Config
from .process.connector import FlagStateConnector
from .process.connector.file_watcher import FileWatcher
from .process.connector.grpc_watcher import GrpcWatcher
from .process.custom_ops import ends_with, fractional, sem_ver, starts_with
from .process.flags import FlagStore

T = typing.TypeVar("T")


class InProcessResolver:
    OPERATORS: typing.ClassVar[dict] = {
        **builtins.BUILTINS,
        "fractional": fractional,
        "starts_with": starts_with,
        "ends_with": ends_with,
        "sem_ver": sem_ver,
    }

    def __init__(self, config: Config, provider: AbstractProvider):
        self.config = config
        self.provider = provider
        self.flag_store = FlagStore(provider)
        self.connector: FlagStateConnector = (
            FileWatcher(
                self.config.offline_flag_source_path,
                self.provider,
                self.flag_store,
                self.config.offline_poll_interval_seconds,
            )
            if self.config.offline_flag_source_path
            else GrpcWatcher(self.config, self.provider, self.flag_store)
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
        if not isinstance(result.value, float):
            result.value = float(result.value)
        return result

    def resolve_integer_details(
        self,
        key: str,
        default_value: int,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        result = self._resolve(key, default_value, evaluation_context)
        if not isinstance(result.value, int):
            result.value = int(result.value)
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

        json_logic_context = evaluation_context.attributes if evaluation_context else {}
        json_logic_context["$flagd"] = {"flagKey": key, "timestamp": int(time.time())}
        json_logic_context["targetingKey"] = (
            evaluation_context.targeting_key if evaluation_context else None
        )
        variant = jsonLogic(flag.targeting, json_logic_context, self.OPERATORS)
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

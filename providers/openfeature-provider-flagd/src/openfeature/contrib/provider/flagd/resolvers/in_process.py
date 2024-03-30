import typing

from json_logic import builtins, jsonLogic

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import FlagNotFoundError
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
from openfeature.provider.provider import AbstractProvider

from ..config import Config
from ..flag_type import FlagType
from .process.custom_ops import fractional
from .process.file_watcher import FileWatcherFlagStore

T = typing.TypeVar("T")


class InProcessResolver:
    OPERATORS: typing.ClassVar[dict] = {**builtins.BUILTINS, "fractional": fractional}

    def __init__(self, config: Config, provider: AbstractProvider):
        self.config = config
        self.provider = provider
        if not self.config.offline_flag_source_path:
            raise ValueError(
                "offline_flag_source_path must be provided when using in-process resolver"
            )
        self.flag_store = FileWatcherFlagStore(
            self.config.offline_flag_source_path, self.provider
        )

    def shutdown(self) -> None:
        self.flag_store.shutdown()

    def resolve_boolean_details(
        self,
        key: str,
        default_value: bool,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        return self._resolve(key, FlagType.BOOLEAN, default_value, evaluation_context)

    def resolve_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        return self._resolve(key, FlagType.STRING, default_value, evaluation_context)

    def resolve_float_details(
        self,
        key: str,
        default_value: float,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        return self._resolve(key, FlagType.FLOAT, default_value, evaluation_context)

    def resolve_integer_details(
        self,
        key: str,
        default_value: int,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        return self._resolve(key, FlagType.INTEGER, default_value, evaluation_context)

    def resolve_object_details(
        self,
        key: str,
        default_value: typing.Union[dict, list],
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[typing.Union[dict, list]]:
        return self._resolve(key, FlagType.OBJECT, default_value, evaluation_context)

    def _resolve(
        self,
        key: str,
        flag_type: FlagType,
        default_value: T,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[T]:
        flag = self.flag_store.get_flag(key)
        if not flag:
            raise FlagNotFoundError(f"Flag with key {key} not present in flag store.")
        if flag["state"] != "ENABLED":
            return FlagResolutionDetails(default_value, reason=Reason.DISABLED)

        variants = flag["variants"]
        default = variants.get(flag.get("defaultVariant"), default_value)
        if "targeting" not in flag:
            return FlagResolutionDetails(default, reason=Reason.STATIC)

        json_logic_context = evaluation_context.attributes if evaluation_context else {}
        json_logic_context["$flagd"] = {"flagKey": key}
        variant = jsonLogic(flag["targeting"], json_logic_context, self.OPERATORS)

        value = flag["variants"].get(variant, default)
        # TODO: Check type matches

        return FlagResolutionDetails(
            value,
            reason=Reason.TARGETING_MATCH,
            variant=variant,
        )

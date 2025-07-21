import typing

from openfeature.contrib.provider.flagd.resolvers.process.connector.file_watcher import (
    FileWatcher,
)
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEventDetails
from openfeature.exception import ErrorCode, FlagNotFoundError, GeneralError, ParseError
from openfeature.flag_evaluation import FlagResolutionDetails, Reason

from ..config import Config
from .process.connector import FlagStateConnector
from .process.connector.grpc_watcher import GrpcWatcher
from .process.flags import FlagStore, Flag
from .process.targeting import targeting

T = typing.TypeVar("T")


def _merge_metadata(
    flag_metadata: typing.Optional[
        typing.Mapping[str, typing.Union[float, int, str, bool]]
    ],
    flag_set_metadata: typing.Optional[
        typing.Mapping[str, typing.Union[float, int, str, bool]]
    ],
) -> typing.Mapping[str, typing.Union[float, int, str, bool]]:
    metadata = {} if flag_set_metadata is None else dict(flag_set_metadata)

    if flag_metadata is not None:
        for key, value in flag_metadata.items():
            metadata[key] = value

    return metadata


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
        self.flag_store = FlagStore(emit_provider_configuration_changed)
        self.connector: FlagStateConnector = (
            FileWatcher(
                self.config, self.flag_store, emit_provider_ready, emit_provider_error
            )
            if self.config.offline_flag_source_path
            else GrpcWatcher(
                self.config,
                self.flag_store,
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
        return self._resolve(key, default_value, evaluation_context)

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

        metadata = _merge_metadata(flag.metadata, self.flag_store.flag_set_metadata)

        if flag.state == "DISABLED":
            return FlagResolutionDetails(
                default_value, flag_metadata=metadata, reason=Reason.DISABLED
            )

        if not flag.targeting:
            return _default_resolve(flag, metadata, Reason.STATIC)

        try:
            variant = targeting(flag.key, flag.targeting, evaluation_context)
            if variant is None:
                return _default_resolve(flag, metadata, Reason.DEFAULT)

            # convert to string to support shorthand (boolean in python is with capital T hence the special case)
            if isinstance(variant, bool):
                variant = str(variant).lower()
            elif not isinstance(variant, str):
                variant = str(variant)

            if variant not in flag.variants:
                raise GeneralError(
                    f"Resolved variant {variant} not in variants config."
                )

        except ReferenceError:
            raise ParseError(f"Invalid targeting {targeting}") from ReferenceError

        variant, value = flag.get_variant(variant)
        if value is None:
            raise GeneralError(f"Resolved variant {variant} not in variants config.")

        return FlagResolutionDetails(
            value,
            variant=variant,
            reason=Reason.TARGETING_MATCH,
            flag_metadata=metadata,
        )


def _default_resolve(flag: Flag, metadata: typing.Mapping[str, typing.Union[float, int, str, bool]], reason: Reason) -> FlagResolutionDetails:
    variant, value = flag.default
    if variant is None:
        return FlagResolutionDetails(
            value,
            variant=variant,
            reason=Reason.ERROR,
            error_code=ErrorCode.FLAG_NOT_FOUND,
            flag_metadata=metadata,
        )
    if variant not in flag.variants:
        raise GeneralError(f"Resolved variant {variant} not in variants config.")
    return FlagResolutionDetails(
        value, variant=variant, flag_metadata=metadata, reason=reason
    )

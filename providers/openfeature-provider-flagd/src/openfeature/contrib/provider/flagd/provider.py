"""
# This is a Python Provider to interact with flagd
#
# -- Usage --
# open_feature_api.set_provider(flagd_provider.FlagdProvider())
# flag_value =  open_feature_client.get_string_value(
#                   key="foo",
#                   default_value="missingflag"
#               )
# print(f"Flag Value is: {flag_value}")
#   OR the more verbose option
# flag = open_feature_client.get_string_details(key="foo", default_value="missingflag")
# print(f"Flag is: {flag.value}")
#   OR
# print(f"Flag Details: {vars(flag)}"")
#
# -- Customisation --
# Follows flagd defaults: 'http' protocol on 'localhost' on port '8013'
# But can be overridden:
# provider = open_feature_api.get_provider()
# provider.initialise(schema="https",endpoint="example.com",port=1234,timeout=10)
"""

import typing
import warnings

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails
from openfeature.provider import AbstractProvider
from openfeature.provider.metadata import Metadata

from .config import CacheType, Config, ResolverType
from .resolvers import AbstractResolver, GrpcResolver, InProcessResolver

T = typing.TypeVar("T")


class FlagdProvider(AbstractProvider):
    """Flagd OpenFeature Provider"""

    def __init__(  # noqa: PLR0913
        self,
        host: typing.Optional[str] = None,
        port: typing.Optional[int] = None,
        tls: typing.Optional[bool] = None,
        deadline_ms: typing.Optional[int] = None,
        timeout: typing.Optional[int] = None,
        retry_backoff_ms: typing.Optional[int] = None,
        selector: typing.Optional[str] = None,
        resolver_type: typing.Optional[ResolverType] = None,
        offline_flag_source_path: typing.Optional[str] = None,
        stream_deadline_ms: typing.Optional[int] = None,
        keep_alive_time: typing.Optional[int] = None,
        cache: typing.Optional[CacheType] = None,
        max_cache_size: typing.Optional[int] = None,
        retry_backoff_max_ms: typing.Optional[int] = None,
        retry_grace_period: typing.Optional[int] = None,
        cert_path: typing.Optional[str] = None,
    ):
        """
        Create an instance of the FlagdProvider

        :param host: the host to make requests to
        :param port: the port the flagd service is available on
        :param tls: enable/disable secure TLS connectivity
        :param deadline_ms: the maximum to wait before a request times out
        :param timeout: the maximum time to wait before a request times out
        :param retry_backoff_ms: the number of milliseconds to backoff
        :param offline_flag_source_path: the path to the flag source file
        :param stream_deadline_ms: the maximum time to wait before a request times out
        :param keep_alive_time: the number of milliseconds to keep alive
        :param resolver_type: the type of resolver to use
        """
        if deadline_ms is None and timeout is not None:
            deadline_ms = timeout * 1000
            warnings.warn(
                "'timeout' property is deprecated, please use 'deadline' instead, be aware that 'deadline' is in milliseconds",
                DeprecationWarning,
                stacklevel=2,
            )

        self.config = Config(
            host=host,
            port=port,
            tls=tls,
            deadline_ms=deadline_ms,
            retry_backoff_ms=retry_backoff_ms,
            retry_backoff_max_ms=retry_backoff_max_ms,
            retry_grace_period=retry_grace_period,
            selector=selector,
            resolver=resolver_type,
            offline_flag_source_path=offline_flag_source_path,
            stream_deadline_ms=stream_deadline_ms,
            keep_alive_time=keep_alive_time,
            cache=cache,
            max_cache_size=max_cache_size,
            cert_path=cert_path,
        )

        self.resolver = self.setup_resolver()

    def setup_resolver(self) -> AbstractResolver:
        if self.config.resolver == ResolverType.RPC:
            return GrpcResolver(
                self.config,
                self.emit_provider_ready,
                self.emit_provider_error,
                self.emit_provider_stale,
                self.emit_provider_configuration_changed,
            )
        elif (
            self.config.resolver == ResolverType.IN_PROCESS
            or self.config.resolver == ResolverType.FILE
        ):
            return InProcessResolver(
                self.config,
                self.emit_provider_ready,
                self.emit_provider_error,
                self.emit_provider_stale,
                self.emit_provider_configuration_changed,
            )
        else:
            raise ValueError(
                f"`resolver_type` parameter invalid: {self.config.resolver}"
            )

    def initialize(self, evaluation_context: EvaluationContext) -> None:
        self.resolver.initialize(evaluation_context)

    def shutdown(self) -> None:
        if self.resolver:
            self.resolver.shutdown()

    def get_metadata(self) -> Metadata:
        """Returns provider metadata"""
        return Metadata(name="FlagdProvider")

    def resolve_boolean_details(
        self,
        key: str,
        default_value: bool,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        return self.resolver.resolve_boolean_details(
            key, default_value, evaluation_context
        )

    def resolve_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        return self.resolver.resolve_string_details(
            key, default_value, evaluation_context
        )

    def resolve_float_details(
        self,
        key: str,
        default_value: float,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        return self.resolver.resolve_float_details(
            key, default_value, evaluation_context
        )

    def resolve_integer_details(
        self,
        key: str,
        default_value: int,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        return self.resolver.resolve_integer_details(
            key, default_value, evaluation_context
        )

    def resolve_object_details(
        self,
        key: str,
        default_value: typing.Union[dict, list],
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[typing.Union[dict, list]]:
        return self.resolver.resolve_object_details(
            key, default_value, evaluation_context
        )

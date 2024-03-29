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

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails
from openfeature.provider.metadata import Metadata
from openfeature.provider.provider import AbstractProvider

from .config import Config, ResolverType
from .resolvers.grpc import GrpcResolver

T = typing.TypeVar("T")


class FlagdProvider(AbstractProvider):
    """Flagd OpenFeature Provider"""

    def __init__(
        self,
        host: typing.Optional[str] = None,
        port: typing.Optional[int] = None,
        tls: typing.Optional[bool] = None,
        timeout: typing.Optional[int] = None,
        resolver_type: typing.Optional[ResolverType] = None,
    ):
        """
        Create an instance of the FlagdProvider

        :param host: the host to make requests to
        :param port: the port the flagd service is available on
        :param tls: enable/disable secure TLS connectivity
        :param timeout: the maximum to wait before a request times out
        """
        self.config = Config(
            host=host,
            port=port,
            tls=tls,
            timeout=timeout,
            resolver_type=resolver_type,
        )

        if self.config.resolver_type == ResolverType.GRPC:
            self.resolver = GrpcResolver(self.config)
        else:
            raise ValueError("`resolver_type` parameter invalid")

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

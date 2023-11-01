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
from numbers import Number

import grpc
from google.protobuf.struct_pb2 import Struct
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    FlagNotFoundError,
    GeneralError,
    InvalidContextError,
    ParseError,
    TypeMismatchError,
)
from openfeature.flag_evaluation import FlagEvaluationDetails
from openfeature.provider.provider import AbstractProvider

from .defaults import Defaults
from .flag_type import FlagType
from .proto.schema.v1 import schema_pb2, schema_pb2_grpc


class FlagdProvider(AbstractProvider):
    """Flagd OpenFeature Provider"""

    def __init__(
        self,
        name: str = "flagd",
        schema: str = Defaults.SCHEMA,
        host: str = Defaults.HOST,
        port: int = Defaults.PORT,
        timeout: int = Defaults.TIMEOUT,
    ):
        """
        Create an instance of the FlagdProvider

        :param name: the name of the provider to be stored in metadata
        :param schema: the schema for the transport protocol, e.g. 'http', 'https'
        :param host: the host to make requests to
        :param port: the port the flagd service is available on
        :param timeout: the maximum to wait before a request times out
        """
        self.provider_name = name
        self.schema = schema
        self.host = host
        self.port = port
        self.timeout = timeout

        channel_factory = (
            grpc.insecure_channel if schema == "http" else grpc.secure_channel
        )
        self.channel = channel_factory(f"{self.host}:{self.port}")
        self.stub = schema_pb2_grpc.ServiceStub(self.channel)

    def shutdown(self):
        self.channel.close()

    def get_metadata(self):
        """Returns provider metadata"""
        return {
            "name": self.get_name(),
            "schema": self.schema,
            "host": self.host,
            "port": self.port,
            "timeout": self.timeout,
        }

    def get_name(self) -> str:
        """Returns provider name"""
        return self.provider_name

    def resolve_boolean_details(
        self,
        key: str,
        default_value: bool,
        evaluation_context: EvaluationContext = None,
    ):
        return self._resolve(key, FlagType.BOOLEAN, default_value, evaluation_context)

    def resolve_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: EvaluationContext = None,
    ):
        return self._resolve(key, FlagType.STRING, default_value, evaluation_context)

    def resolve_float_details(
        self,
        key: str,
        default_value: Number,
        evaluation_context: EvaluationContext = None,
    ):
        return self._resolve(key, FlagType.FLOAT, default_value, evaluation_context)

    def resolve_integer_details(
        self,
        key: str,
        default_value: Number,
        evaluation_context: EvaluationContext = None,
    ):
        return self._resolve(key, FlagType.INTEGER, default_value, evaluation_context)

    def resolve_object_details(
        self,
        key: str,
        default_value: typing.Union[dict, list],
        evaluation_context: EvaluationContext = None,
    ):
        return self._resolve(key, FlagType.OBJECT, default_value, evaluation_context)

    def _resolve(
        self,
        flag_key: str,
        flag_type: FlagType,
        default_value: typing.Any,
        evaluation_context: EvaluationContext,
    ):
        context = self._convert_context(evaluation_context)
        try:
            if flag_type == FlagType.BOOLEAN:
                request = schema_pb2.ResolveBooleanRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveBoolean(request)
            elif flag_type == FlagType.STRING:
                request = schema_pb2.ResolveStringRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveString(request)
            elif flag_type == FlagType.OBJECT:
                request = schema_pb2.ResolveObjectRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveObject(request)
            elif flag_type == FlagType.FLOAT:
                request = schema_pb2.ResolveFloatRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveFloat(request)
            elif flag_type == FlagType.INTEGER:
                request = schema_pb2.ResolveIntRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveInt(request)
            else:
                raise ValueError(f"Unknown flag type: {flag_type}")

        except grpc.RpcError as e:
            code = e.code()
            message = f"received grpc status code {code}"

            if code == grpc.StatusCode.NOT_FOUND:
                raise FlagNotFoundError(message)
            elif code == grpc.StatusCode.INVALID_ARGUMENT:
                raise TypeMismatchError(message)
            elif code == grpc.StatusCode.DATA_LOSS:
                raise ParseError(message)
            raise GeneralError(message)

        # Got a valid flag and valid type. Return it.
        return FlagEvaluationDetails(
            flag_key=flag_key,
            value=response.value,
            reason=response.reason,
            variant=response.variant,
        )

    def _convert_context(self, evaluation_context: EvaluationContext):
        s = Struct()
        if evaluation_context:
            try:
                s.update(evaluation_context.attributes)
            except ValueError as exc:
                message = (
                    "could not serialize evaluation context to google.protobuf.Struct"
                )
                raise InvalidContextError(message) from exc
        return s

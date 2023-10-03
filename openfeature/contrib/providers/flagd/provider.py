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

import requests
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import FlagEvaluationDetails
from openfeature.provider.provider import AbstractProvider

from .defaults import Defaults
from .evaluation_context_serializer import EvaluationContextSerializer
from .flag_type import FlagType
from .web_api_url_factory import WebApiUrlFactory


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

        self.url_factory = WebApiUrlFactory(self.schema, self.host, self.port)

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
        return self.__resolve(key, FlagType.BOOLEAN, default_value, evaluation_context)

    def resolve_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: EvaluationContext = None,
    ):
        return self.__resolve(key, FlagType.STRING, default_value, evaluation_context)

    def resolve_float_details(
        self,
        key: str,
        default_value: Number,
        evaluation_context: EvaluationContext = None,
    ):
        return self.__resolve(key, FlagType.FLOAT, default_value, evaluation_context)

    def resolve_int_details(
        self,
        key: str,
        default_value: Number,
        evaluation_context: EvaluationContext = None,
    ):
        return self.__resolve(key, FlagType.INTEGER, default_value, evaluation_context)

    def resolve_object_details(
        self,
        key: str,
        default_value: typing.Union[dict, list],
        evaluation_context: EvaluationContext = None,
    ):
        return self.__resolve(key, FlagType.OBJECT, default_value, evaluation_context)

    def __resolve(
        self,
        flag_key: str,
        flag_type: FlagType,
        default_value: typing.Any,
        evaluation_context: EvaluationContext,
    ):
        """
        This method is equivalent to:
        curl -X POST http://localhost:8013/{path} \
             -H "Content-Type: application/json" \
             -d '{"flagKey": key, "context": evaluation_context}'
        """

        payload = {
            "flagKey": flag_key,
            "context": EvaluationContextSerializer.to_dict(evaluation_context),
        }

        try:
            url_endpoint = self.url_factory.get_path_for(flag_type)

            response = requests.post(
                url=url_endpoint, timeout=self.timeout, json=payload
            )

        except Exception:
            # Perhaps a timeout? Return the default as an error.
            # The return above and this are separate because in the case of a timeout,
            # the JSON is not available
            # So return a stock, generic answer.

            return FlagEvaluationDetails(
                flag_key=flag_key,
                value=default_value,
                reason=ErrorCode.PROVIDER_NOT_READY,
                variant=default_value,
            )

        json_content = response.json()

        # If lookup worked (200 response) get flag (or empty)
        # This is the "ideal" case.
        if response.status_code == 200:
            # Got a valid flag and valid type. Return it.
            if "value" in json_content:
                # Got a valid flag value for key: {key} of: {json_content['value']}
                return FlagEvaluationDetails(
                    flag_key=flag_key,
                    value=json_content["value"],
                    reason=json_content["reason"],
                    variant=json_content["variant"],
                )

        # Otherwise HTTP call worked
        # However, flag either doesn't exist or doesn't match the type
        # eg. Expecting a string but this value is a boolean.
        # Return whatever we got from the backend.
        return FlagEvaluationDetails(
            flag_key=flag_key,
            value=default_value,
            reason=json_content["code"],
            variant=default_value,
            error_code=json_content["message"],
        )

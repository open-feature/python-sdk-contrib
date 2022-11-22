"""
# This is a Python Provider to interact with flagd
#
# -- Usage --
# open_feature_api.set_provider(flagd_provider.FlagDProvider())
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
from open_feature.evaluation_context.evaluation_context import EvaluationContext
from open_feature.flag_evaluation.error_code import ErrorCode
from open_feature.flag_evaluation.flag_evaluation_details import FlagEvaluationDetails
from open_feature.provider.provider import AbstractProvider


class FlagDProvider(AbstractProvider):
    """FlagD OpenFeature Provider"""

    FLAGD_API_PATH_BOOLEAN = "schema.v1.Service/ResolveBoolean"
    FLAGD_API_PATH_STRING = "schema.v1.Service/ResolveString"
    FLAGD_API_PATH_NUMBER = "schema.v1.Service/ResolveFloat"
    FLAGD_API_PATH_FLOAT = "schema.v1.Service/ResolveFloat"
    FLAGD_API_PATH_INTEGER = "schema.v1.Service/ResolveInteger"
    FLAGD_API_PATH_OBJECT = "schema.v1.Service/ResolveObject"

    def __init__(
        self,
        name: str = "flagd",
        schema: str = "http",
        endpoint: str = "localhost",
        port: int = 8013,
        timeout: int = 2,
    ):
        """
        Create an instance of the FlagDProvider

        :param name: the name of the provider to be stored in metadata
        :param schema: the schema for the transport protocol, e.g. 'http', 'https'
        :param endpoint: the host to make requests to 
        :param port: the port the flagd service is available on
        :param timeout: the maximum to wait before a request times out
        """
        self.provider_name = name
        self.schema = schema
        self.endpoint = endpoint
        self.port = port
        self.timeout = timeout

        

    def initialise(
        self,
        schema: str = "http",
        endpoint: str = "localhost",
        port: int = 8013,
        timeout: int = 2,
    ):
        """
        Initialise FlagD with endpoint details.

        :param schema: the schema for the transport protocol, e.g. 'http', 'https'
        :param endpoint: the host to make requests to 
        :param port: the port the flagd service is available on
        :param timeout: the maximum to wait before a request times out
        """
        self.schema = schema
        self.endpoint = endpoint
        self.port = port
        self.timeout = timeout

    def get_metadata(self):
        """Returns provider metadata"""
        return {
            "name": self.provider_name,
            "schema": self.schema,
            "endpoint": self.endpoint,
            "port": self.port,
            "timeout": self.timeout,
        }

    def get_name(self) -> str:
        """Returns provider name"""
        return self.provider_name

    def get_boolean_details(
        self,
        key: str,
        default_value: bool,
        evaluation_context: EvaluationContext = None,
        flag_evaluation_options: typing.Any = None,
    ):
        return self.__resolve(key, default_value, self.FLAGD_API_PATH_BOOLEAN)

    def get_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: EvaluationContext = None,
        flag_evaluation_options: typing.Any = None,
    ):
        return self.__resolve(key, default_value, self.FLAGD_API_PATH_STRING)

    def get_number_details(
        self,
        key: str,
        default_value: Number,
        evaluation_context: EvaluationContext = None,
        flag_evaluation_options: typing.Any = None,
    ):
        return self.__resolve(key, default_value, self.FLAGD_API_PATH_NUMBER)

    def get_float_details(
        self,
        key: str,
        default_value: Number,
        evaluation_context: EvaluationContext = None,
        flag_evaluation_options: typing.Any = None,
    ):
        return self.__resolve(key, default_value, self.FLAGD_API_PATH_NUMBER)

    def get_number_details(
        self,
        key: str,
        default_value: Number,
        evaluation_context: EvaluationContext = None,
        flag_evaluation_options: typing.Any = None,
    ):
        return self.__resolve(key, default_value, self.FLAGD_API_PATH_NUMBER)

    def get_object_details(
        self,
        key: str,
        default_value: dict,
        evaluation_context: EvaluationContext = None,
        flag_evaluation_options: typing.Any = None,
    ):
        return self.__resolve(key, default_value, self.FLAGD_API_PATH_OBJECT)
    
    def __resolve(
        self,
        key: str,
        default_value: typing.Any,
        evaluation_context: EvaluationContext,
        path: str
    ):
        """
        This method is equivalent to:
        curl -X POST http://localhost:8013/{path} \
             -H "Content-Type: application/json" \
             -d '{"flagKey": key, "context": evaluation_context}'
        """

        payload = {
            "flagKey": key,
            # "context": {**evaluation_context.},
        }

        try:
            url_endpoint = f"{self.schema}://{self.endpoint}:{self.port}/{path}"

            response = requests.post(
                url=url_endpoint, timeout=self.timeout, json=payload
            )

        except Exception:
            # Perhaps a timeout? Return the default as an error.
            # The return above and this are separate because in the case of a timeout,
            # the JSON is not available
            # So return a stock, generic answer.

            return FlagEvaluationDetails(
                key=key,
                value=default_value,
                reason=ErrorCode.PROVIDER_NOT_READY,
                variant=default_value
            )

        json_content = response.json()

        # If lookup worked (200 response) get flag (or empty)
        # This is the "ideal" case.
        if response.status_code == 200:

            # Got a valid flag and valid type. Return it.
            if "value" in json_content:
                # Got a valid flag value for key: {key} of: {json_content['value']}
                return FlagEvaluationDetails(
                    key=key,
                    value=json_content["value"],
                    reason=json_content["reason"],
                    variant=json_content["variant"],
                )

        # Otherwise HTTP call worked
        # However, flag either doesn't exist or doesn't match the type
        # eg. Expecting a string but this value is a boolean.
        # Return whatever we got from the backend.
        return FlagEvaluationDetails(
            key=key,
            value=default_value,
            reason=json_content["code"],
            variant=default_value,
            error_code=json_content["message"],
        )

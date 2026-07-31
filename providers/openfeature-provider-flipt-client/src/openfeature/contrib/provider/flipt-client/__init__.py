from typing import Optional, Union, Any

from enum import Enum
from openfeature.provider import AbstractProvider, Metadata
from flipt_client.models import (
    FetchMode, 
    AuthenticationStrategy, 
    ClientTokenAuthentication,
    JWTAuthentication,
    ClientOptions
)
from flipt_client import FliptEvaluationClient

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import FlagResolutionDetails, Reason, FlagType

# Expose the provider and relevant models
__all__ = ['FliptClientProvider', 'ClientTokenAuthentication', 'JWTAuthentication', 'FetchMode'] 


class FliptClientProvider(AbstractProvider):
    '''Wrapper for the Flipt Evaluation Client with the standard OpenFeature Provider interface'''

    def __init__(
        self,
        base_url: str,
        namespace: str = 'default',
        *,
        update_interval: Optional[int] = None,
        authentication: Optional[AuthenticationStrategy] = None,
        reference: Optional[str] = None,
        fetch_mode: Optional[FetchMode] = None
    ):
        self._client=FliptEvaluationClient(
            namespace=namespace,
            opts=ClientOptions(
                url=base_url,
                update_interval=update_interval,
                authentication=authentication,
                reference=reference,
                fetch_mode=fetch_mode
            )
        )
    
    def get_metadata(self) -> Metadata:
        return Metadata(
            name='OpenFeature Flipt Client-Side Provider',
        )

    def get_provider_hooks(self):
        return []
 
    def _get_entity_id(self, evaluation_context: EvaluationContext) -> str:
        return "" if not evaluation_context.targeting_key else evaluation_context.targeting_key

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext]
    ) -> FlagResolutionDetails[bool]:
        '''Resolve the boolean value of a flag from Flipt'''
        if not flag_key or not flag_key.strip():
            raise ValueError("flag_key cannot be empty or None")
       
        try:
            eval_response = self._client.evaluate_boolean(
                flag_key=flag_key,
                entity_id=self._get_entity_id(evaluation_context),
                context=evaluation_context.attributes
            )
        except Exception as e:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.ERROR,
                error_message=str(e),
                error_code=None ## Explicitly set to None. No clear mapping atm from Flipt error to OpenFeature error codes
            )
        
        return FlagResolutionDetails(
            value=eval_response.enabled,
            reason=FliptEvaluationReason(eval_response.reason).to_openfeature_reason(), ## Pass through the flipt reason str
            flag_metadata={ 
                "timestamp": eval_response.timestamp, 
                "request_duration_millis": eval_response.request_duration_millis }
        )

    def _validate_flag_type(self, flag_type: FlagType, default_value: Any):
        '''Validate the default value type against the expected flag type'''
        if flag_type == FlagType.BOOLEAN:
            assert isinstance(default_value, bool)
        elif flag_type == FlagType.STRING:
            assert isinstance(default_value, str)
        elif flag_type == FlagType.INTEGER:
            assert isinstance(default_value, int)
        elif flag_type == FlagType.FLOAT:
            assert isinstance(default_value, float)
        elif flag_type == FlagType.OBJECT:
            assert isinstance(default_value, dict) or isinstance(default_value, list)
    
    def _resolve_flag_details(
            self,
            flag_key: str,
            flag_type: FlagType,
            default_value: Any,
            evaluation_context: Optional[EvaluationContext] = None,
        ):
        ''' Resolve a variant with strict typing around return value'''
        if not flag_key or not flag_key.strip():
            raise ValueError("flag_key cannot be empty or None")

        ## Assert the default value matches the expected type
        try:
            self._validate_flag_type(flag_type, default_value)
        except AssertionError:
            raise Exception(f"Default value {default_value} does not match the expected evaluation type {flag_type}")

        try:
            eval_response = self._client.evaluate_variant(
                flag_key=flag_key,
                entity_id=self._get_entity_id(evaluation_context),
                context=evaluation_context.attributes
            )
        except Exception as e:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.ERROR,
                error_message=str(e),
                error_code=None ## Explicitly set to None. No clear mapping atm from Flipt error to OpenFeature error codes
            )
        
        flag_value = eval_response.variant_attachment if flag_type == FlagType.OBJECT else eval_response.variant_key
        
        ## Assert the default value matches the expected type
        try:
            self._validate_flag_type(flag_type, flag_value)
        except AssertionError as e:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.ERROR,
                error_message=str(e),
                error_code=ErrorCode.TYPE_MISMATCH 
            )
          
        
        return FlagResolutionDetails(
            value=flag_value,
            reason=FliptEvaluationReason(eval_response.reason).to_openfeature_reason(), ## Pass through the flipt reason str
            flag_metadata={ 
                "timestamp": eval_response.timestamp, 
                "request_duration_millis": eval_response.request_duration_millis }
        )
    
    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        self._resolve_flag_details(
            flag_key=flag_key,
            flag_type=FlagType.STRING,
            default_value=default_value,
            evaluation_context=evaluation_context,
        )

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        self._resolve_flag_details(
            flag_key=flag_key,
            flag_type=FlagType.INTEGER,
            default_value=default_value,
            evaluation_context=evaluation_context,
        )
    
    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        self._resolve_flag_details(
            flag_key=flag_key,
            flag_type=FlagType.FLOAT,
            default_value=default_value,
            evaluation_context=evaluation_context,
        )
    
    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Union[dict, list],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Union[dict, list]]:
        self._resolve_flag_details(
            flag_key=flag_key,
            flag_type=FlagType.OBJECT,
            default_value=default_value,
            evaluation_context=evaluation_context,
        )


class FliptEvaluationReason(Enum, str):
    '''Enum for the FliptClientProvider evaluation reasons'''
    FLAG_DISABLED = 'FLAG_DISABLED_EVALUATION_REASON'
    MATCH = 'MATCH_EVALUATION_REASON'
    DEFAULT = 'DEFAULT_EVALUATION_REASON'
    UNKNOWN = 'UNKNOWN_EVALUATION_REASON'

    @staticmethod
    def from_str(reason: str) -> Union['FliptEvaluationReason', str]:
        '''Convert a Flipt reason string to a FliptEvaluationReason enum'''
        try:
            return FliptEvaluationReason(reason)
        except ValueError:
            return reason

    def to_openfeature_reason(self) -> Union[Reason, str]:
        '''Convert the FliptEvaluationReason to an OpenFeature Reason'''
        if self == FliptEvaluationReason.FLAG_DISABLED:
            return Reason.DISABLED
        elif self == FliptEvaluationReason.MATCH:
            return Reason.TARGETING_MATCH
        elif self == FliptEvaluationReason.DEFAULT:
            return Reason.DEFAULT
        elif self == FliptEvaluationReason.UNKNOWN:
            return Reason.UNKNOWN
        else:
            return str


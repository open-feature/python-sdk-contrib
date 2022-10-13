import os
import pytest
from open_feature.flag_evaluation.error_code import ErrorCode

from openfeature_flagsmith.exceptions import FlagsmithConfigurationError
from openfeature_flagsmith.provider import FlagsmithProvider


def test_should_fail_to_configure_flagsmith_with_no_environment_key():
    # Given
    # When
    with pytest.raises(FlagsmithConfigurationError) as fge:
        FlagsmithProvider()

    # Then
    assert fge.error_code == ErrorCode.PROVIDER_NOT_READY
    assert fge.error_message == "No environment key set for Flagsmith"


def test_should_fail_to_configure_flagsmith():
    # Given
    # When
    FlagsmithProvider()
    # Then


def test_should_succeed_configuring_flagsmith():
    # Given
    # When
    FlagsmithProvider()
    # Then

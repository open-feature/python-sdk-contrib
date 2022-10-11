class FlagsmithConfigurationError(OpenFeatureError):
    """
    This exception should be raised when the Flagsmith provider has not been set up correctly
    """

    def __init__(self, error_message: str = None):
        """
        Constructor for the FlagsmithConfigurationError.  The error code for
        this type of exception is ErrorCode.PROVIDER_NOT_READY.
        @param error_message: a string message representing why the error has been
        raised
        @return: a FlagsmithConfigurationError exception
        """
        super().__init__(error_message, ErrorCode.PROVIDER_NOT_READY)

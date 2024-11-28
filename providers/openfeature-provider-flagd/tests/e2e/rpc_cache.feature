Feature: Flag evaluation with Caching

# This test suite contains scenarios to test the flag evaluation API.

  Background:
    Given a provider is registered

  Scenario: Resolves boolean details with caching
    When a boolean flag with key "boolean-flag" is evaluated with details and default value "false"
    Then the resolved boolean details value should be "true", the variant should be "on", and the reason should be "STATIC"
    Then the resolved boolean details value should be "true", the variant should be "on", and the reason should be "CACHED"

  Scenario: Resolves string details with caching
    When a string flag with key "string-flag" is evaluated with details and default value "bye"
    Then the resolved string details value should be "hi", the variant should be "greeting", and the reason should be "STATIC"
    Then the resolved string details value should be "hi", the variant should be "greeting", and the reason should be "CACHED"

  Scenario: Resolves integer details with caching
    When an integer flag with key "integer-flag" is evaluated with details and default value 1
    Then the resolved integer details value should be 10, the variant should be "ten", and the reason should be "STATIC"
    Then the resolved integer details value should be 10, the variant should be "ten", and the reason should be "CACHED"

  Scenario: Resolves float details with caching
    When a float flag with key "float-flag" is evaluated with details and default value 0.1
    Then the resolved float details value should be 0.5, the variant should be "half", and the reason should be "STATIC"
    Then the resolved float details value should be 0.5, the variant should be "half", and the reason should be "CACHED"

  Scenario: Resolves object details with caching
    When an object flag with key "object-flag" is evaluated with details and a null default value
    Then the resolved object details value should be contain fields "showImages", "title", and "imagesPerPage", with values "true", "Check out these pics!" and 100, respectively
    And the variant should be "template", and the reason should be "STATIC"
    Then the resolved object details value should be contain fields "showImages", "title", and "imagesPerPage", with values "true", "Check out these pics!" and 100, respectively
    And the variant should be "template", and the reason should be "CACHED"

  Scenario: Flag change event with caching
    When a string flag with key "changing-flag" is evaluated with details
    When a PROVIDER_CONFIGURATION_CHANGED handler is added
    And a flag with key "changing-flag" is modified
    Then the returned reason should be "STATIC"
    Then the returned reason should be "CACHED"
    Then the PROVIDER_CONFIGURATION_CHANGED handler must run
    And the event details must indicate "changing-flag" was altered
    Then the returned reason should be "STATIC"
    Then the returned reason should be "CACHED"
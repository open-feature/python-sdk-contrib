Feature: Evaluator error handling

  # Validates that the evaluator returns the correct error codes for
  # well-known error conditions: FLAG_NOT_FOUND and TYPE_MISMATCH.
  # Flags are configured in evaluator/flags/testkit-flags.json.

  Background:
    Given an evaluator

  Scenario: Flag not found
    Given a String-flag with key "missing-flag" and a fallback value "uh-oh"
    When the flag was evaluated with details
    Then the error-code should be "FLAG_NOT_FOUND"

  Scenario: Type mismatch
    Given a Integer-flag with key "wrong-flag" and a fallback value "13"
    When the flag was evaluated with details
    Then the error-code should be "TYPE_MISMATCH"

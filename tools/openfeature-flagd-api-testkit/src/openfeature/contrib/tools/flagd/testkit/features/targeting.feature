@targeting
Feature: Evaluator targeting

  # Tests context-based targeting rules including targeting key evaluation.

  Scenario Outline: Targeting by targeting key
    Given an evaluator
    And a String-flag with key "targeting-key-flag" and a fallback value "fallback"
    And a context containing a targeting key with value "<targeting_key>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"
    And the reason should be "<reason>"

    Examples:
      | targeting_key                        | value | reason          |
      | 5c3d8535-f81a-4478-a6d3-afaa4d51199e | hit   | TARGETING_MATCH |
      | f20bd32d-703b-48b6-bc8e-79d53c85134a | miss  | DEFAULT         |

@no-default-variant
Feature: Evaluator no-default-variant handling

  # Validates correct behavior when a flag's defaultVariant is null or undefined.
  # In such cases the evaluator falls back to the code-default supplied by the caller.
  # Flags are configured in evaluator/flags/testkit-flags.json.

  Scenario Outline: Resolve flag with no default variant
    Given an evaluator
    And a <type>-flag with key "<key>" and a fallback value "<code_default>"
    And a context containing a key "email", with type "String" and with value "<email>"
    When the flag was evaluated with details
    Then the resolved details value should be "<resolved_value>"
    And the reason should be "<reason>"

    Examples:
      | key                                         | type    | email              | code_default | resolved_value | reason          |
      | null-default-flag                           | Boolean |                    | true         | true           | DEFAULT         |
      | null-default-flag                           | Boolean |                    | false        | false          | DEFAULT         |
      | undefined-default-flag                      | Integer |                    | 100          | 100            | DEFAULT         |
      | no-default-flag-null-targeting-variant      | String  | wozniak@orange.com | Inventor     | Inventor       | DEFAULT         |
      | no-default-flag-null-targeting-variant      | String  | jobs@orange.com    | CEO          | CEO            | TARGETING_MATCH |
      | no-default-flag-undefined-targeting-variant | String  | wozniak@orange.com | Retired      | Retired        | DEFAULT         |

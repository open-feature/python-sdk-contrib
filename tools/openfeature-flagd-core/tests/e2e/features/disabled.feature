@disabled
Feature: Disabled flag evaluation

  # A flag with state=DISABLED resolves with reason=DISABLED and no value or
  # variant; the SDK returns the caller's code default.
  # Relates to: https://github.com/open-feature/flagd/issues/1965

  Scenario Outline: Evaluating a disabled flag returns reason DISABLED and code default
    Given an evaluator
    And a <type>-flag with key "<key>" and a fallback value "<default>"
    When the flag was evaluated with details
    Then the resolved details value should be "<default>"
    And the reason should be "DISABLED"

    Examples:
      | key                   | type    | default |
      | disabled-boolean-flag | Boolean | false   |
      | disabled-string-flag  | String  | bye     |
      | disabled-integer-flag | Integer | 1       |
      | disabled-float-flag   | Float   | 0.1     |
      | disabled-object-flag  | Object  | {}      |

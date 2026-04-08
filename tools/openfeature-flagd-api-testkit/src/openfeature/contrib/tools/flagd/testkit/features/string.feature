@string
Feature: Evaluator string comparison operator

  # Tests the starts_with and ends_with custom operators.

  Scenario Outline: Substring operators
    Given an evaluator
    And a String-flag with key "starts-ends-flag" and a fallback value "fallback"
    And a context containing a key "id", with type "String" and with value "<id>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"

    Examples:
      | id     | value   |
      | abcdef | prefix  |
      | uvwxyz | postfix |
      | abcxyz | prefix  |
      | lmnopq | none    |

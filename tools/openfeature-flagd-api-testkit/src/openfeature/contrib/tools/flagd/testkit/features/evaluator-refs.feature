Feature: Evaluator evaluator refs

  # Tests that $ref shared targeting rules work correctly.

  Scenario Outline: Evaluator reuse via $ref
    Given an evaluator
    And a String-flag with key "<key>" and a fallback value "fallback"
    And a context containing a key "email", with type "String" and with value "ballmer@macrosoft.com"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"

    Examples:
      | key                            | value |
      | some-email-targeted-flag       | hi    |
      | some-other-email-targeted-flag | yes   |

@semver
Feature: Evaluator semantic version operator

  # Tests the sem_ver custom operator for semantic version comparisons.

  Background:
    Given an evaluator

  Scenario Outline: Numeric comparison
    Given a String-flag with key "equal-greater-lesser-version-flag" and a fallback value "fallback"
    And a context containing a key "version", with type "String" and with value "<version>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"

    Examples:
      | version     | value   |
      | 2.0.0       | equal   |
      | 2.1.0       | greater |
      | 1.9.0       | lesser  |
      | 2.0.0-alpha | lesser  |
      | 2.0.0.0     | none    |

  Scenario Outline: Semantic comparison (minor/major range)
    Given a String-flag with key "major-minor-version-flag" and a fallback value "fallback"
    And a context containing a key "version", with type "String" and with value "<version>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"

    Examples:
      | version | value |
      | 3.0.1   | minor |
      | 3.1.0   | major |
      | 4.0.0   | none  |

  @operator-errors
  Scenario Outline: sem_ver returns null for invalid input and falls back to default variant
    Given an evaluator
    And a String-flag with key "<key>" and a fallback value "wrong"
    And a context containing a key "version", with type "String" and with value "<context_value>"
    When the flag was evaluated with details
    Then the resolved details value should be "fallback"
    Examples:
      | key                          | context_value |
      | semver-invalid-version-flag  | not-a-version |
      | semver-invalid-operator-flag | 1.0.0         |

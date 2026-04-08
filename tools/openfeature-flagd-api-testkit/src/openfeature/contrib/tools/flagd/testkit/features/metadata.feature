@metadata
Feature: Evaluator flag metadata

  # This test suite validates metadata handling in the Evaluator interface.
  # It is associated with the flags configured in evaluator/flags/testkit-flags.json.

  Background:
    Given an evaluator

  Scenario: Returns flag metadata
    Given a Boolean-flag with key "metadata-flag" and a fallback value "false"
    When the flag was evaluated with details
    Then the resolved metadata should contain
      | key     | metadata_type | value |
      | string  | String        | 1.0.2 |
      | integer | Integer       | 2     |
      | float   | Float         | 0.1   |
      | boolean | Boolean       | true  |

  Scenario Outline: Returns no metadata for flags without metadata
    Given a <flag_type>-flag with key "<key>" and a fallback value "<default_value>"
    When the flag was evaluated with details
    Then the resolved metadata is empty

    Examples:
      | key          | flag_type | default_value |
      | boolean-flag | Boolean   | true          |
      | integer-flag | Integer   | 23            |
      | float-flag   | Float     | 2.3           |
      | string-flag  | String    | value         |

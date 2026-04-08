Feature: Evaluator zero value resolution

  # Validates that zero/falsy/empty values are correctly resolved,
  # both in static flags and when selected via targeting rules.
  # Flags are configured in evaluator/flags/testkit-flags.json.

  Background:
    Given an evaluator

  Scenario Outline: Resolve zero values statically
    Given a <type>-flag with key "<key>" and a fallback value "<default>"
    When the flag was evaluated with details
    Then the resolved details value should be "<resolved_value>"
    And the reason should be "STATIC"

    Examples: Boolean evaluations
      | key               | type    | default | resolved_value |
      | boolean-zero-flag | Boolean | true    | false          |

    Examples: String evaluations
      | key              | type   | default | resolved_value |
      | string-zero-flag | String | hi      |                |

    Examples: Number evaluations
      | key               | type    | default | resolved_value |
      | integer-zero-flag | Integer | 1       | 0              |
      | float-zero-flag   | Float   | 0.1     | 0.0            |

    Examples: Object evaluations
      | key              | type   | default     | resolved_value |
      | object-zero-flag | Object | {\"a\": 1} | {}             |

  @targeting
  Scenario Outline: Resolve zero value with targeting match
    Given a <type>-flag with key "<key>" and a fallback value "<default>"
    And a context containing a key "email", with type "String" and with value "ballmer@macrosoft.com"
    When the flag was evaluated with details
    Then the resolved details value should be "<resolved_value>"
    And the reason should be "TARGETING_MATCH"

    Examples: Boolean evaluations
      | key                        | type    | default | resolved_value |
      | boolean-targeted-zero-flag | Boolean | true    | false          |

    Examples: String evaluations
      | key                       | type   | default | resolved_value |
      | string-targeted-zero-flag | String | hi      |                |

    Examples: Number evaluations
      | key                        | type    | default | resolved_value |
      | integer-targeted-zero-flag | Integer | 1       | 0              |
      | float-targeted-zero-flag   | Float   | 0.1     | 0.0            |

  @targeting
  Scenario Outline: Resolve zero value using default when targeting does not match
    Given a <type>-flag with key "<key>" and a fallback value "<default>"
    And a context containing a key "email", with type "String" and with value "ballmer@none.com"
    When the flag was evaluated with details
    Then the resolved details value should be "<resolved_value>"
    And the reason should be "DEFAULT"

    Examples: Boolean evaluations
      | key                        | type    | default | resolved_value |
      | boolean-targeted-zero-flag | Boolean | true    | false          |

    Examples: String evaluations
      | key                       | type   | default | resolved_value |
      | string-targeted-zero-flag | String | hi      |                |

    Examples: Number evaluations
      | key                        | type    | default | resolved_value |
      | integer-targeted-zero-flag | Integer | 1       | 0              |
      | float-targeted-zero-flag   | Float   | 0.1     | 0.0            |

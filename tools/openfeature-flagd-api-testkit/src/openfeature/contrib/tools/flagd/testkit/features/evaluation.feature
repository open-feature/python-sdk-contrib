Feature: Evaluator basic flag evaluation

  # Validates basic static flag resolution for all supported types.
  # Flags are configured in evaluator/flags/testkit-flags.json.

  Scenario Outline: Resolve basic values
    Given an evaluator
    And a <type>-flag with key "<key>" and a fallback value "<default>"
    When the flag was evaluated with details
    Then the resolved details value should be "<resolved_value>"

    Examples: Boolean evaluations
      | key          | type    | default | resolved_value |
      | boolean-flag | Boolean | false   | true           |

    Examples: String evaluations
      | key         | type   | default | resolved_value |
      | string-flag | String | bye     | hi             |

    Examples: Number evaluations
      | key          | type    | default | resolved_value |
      | integer-flag | Integer | 1       | 10             |
      | float-flag   | Float   | 0.1     | 0.5            |

    Examples: Object evaluations
      | key         | type   | default | resolved_value                                                                     |
      | object-flag | Object | {}      | {\"showImages\": true,\"title\": \"Check out these pics!\",\"imagesPerPage\": 100} |

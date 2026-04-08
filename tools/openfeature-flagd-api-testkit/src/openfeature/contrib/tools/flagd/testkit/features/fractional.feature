@fractional
Feature: Evaluator fractional operator

  # Tests the fractional bucketing operator for consistent user assignment.
  # @fractional-v1: legacy float-based bucketing (abs(hash) / i32::MAX * 100)
  # @fractional-v2: high-precision integer bucketing ((hash * totalWeight) >> 32)

  Background:
    Given an evaluator

  Scenario Outline: Fractional operator
    Given a String-flag with key "fractional-flag" and a fallback value "fallback"
    And a context containing a nested property with outer key "user" and inner key "name", with value "<name>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"

    @fractional-v1
    Examples: v1
      | name  | value    |
      | jack  | spades   |
      | queen | clubs    |
      | ten   | diamonds |
      | nine  | hearts   |
      | 3     | diamonds |

    @fractional-v2
    Examples: v2
      | name  | value    |
      | jack  | hearts   |
      | queen | spades   |
      | ten   | clubs    |
      | nine  | diamonds |
      | 3     | clubs    |

  Scenario Outline: Fractional operator shorthand
    Given a String-flag with key "fractional-flag-shorthand" and a fallback value "fallback"
    And a context containing a targeting key with value "<targeting_key>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"

    @fractional-v1
    Examples: v1
      | targeting_key    | value |
      | jon@company.com  | heads |
      | jane@company.com | tails |

    @fractional-v2
    Examples: v2
      | targeting_key    | value |
      | jon@company.com  | heads |
      | jane@company.com | tails |

  Scenario Outline: Fractional operator with shared seed
    Given a String-flag with key "fractional-flag-A-shared-seed" and a fallback value "fallback"
    And a context containing a nested property with outer key "user" and inner key "name", with value "<name>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"

    @fractional-v1
    Examples: v1
      | name  | value    |
      | jack  | hearts   |
      | queen | spades   |
      | ten   | hearts   |
      | nine  | diamonds |

    @fractional-v2
    Examples: v2
      | name  | value    |
      | seven | hearts   |
      | eight | diamonds |
      | nine  | clubs    |
      | two   | spades   |

  Scenario Outline: Second fractional operator with shared seed
    Given a String-flag with key "fractional-flag-B-shared-seed" and a fallback value "fallback"
    And a context containing a nested property with outer key "user" and inner key "name", with value "<name>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"

    @fractional-v1
    Examples: v1
      | name  | value           |
      | jack  | ace-of-hearts   |
      | queen | ace-of-spades   |
      | ten   | ace-of-hearts   |
      | nine  | ace-of-diamonds |

    @fractional-v2
    Examples: v2
      | name  | value           |
      | seven | ace-of-hearts   |
      | eight | ace-of-diamonds |
      | nine  | ace-of-clubs    |
      | two   | ace-of-spades   |

  # Hash edge-case vectors — keys chosen by brute-force search so their
  # MurmurHash3-x86-32 (seed=0) falls at the six critical boundary values.
  @fractional-v2
  Scenario Outline: Fractional operator hash edge cases
    Given a String-flag with key "fractional-hash-edge-flag" and a fallback value "fallback"
    And a context containing a targeting key with value "<key>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"

    Examples:
      | key    | value |
      | ejOoVL | lower |
      | bY9fO- | lower |
      | SI7p-  | lower |
      | 6LvT0  | upper |
      | ceQdGm | upper |

  # Nested JSON Logic expressions as bucket variant names / weights.
  # Requires evaluator implementations to support the @fractional-nested feature.
  # Use -t "not @fractional-nested" to exclude during transition.

  @fractional-nested
  Scenario Outline: Fractional operator with nested if expression as variant name
    # bucket0=[if(tier=="premium","premium","standard"),50], bucket1=["standard",50]
    # jon@company.com bv(100)=36 → bucket0; user1 bv(100)=76 → bucket1
    Given an evaluator
    And a String-flag with key "fractional-nested-if-flag" and a fallback value "fallback"
    And a context containing a targeting key with value "<targetingKey>"
    And a context containing a key "tier", with type "String" and with value "<tier>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"
    Examples:
      | targetingKey    | tier    | value    |
      | jon@company.com | premium | premium  |
      | jon@company.com | basic   | standard |
      | user1           | premium | standard |
      | user1           | basic   | standard |

  @fractional-nested
  Scenario Outline: Fractional operator with nested var expression as variant name
    # bucket0=[var("color"),50], bucket1=["blue",50]
    # jon@company.com bv(100)=36 → bucket0 (resolves var "color"); user1 bv(100)=76 → bucket1 ("blue")
    Given an evaluator
    And a String-flag with key "fractional-nested-var-flag" and a fallback value "fallback"
    And a context containing a targeting key with value "<targetingKey>"
    And a context containing a key "color", with type "String" and with value "<color>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"
    Examples:
      | targetingKey    | color  | value    |
      | jon@company.com | red    | red      |
      | jon@company.com | green  | green    |
      | user1           | red    | blue     |
      | jon@company.com | yellow | fallback |
      | jon@company.com |        | fallback |

  @fractional-nested
  Scenario Outline: Fractional operator with nested if expression as weight
    # bucket0=["red",if(tier=="premium",100,0)], bucket1=["blue",10]
    Given an evaluator
    And a String-flag with key "fractional-nested-weight-flag" and a fallback value "fallback"
    And a context containing a targeting key with value "<targetingKey>"
    And a context containing a key "tier", with type "String" and with value "<tier>"
    When the flag was evaluated with details
    Then the resolved details value should be "<value>"
    Examples:
      | targetingKey    | tier    | value |
      | jon@company.com | premium | red   |
      | jon@company.com | basic   | blue  |
      | user1           | premium | red   |
      | user1           | basic   | blue  |

  @fractional-nested
  Scenario: Fractional as condition
    Given an evaluator
    And a String-flag with key "fractional-as-condition-flag" and a fallback value "zero"
    And a context containing a targeting key with value "some-targeting-key"
    When the flag was evaluated with details
    Then the resolved details value should be "hundreds"

  @fractional-nested
  Scenario: Fractional as condition evaluates false path
    Given an evaluator
    And a String-flag with key "fractional-as-condition-false-flag" and a fallback value "zero"
    And a context containing a targeting key with value "some-targeting-key"
    When the flag was evaluated with details
    Then the resolved details value should be "ones"

  @operator-errors
  Scenario: fractional operator with missing bucket key falls back to default variant
    Given an evaluator
    And a String-flag with key "fractional-null-bucket-key-flag" and a fallback value "wrong"
    When the flag was evaluated with details
    Then the resolved details value should be "fallback"

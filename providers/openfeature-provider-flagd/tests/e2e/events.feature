Feature: flagd providers

  # This test suite contains scenarios to test flagd providers.
  # It's associated with the flags configured in flags/changing-flag.json and flags/zero-flags.json.
  # It should be used in conjunction with the suites supplied by the OpenFeature specification.

  Background:
    Given a flagd provider is set

  # events
  Scenario Outline: Provider events
    When a <event> handler is added
    Then the <event> handler must run
    Examples:
      | event                          |
      | PROVIDER_ERROR                 |
      | PROVIDER_STALE                 |
      | PROVIDER_READY                 |

  # events
  Scenario: Provider events chain ready -> stale -> error -> ready
    When a PROVIDER_READY handler is added
    Then the PROVIDER_READY handler must run
    When a PROVIDER_STALE handler is added
    Then the PROVIDER_STALE handler must run
    When a PROVIDER_ERROR handler is added
    Then the PROVIDER_ERROR handler must run
    When a PROVIDER_READY handler is added
    Then the PROVIDER_READY handler must run

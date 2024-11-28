Feature: Configuration Test

  @rpc @in-process
  Scenario Outline: Default Config
    When we initialize a config
    Then the option "<option>" of type "<type>" should have the value "<default>"
    Examples: Basic
      | option       | type         | default   |
      | resolverType | ResolverType | rpc       |
      | host         | String       | localhost |
      | port         | Integer      | 8013      |
      | tls          | Boolean      | false     |
      | deadline     | Integer      | 500       |
    @customCert
    Examples: Certificates
      | option   | type   | default |
      | certPath | String | null    |
    @unixsocket
    Examples: Unixsocket
      | option     | type   | default |
      | socketPath | String | null    |
    @events
    Examples: Events
      | option           | type    | default |
      | streamDeadlineMs | Integer | 600000  |
      | keepAlive        | Long    | 0       |
      | retryBackoffMs   | Integer | 1000    |
    @sync
    Examples: Sync
      | option           | type    | default |
      | streamDeadlineMs | Integer | 600000  |
      | keepAlive        | Long    | 0       |
      | retryBackoffMs   | Integer | 1000    |
      | selector         | String  | null    |
    @caching
    Examples: caching
      | option       | type      | default |
      | cacheType    | CacheType | lru     |
      | maxCacheSize | Integer   | 1000    |
    @offline
    Examples: offline
      | option                | type   | default |
      | offlineFlagSourcePath | String | null    |

  @rpc
  Scenario Outline: Default Config RPC
    When we initialize a config for "rpc"
    Then the option "<option>" of type "<type>" should have the value "<default>"
    Examples:
      | option | type    | default |
      | port   | Integer | 8013    |

  @in-process
  Scenario Outline: Default Config In-Process
    When we initialize a config for "in-process"
    Then the option "<option>" of type "<type>" should have the value "<default>"
    Examples:
      | option | type    | default |
      | port   | Integer | 8015    |

  Scenario Outline: Dedicated Config
    When we have an option "<option>" of type "<type>" with value "<value>"
    And we initialize a config
    Then the option "<option>" of type "<type>" should have the value "<value>"
    Examples:
      | option       | type         | value      |
      | resolverType | ResolverType | in-process |
      | host         | String       | local      |
      | tls          | Boolean      | True       |
      | port         | Integer      | 1234       |
      | deadline     | Integer      | 123        |
    @customCert
    Examples:
      | option   | type   | value |
      | certPath | String | path  |
    @unixsocket
    Examples:
      | option     | type   | value |
      | socketPath | String | path  |
    @events
    Examples:
      | option           | type    | value  |
      | streamDeadlineMs | Integer | 500000 |
      | keepAlive        | Long    | 5      |
      | retryBackoffMs   | Integer | 5000   |
    @sync
    Examples:
      | option           | type    | value    |
      | streamDeadlineMs | Integer | 500000   |
      | keepAlive        | Long    | 5        |
      | retryBackoffMs   | Integer | 5000     |
      | selector         | String  | selector |
    @caching
    Examples:
      | option       | type      | value    |
      | cacheType    | CacheType | disabled |
      | maxCacheSize | Integer   | 1236     |
    @offline
    Examples:
      | option                | type   | value |
      | offlineFlagSourcePath | String | path  |

  Scenario Outline: Dedicated Config via Env_var
    When we have an environment variable "<env>" with value "<value>"
    And we initialize a config
    Then the option "<option>" of type "<type>" should have the value "<value>"
    Examples:
      | option       | env               | type         | value      |
      | resolverType | FLAGD_RESOLVER    | ResolverType | in-process |
      | resolverType | FLAGD_RESOLVER    | ResolverType | IN-PROCESS |
      | resolverType | FLAGD_RESOLVER    | ResolverType | rpc        |
      | resolverType | FLAGD_RESOLVER    | ResolverType | RPC        |
      | host         | FLAGD_HOST        | String       | local      |
      | tls          | FLAGD_TLS         | Boolean      | True       |
      | port         | FLAGD_PORT        | Integer      | 1234       |
      | deadline     | FLAGD_DEADLINE_MS | Integer      | 123        |
    @customCert
    Examples:
      | option   | env                    | type   | value |
      | certPath | FLAGD_SERVER_CERT_PATH | String | path  |
    @unixsocket
    Examples:
      | option     | env               | type   | value |
      | socketPath | FLAGD_SOCKET_PATH | String | path  |
    @events
    Examples:
      | option           | env                      | type    | value  |
      | streamDeadlineMs | FLAGD_STREAM_DEADLINE_MS | Integer | 500000 |
      | keepAlive        | FLAGD_KEEP_ALIVE_TIME_MS | Long    | 5      |
      | retryBackoffMs   | FLAGD_RETRY_BACKOFF_MS   | Integer | 5000   |
    @sync
    Examples:
      | option           | env                      | type    | value    |
      | streamDeadlineMs | FLAGD_STREAM_DEADLINE_MS | Integer | 500000   |
      | keepAlive        | FLAGD_KEEP_ALIVE_TIME_MS | Long    | 5        |
      | retryBackoffMs   | FLAGD_RETRY_BACKOFF_MS   | Integer | 5000     |
      | selector         | FLAGD_SOURCE_SELECTOR    | String  | selector |
    @caching
    Examples:
      | option       | env                  | type      | value    |
      | cacheType    | FLAGD_CACHE          | CacheType | disabled |
      | maxCacheSize | FLAGD_MAX_CACHE_SIZE | Integer   | 1236     |
    @offline
    Examples:
      | option                | env                            | type   | value |
      | offlineFlagSourcePath | FLAGD_OFFLINE_FLAG_SOURCE_PATH | String | path  |

  Scenario Outline: Dedicated Config via Env_var and set
    When we have an environment variable "<env>" with value "<env-value>"
    And we have an option "<option>" of type "<type>" with value "<value>"
    And we initialize a config
    Then the option "<option>" of type "<type>" should have the value "<value>"
    Examples:
      | option       | env               | type         | value      | env-value |
      | resolverType | FLAGD_RESOLVER    | ResolverType | in-process | rpc       |
      | host         | FLAGD_HOST        | String       | local      | l         |
      | tls          | FLAGD_TLS         | Boolean      | True       | False     |
      | port         | FLAGD_PORT        | Integer      | 1234       | 3456      |
      | deadline     | FLAGD_DEADLINE_MS | Integer      | 123        | 345       |
    @customCert
    Examples:
      | option   | env                    | type   | value | env-value |
      | certPath | FLAGD_SERVER_CERT_PATH | String | path  | rpc       |
    @unixsocket
    Examples:
      | option     | env               | type   | value | env-value |
      | socketPath | FLAGD_SOCKET_PATH | String | path  | rpc       |
    @events
    Examples:
      | option           | env                      | type    | value  | env-value |
      | streamDeadlineMs | FLAGD_STREAM_DEADLINE_MS | Integer | 500000 | 400       |
      | keepAlive        | FLAGD_KEEP_ALIVE_TIME_MS | Long    | 5      | 4         |
      | retryBackoffMs   | FLAGD_RETRY_BACKOFF_MS   | Integer | 5000   | 400       |
    @sync
    Examples:
      | option           | env                      | type    | value  | env-value |
      | streamDeadlineMs | FLAGD_STREAM_DEADLINE_MS | Integer | 500000 | 400       |
      | keepAlive        | FLAGD_KEEP_ALIVE_TIME_MS | Long    | 5      | 4         |
      | retryBackoffMs   | FLAGD_RETRY_BACKOFF_MS   | Integer | 5000   | 400       |
      | selector | FLAGD_SOURCE_SELECTOR | String | selector | sele      |
    @caching
    Examples:
      | option       | env                  | type      | value    | env-value |
      | cacheType    | FLAGD_CACHE          | CacheType | disabled | lru       |
      | maxCacheSize | FLAGD_MAX_CACHE_SIZE | Integer   | 1236     | 2345      |
    @offline
    Examples:
      | option                | env                            | type   | value | env-value |
      | offlineFlagSourcePath | FLAGD_OFFLINE_FLAG_SOURCE_PATH | String | path  | lll       |

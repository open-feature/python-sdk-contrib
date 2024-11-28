# flagd Provider for OpenFeature

This provider is designed to use flagd's [evaluation protocol](https://github.com/open-feature/schemas/blob/main/protobuf/schema/v1/schema.proto).

## Installation

```
pip install openfeature-provider-flagd
```

## Configuration and Usage

The flagd provider can operate in two modes: [RPC](#remote-resolver-rpc) (evaluation takes place in flagd, via gRPC calls) or [in-process](#in-process-resolver) (evaluation takes place in-process, with the provider getting a ruleset from a compliant sync-source).

### Remote resolver (RPC)

This is the default mode of operation of the provider.
In this mode, `FlagdProvider` communicates with [flagd](https://github.com/open-feature/flagd) via the gRPC protocol.
Flag evaluations take place remotely at the connected flagd instance.

Instantiate a new FlagdProvider instance and configure the OpenFeature SDK to use it:

```python
from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

api.set_provider(FlagdProvider())
```

### In-process resolver

This mode performs flag evaluations locally (in-process).

```python
from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType

api.set_provider(FlagdProvider(
    resolver_type=ResolverType.IN_PROCESS,
    offline_flag_source_path="my-flag.json",
))
```

### Configuration options

The default options can be defined in the FlagdProvider constructor.

| Option name              | Environment variable name      | Type & Values              | Default                       | Compatible resolver |
| ------------------------ | ------------------------------ | -------------------------- | ----------------------------- | ------------------- |
| resolver_type            | FLAGD_RESOLVER                 | enum - `rpc`, `in-process` | rpc                           |                     |
| host                     | FLAGD_HOST                     | str                        | localhost                     | rpc & in-process    |
| port                     | FLAGD_PORT                     | int                        | 8013 (rpc), 8015 (in-process) | rpc & in-process    |
| tls                      | FLAGD_TLS                      | bool                       | false                         | rpc & in-process    |
| deadline                 | FLAGD_DEADLINE_MS              | int                        | 500                           | rpc & in-process    |
| stream_deadline_ms       | FLAGD_STREAM_DEADLINE_MS       | int                        | 600000                        | rpc & in-process    |
| keep_alive_time          | FLAGD_KEEP_ALIVE_TIME_MS       | int                        | 0                             | rpc & in-process    |
| selector                 | FLAGD_SOURCE_SELECTOR          | str                        | null                          | in-process          |
| cache_type               | FLAGD_CACHE                    | enum - `lru`, `disabled`   | lru                           | rpc                 |
| max_cache_size           | FLAGD_MAX_CACHE_SIZE           | int                        | 1000                          | rpc                 |
| retry_backoff_ms         | FLAGD_RETRY_BACKOFF_MS         | int                        | 1000                          | rpc                 |
| offline_flag_source_path | FLAGD_OFFLINE_FLAG_SOURCE_PATH | str                        | null                          | in-process          |

<!-- not implemented
| target_uri               | FLAGD_TARGET_URI               | alternative to host/port, supporting custom name resolution | string    | null                | rpc & in-process |
| socket_path              | FLAGD_SOCKET_PATH              | alternative to host port, unix socket                       | String    | null                | rpc & in-process |
| cert_path                | FLAGD_SERVER_CERT_PATH         | tls cert path                                               | String    | null                | rpc & in-process |
| max_event_stream_retries | FLAGD_MAX_EVENT_STREAM_RETRIES | int                                                         | 5         | rpc                 |
| context_enricher         | -                              | sync-metadata to evaluation context mapping function        | function  | identity function   | in-process       |
| offline_pollIntervalMs   | FLAGD_OFFLINE_POLL_MS          | poll interval for reading offlineFlagSourcePath             | int       | 5000                | in-process       |
 -->

> [!NOTE]
> Some configurations are only applicable for RPC resolver.

<!--
### Unix socket support
Unix socket communication with flagd is facilitated by usaging of the linux-native `epoll` library on `linux-x86_64`
only (ARM support is pending the release of `netty-transport-native-epoll` v5).
Unix sockets are not supported on other platforms or architectures.
-->

### Reconnection

Reconnection is supported by the underlying gRPC connections.
If the connection to flagd is lost, it will reconnect automatically.
A failure to connect will result in an [error event](https://openfeature.dev/docs/reference/concepts/events#provider_error) from the provider, though it will attempt to reconnect indefinitely.

### Deadlines

Deadlines are used to define how long the provider waits to complete initialization or flag evaluations.
They behave differently based on the resolver type.

#### Deadlines with Remote resolver (RPC)

If the remote evaluation call is not completed within this deadline, the gRPC call is terminated with the error `DEADLINE_EXCEEDED`
and the evaluation will default.

### TLS

TLS is available in situations where flagd is running on another host.

<!--
You may optionally supply an X.509 certificate in PEM format. Otherwise, the default certificate store will be used.
```java
FlagdProvider flagdProvider = new FlagdProvider(
        FlagdOptions.builder()
                .host("myflagdhost")
                .tls(true)                      // use TLS
                .certPath("etc/cert/ca.crt")    // PEM cert
                .build());
```
-->

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.

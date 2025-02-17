# flagd Provider for OpenFeature

This provider is designed to use flagd's [evaluation protocol](https://github.com/open-feature/schemas/blob/main/protobuf/schema/v1/schema.proto), or locally evaluate flags defined in a flagd [flag definition](https://github.com/open-feature/schemas/blob/main/json/flagd-definitions.json) via the OpenFeature Python SDK.

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

This mode performs flag evaluations locally (in-process). Flag configurations for evaluation are obtained via gRPC protocol using [sync protobuf schema](https://buf.build/open-feature/flagd/file/main:sync/v1/sync_service.proto) service definition.

Consider the following example to create a `FlagdProvider` with in-process evaluations,

```python
from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType

api.set_provider(FlagdProvider(
    resolver_type=ResolverType.IN_PROCESS,
))
```

In the above example, in-process handlers attempt to connect to a sync service on address `localhost:8013` to obtain [flag definitions](https://github.com/open-feature/schemas/blob/main/json/flags.json).

<!--
#### Sync-metadata

To support the injection of contextual data configured in flagd for in-process evaluation, the provider exposes a `getSyncMetadata` accessor which provides the most recent value returned by the [GetMetadata RPC](https://buf.build/open-feature/flagd/docs/main:flagd.sync.v1#flagd.sync.v1.FlagSyncService.GetMetadata).
The value is updated with every (re)connection to the sync implementation.
This can be used to enrich evaluations with such data.
If the `in-process` mode is not used, and before the provider is ready, the `getSyncMetadata` returns an empty map.
-->
### File mode

In-process resolvers can also work in an offline mode.
To enable this mode, you should provide a valid flag configuration file with the option `offlineFlagSourcePath`.

```python
from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType

api.set_provider(FlagdProvider(
    resolver_type=ResolverType.FILE,
    offline_flag_source_path="my-flag.json",
))
```

Provider will attempt to detect file changes using polling.
Polling happens at 5 second intervals and this is currently unconfigurable.
This mode is useful for local development, tests and offline applications.

### Configuration options

The default options can be defined in the FlagdProvider constructor.

| Option name              | Environment variable name      | Type & Values              | Default                       | Compatible resolver |
|--------------------------|--------------------------------|----------------------------|-------------------------------|---------------------|
| resolver_type            | FLAGD_RESOLVER                 | enum - `rpc`, `in-process` | rpc                           |                     |
| host                     | FLAGD_HOST                     | str                        | localhost                     | rpc & in-process    |
| port                     | FLAGD_PORT                     | int                        | 8013 (rpc), 8015 (in-process) | rpc & in-process    |
| tls                      | FLAGD_TLS                      | bool                       | false                         | rpc & in-process    |
| cert_path                | FLAGD_SERVER_CERT_PATH         | String                     | null                          | rpc & in-process    |
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


You may optionally supply an X.509 certificate in PEM format. Otherwise, the default certificate store will be used.

```python
from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

api.set_provider(FlagdProvider(
    tls=True,                        # use TLS
    cert_path="etc/cert/ca.crt"      # PEM cert
))
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.

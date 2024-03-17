
# OpenTelemetry Hook

The OpenTelemetry tracing hook for OpenFeature provides a [spec compliant][otel-spec] way to automatically add a feature flag evaluation to a span as a span event. Since feature flags are dynamic and affect runtime behavior, it’s important to collect relevant feature flag telemetry signals. This can be used to determine the impact a feature has on a request, enabling enhanced observability use cases, such as A/B testing or progressive feature releases.

## Installation

```
pip install openfeature-hooks-opentelemetry
```


## Usage

OpenFeature provides various ways to register hooks. The location that a hook is registered affects when the hook is run. It's recommended to register the `TracingHook` globally in most situations but it's possible to only enable the hook on specific clients. You should **never** register the `TracingHook` globally and on a client.

More information on hooks can be found in the [OpenFeature documentation][hook-concept].

### Register Globally

The `TracingHook` can be set globally. This will ensure that every flag evaluation will always create a span event, if an active span is available.

```python
from openfeature import api
from openfeature.contrib.hook.opentelemetry import TracingHook

api.add_hooks([TracingHook()])
```

### Register Per Client

The `TracingHook` can also be set on an individual client. This should only be done if it wasn't set globally and other clients shouldn't use this hook. Setting the hook on the client will ensure that every flag evaluation performed by this client will always create a span event, if an active span is available.

```python
from openfeature import api
from openfeature.contrib.hook.opentelemetry import TracingHook

client = api.get_client("my-app")
client.add_hooks([TracingHook()])
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.


[otel-spec]: https://opentelemetry.io/docs/reference/specification/trace/semantic_conventions/feature-flags/
[hook-concept]: https://openfeature.dev/docs/reference/concepts/hooks

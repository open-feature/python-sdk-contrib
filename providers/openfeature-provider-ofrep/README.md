# OFREP Provider for OpenFeature

This provider is designed to use the [OpenFeature Remote Evaluation Protocol (OFREP)](https://openfeature.dev/specification/appendix-c).

## Installation

```
pip install openfeature-provider-ofrep
```

## Configuration and Usage

Instantiate a new OFREPProvider instance and configure the OpenFeature SDK to use it:

```python
from openfeature import api
from openfeature.contrib.provider.ofrep import OFREPProvider

api.set_provider(OFREPProvider())
```

### Configuration options

<!-- TODO: add configuration options -->

## Provider conformance suite

This provider runs the [OpenFeature Provider Conformance Suite][tck] against a flagd-testbed stack
serving OFREP, in `tests/tck`. The suite owns the container stack: `tests/tck/conftest.py` declares
a Compose file and the port the provider connects to, and nothing else.

**It is excluded from the default build, and a maintainer runs it by hand before merging a change to
it.**

```
poe test-tck        # needs Docker
poe test            # everything else, which is what CI runs
```

The exclusion is a decision rather than an oversight. It needs Docker, and — the part that actually
decides it — a conformance suite reports what is true of the *stack* under test. A full run today is
**2 failed, 37 passed, 16 skipped, 1 xfailed**: both failures are canonical flags that flagd-testbed
v3.8.0 does not seed yet, and the `xfail` is the one genuine provider gap, recorded as a
`KnownDeviation` rather than hidden. A gate that has to be green cannot hold a suite whose honest
output is red, and turning the two backend gaps into `xfail`s would say the provider is at fault
where the backend is.

`tests/tck/conftest.py` and `tests/tck/test_ofrep_conformance.py` account for each one, so a
reviewer running the suite can tell a new failure from a known one.

`tests/tck/settled_control.py` is worth reading before you touch the suite: it is a named workaround
for one backend defect — flagd-testbed's `/start` returns about 40 ms before it serves the flag set,
which the control API forbids — and the specification prescribes that such a wait live in the
adoption, citing the defect, rather than in the shared harness.

[tck]: ../../tools/openfeature-tck/README.md

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.

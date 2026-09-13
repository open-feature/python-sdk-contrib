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

The exclusion lives in `pyproject.toml`: `--ignore=tests/tck` on the two tasks `build.yml` reaches,
with the reason in a comment above them. Why a conformance suite is not a required gate is
[Appendix F, "Running the suite in CI"][appendix-f], and is not restated here.

Two things that are this provider's rather than the policy's:

- **Docker is not what decides it.** The flagd package's `tests/e2e` needs Docker too and does run in
  the default build. What decides it is the run: **2 failed, 45 passed, 17 skipped, 1 xfailed** —
  both failures are canonical flags that flagd-testbed v3.8.0 does not seed yet, and the `xfail` is
  the one genuine provider gap, recorded as a `KnownDeviation` rather than hidden.
  `tests/tck/conftest.py` and `tests/tck/test_ofrep.py` account for each one, so a
  reviewer running the suite can tell a new failure from a known one.
- **The default build still collects the suite** — `poe test` and `poe test-cov` end in
  `pytest tests/tck --collect-only`, which imports every module and starts no container. An excluded
  suite that has quietly stopped importing against the harness is worse than one that runs and
  fails, and `mypy` here is configured over `src` alone, so nothing else would notice.

`tests/tck/settled_control.py` is worth reading before you touch the suite: it is a named workaround
for one backend defect — flagd-testbed's `/start` returns about 40 ms before it serves the flag set,
which the control API forbids — and the specification prescribes that such a wait live in the
adoption, citing the defect, rather than in the shared harness.

[tck]: ../../tools/openfeature-tck/README.md
[appendix-f]: https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.

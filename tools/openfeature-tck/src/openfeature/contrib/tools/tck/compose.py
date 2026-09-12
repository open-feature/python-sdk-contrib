"""The container stack, owned by the suite rather than by every adopter.

A provider that talks to a backend needs that backend running, its dynamically
mapped host ports discovered, and an :class:`~.httpcontrol.HttpControl` built
against its control API. Every adoption needs the same three things, and until
now every adoption wrote them: this package shipped the control client and left
orchestration to the adopter, so the flagd adoption alone carried a 122-line
``conftest.py`` and a 170-line ``suite.py`` of container wiring, and the next
adopter would have paid for it again.

So the suite owns the stack. **An adopter names a Compose file, says which
service and ports to expose, and supplies a factory that builds a provider from
a discovered endpoint.** Everything else -- start the stack once, discover the
mapped ports, build the control, wait until it accepts commands, tear down after
the last scenario -- happens here.

Two lines, in the adopter's ``conftest.py``::

    @pytest.fixture(scope="session")
    def compose_backend() -> ComposeBackend:
        return ComposeBackend(
            compose_file="tests/tck/docker-compose.yaml",
            backend_ports=[8013],
        )

    @pytest.fixture(scope="session")
    def tck_config(tck_backend: RunningBackend) -> TckConfig:
        return TckConfig(
            name="my-provider",
            control=tck_backend.control,
            new_provider=lambda: MyProvider(
                host=tck_backend.endpoint.host,
                port=tck_backend.endpoint.port(8013),
            ),
        )

``tck_backend`` is a session-scoped fixture this package's plugin supplies. It
is lazy, so a provider with no backend never touches it and never needs Docker
installed -- see :mod:`~.inprocess`.

**The stack starts once per suite and is never restarted.** Container
orchestrators assign host ports dynamically and cannot reliably preserve them
across a restart, so a restarted backend comes back on a different host port,
silently invalidating every provider already pointed at the old one -- and the
failure looks like a flaky provider rather than a broken test. Backend
unavailability is always simulated *inside* the running stack, through the
control API. That is also why :attr:`TckConfig.new_provider` is a factory rather
than an instance: the ports do not exist until the stack is up.

**The Compose path does not replace the manual one.** A provider with no backend
at all keeps supplying its own :class:`~.control.BackendControl` exactly as
before. Compose is an additional path, and the one nearly every provider wants.

**Do not substitute a control of your own that pokes an external backend through
a side channel.** The HTTP control API is the normative contract: another
language's suite drives the same endpoints against the same stack and must get
the same answers. See :class:`~.control.BackendControl`.

Requires the ``compose`` extra -- ``pip install 'openfeature-tck[compose]'`` --
which is what pulls in ``testcontainers``. Keeping it optional is deliberate: an
in-memory adopter should not have to install container tooling to run a suite
that never starts a container.
"""

from __future__ import annotations

import contextlib
import socket
import time
import typing
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .httpcontrol import (
    DEFAULT_CONFIGURATION,
    DEFAULT_STARTUP_TIMEOUT,
    ControlApiError,
    HttpControl,
)

__all__ = [
    "DEFAULT_BACKEND_SERVICE",
    "DEFAULT_CONTROL_PORT",
    "BackendEndpoint",
    "ComposeBackend",
    "ComposeStack",
    "RunningBackend",
    "run_compose_backend",
]

DEFAULT_BACKEND_SERVICE = "backend"
"""The Compose service name a stack is expected to host the backend under.

Fixed across every language's TCK, so the same Compose file is the whole of what
an adoption shares between two of them.
"""

DEFAULT_CONTROL_PORT = 8080
"""The container-internal port the control API is expected to listen on."""

_PORT_PROBE_TIMEOUT = 1.0
"""Seconds bounding a single TCP connect while waiting for a published port."""

_PORT_POLL_INTERVAL = 0.2


class ComposeStack(typing.Protocol):
    """The two things this module needs from a Compose stack.

    A protocol rather than ``testcontainers.compose.DockerCompose`` itself, so
    that port resolution is checkable and testable without Docker installed and
    without the optional dependency present. The real class satisfies it
    structurally.
    """

    def get_service_host(
        self, service_name: str | None = ..., port: int | None = ...
    ) -> str | None: ...

    def get_service_port(
        self, service_name: str | None = ..., port: int | None = ...
    ) -> int | None: ...


@dataclass(frozen=True)
class BackendEndpoint:
    """Where the running stack is reachable, handed to the provider factory.

    This type exists because host ports are only known *after* the stack has
    started. A Compose file under test must not pin host ports -- Docker assigns
    them dynamically -- so a provider cannot be configured until the stack is up,
    which is the whole reason :attr:`TckConfig.new_provider` is a factory.

    The mapping is stable for the lifetime of the suite: the stack is started
    once and never restarted, so a provider built from this endpoint stays valid
    for every scenario.
    """

    stack: ComposeStack
    """The running stack the addresses are resolved from."""

    backend_service: str = DEFAULT_BACKEND_SERVICE
    """The service :attr:`host` and the one-argument :meth:`port` resolve against."""

    service_ports: Mapping[str, Sequence[int]] = field(default_factory=dict)
    """Which container-internal ports each service publishes, from the declaration.

    Carried so that a host can be resolved at all. Testcontainers resolves a
    service's host *through* one of its published ports, and asked for a service
    without naming one it demands that the service publish exactly one -- so on
    a stack like flagd's, which publishes three on one service, the no-port form
    raises ``NoSuchPortExposed`` and the message blames the port rather than the
    call. Any of the service's ports answers the question, so the first declared
    one is used.
    """

    @property
    def host(self) -> str:
        """The host the backend service is reachable on.

        Not necessarily ``localhost``: with a remote Docker daemon, Docker
        Desktop on some platforms, or a rootless setup it can be an arbitrary
        address. Always use this rather than hard-coding a host.
        """
        return self.host_of(self.backend_service)

    def host_of(self, service: str) -> str:
        """The host a named service is reachable on.

        :raises ControlApiError: if the declaration names no port for that
            service, so there is nothing to resolve a host through -- and
            nothing for a provider to connect to either.
        """
        probe = next(iter(self.service_ports.get(service, ())), None)
        if probe is None:
            known = ", ".join(sorted(self.service_ports)) or "(none)"
            msg = (
                f"no port is declared for service {service!r}, so its host cannot "
                f"be resolved: a host is resolved through one of a service's "
                f"published ports. Declared services are {known}; add it to "
                f"ComposeBackend.additional_ports"
            )
            raise ControlApiError(msg)
        host = self.stack.get_service_host(service, probe)
        return host or "localhost"

    def port(self, internal_port: int, *, service: str | None = None) -> int:
        """The mapped host port for a container-internal port.

        :param internal_port: the container-internal port, as declared in
            :attr:`ComposeBackend.backend_ports` or
            :attr:`ComposeBackend.additional_ports`.
        :param service: the Compose service, defaulting to
            :attr:`backend_service`. Use it for a stack with more than one
            service -- a proxy, an edge service, a sidecar.
        :raises ControlApiError: if that port is not published by the stack,
            which means the Compose file does not list it under ``ports:``.
        """
        name = service or self.backend_service
        mapped = self.stack.get_service_port(name, internal_port)
        if mapped is None:
            msg = (
                f"the Compose stack publishes no host port for {internal_port} on "
                f"service {name!r}. A port is only published if the Compose file "
                f"lists it under that service's `ports:` -- unpinned, as a bare "
                f"container port, so Docker maps it dynamically"
            )
            raise ControlApiError(msg)
        return int(mapped)


@dataclass(frozen=True)
class ComposeBackend:
    """What an adopter declares about the stack under test.

    Everything except :attr:`compose_file` and :attr:`backend_ports` has a
    default, and the defaults are the same in every language's TCK.
    """

    compose_file: str | Path
    """Path to the Compose file describing the stack.

    Resolved relative to the package directory -- the directory ``pytest`` was
    invoked from for a normal ``poe test``, which is the same directory the
    package's ``pyproject.toml`` sits in. An absolute path is used as given.

    The stack must not pin host ports. Docker assigns them dynamically and this
    module discovers them after startup; a pinned host port makes the suite
    unrunnable in parallel and collides with whatever the developer already has
    listening.
    """

    backend_ports: Sequence[int]
    """Container-internal ports on :attr:`backend_service` that the *provider*
    connects to.

    :attr:`control_port` is handled automatically and must not be listed here.

    Declaring them is what lets the harness fail with "the Compose file does not
    publish 8013" at startup, rather than with a provider that cannot connect
    three scenarios later.
    """

    backend_service: str = DEFAULT_BACKEND_SERVICE
    """The Compose service hosting both the control API and the backend."""

    control_port: int = DEFAULT_CONTROL_PORT
    """The container-internal port of the control API."""

    additional_ports: Mapping[str, Sequence[int]] = field(default_factory=dict)
    """Extra service -> ports, for a stack with more than one service.

    Resolved through the endpoint by service name::

        endpoint.port(9212, service="proxy")
    """

    configuration: str = DEFAULT_CONFIGURATION
    """The configuration name passed to ``POST /start``.

    ``default`` is the only name every backend must support, and the one that
    serves the canonical flag set the feature files assume.
    """

    startup_timeout: float = DEFAULT_STARTUP_TIMEOUT
    """Seconds to wait for the stack and its control API to become reachable."""

    def __post_init__(self) -> None:
        # Normalised before anything is validated, so a declaration written as
        # any other iterable is checked as the tuple it becomes rather than
        # consumed by the checking.
        object.__setattr__(self, "backend_ports", tuple(self.backend_ports))
        object.__setattr__(
            self,
            "additional_ports",
            {service: tuple(ports) for service, ports in self.additional_ports.items()},
        )

        problems: list[str] = []

        if not str(self.compose_file):
            problems.append(
                "compose_file is required: it is the path to the Compose file "
                "describing the stack under test"
            )
        if not self.backend_ports:
            problems.append(
                "backend_ports is required and must not be empty: it is the "
                "container-internal ports the provider connects to, so the harness can "
                "check the Compose file publishes them before the first scenario. The "
                f"control port ({self.control_port}) is handled automatically and does "
                "not belong here"
            )
        if self.control_port in self.backend_ports:
            problems.append(
                f"backend_ports lists the control port {self.control_port}: it is "
                "exposed automatically, and a provider that connects to the control "
                "API is not exercising the contract this suite tests. Remove it, or "
                "set control_port if the control API is somewhere else"
            )
        if not self.backend_service:
            problems.append(
                "backend_service must name a Compose service: it is the service "
                "hosting both the control API and the backend"
            )
        if self.startup_timeout <= 0:
            problems.append(
                f"startup_timeout must be positive, not {self.startup_timeout!r}"
            )

        if problems:
            joined = "\n  - ".join(problems)
            msg = f"invalid ComposeBackend:\n  - {joined}"
            raise ValueError(msg)

    def resolved_compose_file(self, root: Path | None = None) -> Path:
        """The Compose file as an absolute path, resolved against ``root``.

        ``root`` defaults to the current working directory, which for a normal
        ``poe test`` is the package directory.
        """
        candidate = Path(self.compose_file)
        if not candidate.is_absolute():
            candidate = (root or Path.cwd()) / candidate
        return candidate

    @property
    def exposed_ports(self) -> dict[str, tuple[int, ...]]:
        """Every service and container-internal port the stack must publish.

        The control port first, because a stack that publishes nothing else
        still has to answer control calls, then the backend ports, then whatever
        :attr:`additional_ports` adds.
        """
        ports: dict[str, tuple[int, ...]] = {
            self.backend_service: (self.control_port, *self.backend_ports),
        }
        for service, extra in self.additional_ports.items():
            merged = (*ports.get(service, ()), *extra)
            # dict.fromkeys rather than a set: order is what makes the startup
            # failure message read in the order the adopter wrote the ports.
            ports[service] = tuple(dict.fromkeys(merged))
        return ports


@dataclass(frozen=True)
class RunningBackend:
    """The started stack, as the ``tck_backend`` fixture yields it.

    Two things, because two things are all an adoption needs: the control to
    hand to :attr:`TckConfig.control`, and the endpoint to build providers from.
    """

    control: HttpControl
    """The control API client, already awaited ready.

    One instance per stack, and it must stay that way where two suites drive the
    same backend: it remembers whether a disconnect has left the backend down,
    so the next scenario is prepared with ``/start`` rather than ``/reset``, and
    two instances would each hold half of that knowledge.
    """

    endpoint: BackendEndpoint
    """Host and mapped ports of the running stack, for the provider factory."""

    backend: ComposeBackend
    """The declaration this stack was started from."""


def run_compose_backend(
    backend: ComposeBackend, *, root: Path | None = None
) -> Iterator[RunningBackend]:
    """Start the declared stack, yield it, and tear it down.

    A generator, so the ``tck_backend`` fixture is ``yield from`` over this and
    an adopter who wants a fixture of their own naming or scoping can be too::

        @pytest.fixture(scope="session")
        def tck_backend() -> Iterator[RunningBackend]:
            yield from run_compose_backend(ComposeBackend(...))

    Startup is: bring the stack up and wait for its containers, wait for every
    declared port to accept a connection, then wait for the control API itself
    to accept commands. The last of those is a real readiness check rather than
    a pause -- see :meth:`HttpControl.await_ready`.
    """
    compose_file = backend.resolved_compose_file(root)
    if not compose_file.is_file():
        msg = (
            f"Compose file not found: {compose_file}. "
            f"ComposeBackend.compose_file is resolved relative to the package "
            f"directory, which is where pytest runs from"
        )
        raise FileNotFoundError(msg)

    stack = _docker_compose(compose_file)
    stack.start()
    try:
        endpoint = BackendEndpoint(
            stack=typing.cast("ComposeStack", stack),
            backend_service=backend.backend_service,
            service_ports=backend.exposed_ports,
        )
        _await_ports(backend, endpoint)

        control = HttpControl(
            f"http://{endpoint.host}:{endpoint.port(backend.control_port)}",
            configuration=backend.configuration,
        )
        control.await_ready(backend.startup_timeout)

        yield RunningBackend(control=control, endpoint=endpoint, backend=backend)
    finally:
        stack.stop()


def _docker_compose(compose_file: Path) -> typing.Any:
    """Build a ``DockerCompose`` for one Compose file.

    Imported here rather than at module scope so that importing this module --
    which the package's ``__init__`` does -- costs nothing and, more to the
    point, does not require ``testcontainers`` to be installed. An in-memory
    adopter has no use for container tooling and should not have to install it.
    """
    try:
        # PLC0415: deliberately not at module scope. That is the whole point of
        # this function -- see the docstring.
        from testcontainers.compose import DockerCompose  # noqa: PLC0415
    except ImportError as error:  # pragma: no cover - depends on the environment
        msg = (
            "the Compose harness needs testcontainers, which is the `compose` "
            "extra of this package: `pip install 'openfeature-tck[compose]'`. It is "
            "optional because a provider with no backend runs the whole suite "
            "without a container -- see the in-process control"
        )
        raise ImportError(msg) from error

    return DockerCompose(
        context=str(compose_file.parent),
        compose_file_name=compose_file.name,
        # `docker compose up --wait`, so start() returns once the containers are
        # up rather than once the command has been issued.
        wait=True,
    )


def _await_ports(backend: ComposeBackend, endpoint: BackendEndpoint) -> None:
    """Wait until every declared port accepts a TCP connection.

    Java's harness gets this from a Testcontainers listening-port wait strategy
    per exposed service port; ``docker compose up --wait`` only promises the
    container is up, which for a service with no healthcheck it is well before
    anything is listening. Same guarantee, established the same way, so the two
    languages fail at the same point rather than one of them failing later and
    somewhere less obvious.
    """
    deadline = time.monotonic() + backend.startup_timeout
    for service, ports in backend.exposed_ports.items():
        host = endpoint.host_of(service)
        for internal in ports:
            mapped = endpoint.port(internal, service=service)
            _await_listening(host, mapped, service, internal, deadline)


def _await_listening(
    host: str, port: int, service: str, internal: int, deadline: float
) -> None:
    last: OSError | None = None
    while True:
        try:
            with contextlib.closing(
                socket.create_connection((host, port), timeout=_PORT_PROBE_TIMEOUT)
            ):
                return
        except OSError as error:
            last = error
        if time.monotonic() >= deadline:
            msg = (
                f"nothing is listening on {host}:{port} -- the host port Compose "
                f"mapped for container port {internal} of service {service!r} -- "
                f"within the startup timeout: {last}. Either the service does not "
                f"listen on {internal}, or the stack needs a longer "
                f"ComposeBackend.startup_timeout"
            )
            raise ControlApiError(msg)
        time.sleep(_PORT_POLL_INTERVAL)

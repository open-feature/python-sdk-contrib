"""What an adopter declares about a container stack, and what the harness owes them.

The stack lifecycle itself needs Docker and is proved by the flagd adoption,
which runs the whole canonical suite against a real testbed through this
harness. What is checked here is everything that can be wrong *without* a
container, and all of it was adopter code until now: the declaration's defaults,
the refusals that turn a mistake into a message instead of a provider that
cannot connect three scenarios later, and the port resolution the provider
factory is handed.

``ComposeStack`` is a protocol rather than ``DockerCompose`` itself, which is
what makes that possible: a stub satisfying two methods stands in for Docker, so
the resolution logic is examined rather than assumed.
"""

from __future__ import annotations

import dataclasses
import typing
from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import (
    DEFAULT_BACKEND_SERVICE,
    DEFAULT_CONFIGURATION,
    DEFAULT_CONTROL_PORT,
    DEFAULT_STARTUP_TIMEOUT,
    BackendEndpoint,
    ComposeBackend,
    ControlApiError,
    run_compose_backend,
)

BACKEND_PORT = 8013
"""A container-internal port a provider connects to. flagd's RPC port, for realism."""


@dataclasses.dataclass
class _StubStack:
    """A Compose stack that publishes exactly what it is told to.

    Keyed by ``(service, container port) -> host port``, because that is the
    whole of what the harness asks a stack for -- and getting the service half
    wrong is how a multi-service stack resolves a port against the wrong
    container.
    """

    published: dict[tuple[str, int], int]
    host: str = "127.0.0.1"

    def get_service_host(
        self, service_name: str | None = None, port: int | None = None
    ) -> str | None:
        # Testcontainers resolves a host *through* a published port, and asked
        # without one it insists the service publish exactly one. Reproduced
        # rather than waved through: a stub that answered anyway is why the
        # no-port form reached a real three-port stack and raised there.
        assert service_name is not None
        if port is None:
            ports = [key for key in self.published if key[0] == service_name]
            assert len(ports) == 1, (
                f"service {service_name!r} publishes {len(ports)} ports, so the "
                f"host cannot be resolved without naming one of them"
            )
        return self.host

    def get_service_port(
        self, service_name: str | None = None, port: int | None = None
    ) -> int | None:
        assert service_name is not None
        assert port is not None
        return self.published.get((service_name, port))


def _endpoint(
    published: dict[tuple[str, int], int],
    service: str = DEFAULT_BACKEND_SERVICE,
) -> BackendEndpoint:
    """An endpoint over a stub stack, told which ports each service publishes.

    Which is what the real one is told, from the declaration: the host is
    resolved through one of them.
    """
    ports: dict[str, list[int]] = {}
    for name, internal in published:
        ports.setdefault(name, []).append(internal)
    return BackendEndpoint(
        stack=typing.cast("typing.Any", _StubStack(published=published)),
        backend_service=service,
        service_ports=ports,
    )


# -- the declaration ---------------------------------------------------------


def test_the_defaults_are_the_ones_every_language_fixes() -> None:
    """Pinned as literals, because the Compose file is what an adoption shares.

    A provider shipped in two languages writes one Compose file and two
    declarations against it, so a default that differs between two TCKs makes
    the file wrong in one of them -- and the symptom is a stack that starts and
    a control API nothing can reach. Every other assertion in this file uses the
    constants and would stay green through a change to them.
    """
    backend = ComposeBackend(compose_file="docker-compose.yaml", backend_ports=[8013])

    assert backend.backend_service == "backend"
    assert backend.control_port == 8080
    assert backend.additional_ports == {}
    assert backend.configuration == "default"
    assert backend.startup_timeout == 60.0

    assert DEFAULT_BACKEND_SERVICE == "backend"
    assert DEFAULT_CONTROL_PORT == 8080
    assert DEFAULT_CONFIGURATION == "default"
    assert DEFAULT_STARTUP_TIMEOUT == 60.0


def test_backend_ports_is_required_and_says_the_control_port_is_not_one() -> None:
    """The one refusal an adopter is most likely to meet, so it has to teach.

    An empty ``backend_ports`` is a declaration that says nothing about which
    ports the provider needs, which turns a startup check into nothing and the
    first scenario into an unexplained connection failure.
    """
    with pytest.raises(ValueError, match="backend_ports is required") as raised:
        ComposeBackend(compose_file="docker-compose.yaml", backend_ports=[])

    assert "control port (8080) is handled automatically" in str(raised.value)


def test_the_control_port_may_not_be_declared_as_a_backend_port() -> None:
    """Listing it is a sign of a misunderstanding rather than a duplicate entry.

    The control API is the harness's, not the provider's. A provider pointed at
    it is not exercising the contract this suite tests, and a declaration that
    lists it reads as though it might be.
    """
    with pytest.raises(ValueError, match="lists the control port 8080"):
        ComposeBackend(
            compose_file="docker-compose.yaml",
            backend_ports=[BACKEND_PORT, DEFAULT_CONTROL_PORT],
        )


def test_a_relocated_control_port_may_be_a_backend_port_elsewhere() -> None:
    """The check is against the declared control port, not against 8080.

    A stack serving its control API somewhere else is entitled to have 8080 be
    an ordinary backend port.
    """
    backend = ComposeBackend(
        compose_file="docker-compose.yaml",
        backend_ports=[DEFAULT_CONTROL_PORT],
        control_port=9090,
    )
    assert backend.exposed_ports == {"backend": (9090, DEFAULT_CONTROL_PORT)}


def test_a_declaration_reports_every_problem_it_has_at_once() -> None:
    """One traceback naming everything wrong, not one per round trip."""
    with pytest.raises(ValueError) as raised:
        ComposeBackend(
            compose_file="docker-compose.yaml",
            backend_ports=[],
            backend_service="",
            startup_timeout=0,
        )

    message = str(raised.value)
    assert "backend_ports is required" in message
    assert "backend_service must name a Compose service" in message
    assert "startup_timeout must be positive" in message


def test_the_declaration_is_normalised_to_tuples() -> None:
    """So a declaration written as a list is stored as what it is checked as.

    Normalised before validation rather than after, which is the order that
    matters: the control-port check reads ``backend_ports``, and reading it
    first would consume a one-shot iterable before it reached the field.
    """
    backend = ComposeBackend(
        compose_file="docker-compose.yaml",
        backend_ports=[8013, 8015],
        additional_ports={"proxy": [9212]},
    )
    assert backend.backend_ports == (8013, 8015)
    assert backend.additional_ports == {"proxy": (9212,)}


def test_the_control_port_is_exposed_ahead_of_everything_an_adopter_named() -> None:
    """It is the harness's own port and is never declared, so it is added here.

    First, because a stack that publishes nothing else still has to answer
    control calls, and the startup failure should say so before it says anything
    about a provider port.
    """
    backend = ComposeBackend(
        compose_file="docker-compose.yaml",
        backend_ports=[8013, 8015],
        additional_ports={"proxy": [9212]},
    )
    assert backend.exposed_ports == {
        "backend": (DEFAULT_CONTROL_PORT, 8013, 8015),
        "proxy": (9212,),
    }


def test_additional_ports_on_the_backend_service_join_rather_than_replace() -> None:
    """A stack may name the backend service again without losing the control port."""
    backend = ComposeBackend(
        compose_file="docker-compose.yaml",
        backend_ports=[8013],
        additional_ports={DEFAULT_BACKEND_SERVICE: [8015, 8013]},
    )
    assert backend.exposed_ports == {"backend": (DEFAULT_CONTROL_PORT, 8013, 8015)}


# -- resolving the compose file ----------------------------------------------


def test_a_relative_compose_path_resolves_against_the_package_directory(
    tmp_path: Path,
) -> None:
    """Which is where pytest runs from, so ``tests/tck/docker-compose.yaml`` works."""
    backend = ComposeBackend(
        compose_file="tests/tck/docker-compose.yaml", backend_ports=[BACKEND_PORT]
    )
    assert (
        backend.resolved_compose_file(tmp_path)
        == tmp_path / "tests/tck/docker-compose.yaml"
    )


def test_an_absolute_compose_path_is_used_as_given(tmp_path: Path) -> None:
    absolute = tmp_path / "elsewhere" / "docker-compose.yaml"
    backend = ComposeBackend(compose_file=absolute, backend_ports=[BACKEND_PORT])
    assert backend.resolved_compose_file(tmp_path / "ignored") == absolute


def test_a_missing_compose_file_fails_before_anything_is_started(
    tmp_path: Path,
) -> None:
    """And says where it looked, because the answer is usually "not where I meant".

    Raised from the generator before Docker is touched, so an adopter who
    mistyped the path does not wait for a stack to come up first -- and never
    needs Docker to find out.
    """
    backend = ComposeBackend(
        compose_file="tests/tck/docker-compose.yaml", backend_ports=[BACKEND_PORT]
    )
    with pytest.raises(FileNotFoundError) as raised:
        next(run_compose_backend(backend, root=tmp_path))

    message = str(raised.value)
    assert "docker-compose.yaml" in message
    assert "resolved relative to the package directory" in message


# -- the endpoint the provider factory is handed -----------------------------


def test_a_mapped_port_is_looked_up_by_container_port() -> None:
    """Which is what an adopter knows: 8013 is in their Compose file, 32769 is not."""
    endpoint = _endpoint({(DEFAULT_BACKEND_SERVICE, BACKEND_PORT): 32769})
    assert endpoint.port(BACKEND_PORT) == 32769


def test_a_port_may_be_qualified_by_service_for_a_multi_service_stack() -> None:
    """Two services may publish the same container port, and usually do.

    Resolving one against the other is silent: the provider connects to
    something that answers, and the scenario fails on whatever it answers with.
    """
    endpoint = _endpoint(
        {
            (DEFAULT_BACKEND_SERVICE, BACKEND_PORT): 32769,
            ("proxy", BACKEND_PORT): 32770,
        }
    )
    assert endpoint.port(BACKEND_PORT) == 32769
    assert endpoint.port(BACKEND_PORT, service="proxy") == 32770


def test_the_host_is_the_stacks_own_rather_than_localhost() -> None:
    """A remote daemon, Docker Desktop or a rootless setup can serve any address."""
    endpoint = BackendEndpoint(
        stack=typing.cast(
            "typing.Any",
            _StubStack(
                published={(DEFAULT_BACKEND_SERVICE, BACKEND_PORT): 32769},
                host="192.168.64.2",
            ),
        ),
        service_ports={DEFAULT_BACKEND_SERVICE: [BACKEND_PORT]},
    )
    assert endpoint.host == "192.168.64.2"


def test_the_host_of_a_service_publishing_several_ports_still_resolves() -> None:
    """flagd's stack publishes three on one service, which is the common shape.

    Resolved through one of the declared ports, because testcontainers resolves
    a host *through* a published port and, asked without one, requires the
    service to publish exactly one. The no-port form therefore worked on every
    single-port stack and raised ``NoSuchPortExposed`` on the first real one --
    with a message about the port rather than about the call.
    """
    endpoint = _endpoint(
        {
            (DEFAULT_BACKEND_SERVICE, DEFAULT_CONTROL_PORT): 32768,
            (DEFAULT_BACKEND_SERVICE, BACKEND_PORT): 32769,
            (DEFAULT_BACKEND_SERVICE, 8015): 32770,
        }
    )
    assert endpoint.host == "127.0.0.1"
    assert endpoint.port(8015) == 32770


def test_an_undeclared_service_says_so_rather_than_failing_inside_docker() -> None:
    """A service the declaration does not name has nothing published for it.

    So there is nothing to resolve a host through and nothing for a provider to
    connect to. Answered here, naming the services that *were* declared, rather
    than passed down to testcontainers to answer as a port problem.
    """
    endpoint = _endpoint({(DEFAULT_BACKEND_SERVICE, BACKEND_PORT): 32769})
    with pytest.raises(ControlApiError) as raised:
        endpoint.host_of("proxy")

    message = str(raised.value)
    assert "no port is declared for service 'proxy'" in message
    assert "additional_ports" in message


def test_an_unpublished_port_says_the_compose_file_has_to_list_it() -> None:
    """The error an adopter actually hits, and the fix is in the Compose file.

    Testcontainers' own answer here is a ``NoSuchPortExposed`` naming the port
    and nothing else, which reads as though the harness were at fault.
    """
    endpoint = _endpoint({(DEFAULT_BACKEND_SERVICE, DEFAULT_CONTROL_PORT): 32768})
    with pytest.raises(ControlApiError) as raised:
        endpoint.port(BACKEND_PORT)

    message = str(raised.value)
    assert f"no host port for {BACKEND_PORT}" in message
    assert "`ports:`" in message

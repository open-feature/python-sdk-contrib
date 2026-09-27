"""Generate the gRPC and protobuf modules from the flagd schemas submodule.

Used by `poe generate-protos` before the tests and the type check, and by the
hatch build hook (hatch_build.py) when a distribution is built. Generation is a
test *input*, not an artifact of the build, so it has to be runnable on its own:
requiring `uv build` to get importable code is what forced CI to build every
package on every Python version just to obtain these modules.

The .proto files are owned by open-feature/schemas and reach this package
through a git submodule, so nothing here can fork their definition. The
generated modules are gitignored and regenerated from whatever revision the
submodule pin names, which is what keeps the two from drifting apart unnoticed.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
# protoc resolves imports and package paths against this, so the generated
# modules land under src/ mirroring their path here: a .proto at
# openfeature/schemas/protobuf/flagd/sync/v1/sync.proto becomes
# src/openfeature/schemas/protobuf/flagd/sync/v1/sync_pb2.py.
PROTO_PATH = "."
OUTPUT_PATH = "src"

# (protoc generator, generated-file suffix). `python` and `grpc_python` are
# built into grpc_tools.protoc; the two mypy_* ones are separate executables that
# mypy-protobuf installs, which is why it is a dev dependency and not only a
# build-time one.
GENERATORS = [
    ("python", "_pb2.py"),
    ("grpc_python", "_pb2_grpc.py"),
    ("mypy", "_pb2.pyi"),
    ("mypy_grpc", "_pb2_grpc.pyi"),
]
EXTERNAL_PLUGINS = ("mypy", "mypy_grpc")


def find_plugin(name: str) -> str | None:
    """Locate a protoc plugin executable next to the running interpreter.

    protoc would find it on PATH, but only if the environment happens to be
    activated. Resolving it against sys.executable means the plugin that ships
    with *this* interpreter is used -- the dev environment when poe runs the
    script, the isolated build environment when the build hook does.
    """
    return shutil.which(f"protoc-gen-{name}", path=str(Path(sys.executable).parent))


def find_protos() -> list[Path]:
    """Every .proto under the package root, relative to it.

    Dot-directories are skipped so a virtualenv inside the package directory
    cannot drag site-packages' own .proto files into the generation.
    """
    return sorted(
        proto.relative_to(ROOT)
        for proto in (ROOT / PROTO_PATH).glob("**/*.proto")
        if not any(part.startswith(".") for part in proto.relative_to(ROOT).parts)
    )


def outputs_for(protos: list[Path]) -> list[Path]:
    """The files `generate` writes for those inputs, relative to the root."""
    return [
        Path(OUTPUT_PATH) / proto.parent / f"{proto.stem}{suffix}"
        for proto in protos
        for _, suffix in GENERATORS
    ]


def generate() -> list[Path]:
    """Run protoc; return what it generated, relative to the package root.

    Returns an empty list when there is no .proto to compile. That is the normal
    case when building a wheel from an sdist: the submodule is not in the sdist
    but the generated modules are, so there is nothing to do and nothing wrong.
    """
    protos = find_protos()
    if not protos:
        return []

    args = [sys.executable, "-m", "grpc_tools.protoc", "--proto_path", PROTO_PATH]
    for name, _ in GENERATORS:
        if name in EXTERNAL_PLUGINS:
            plugin = find_plugin(name)
            if plugin:
                args.append(f"--plugin=protoc-gen-{name}={plugin}")
        args.append(f"--{name}_out={OUTPUT_PATH}")
    args += [str(proto) for proto in protos]

    # Every argument is built here from the checked-in configuration above and
    # from paths found inside this package, so there is no untrusted input.
    subprocess.run(args, cwd=ROOT, check=True)  # noqa: S603
    return outputs_for(protos)


if __name__ == "__main__":
    if not generate():
        msg = (
            f"No .proto files found under {ROOT}. Make sure submodules are "
            "initialized: `git submodule update --init "
            "providers/openfeature-provider-flagd/openfeature/schemas`."
        )
        raise SystemExit(msg)

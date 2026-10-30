"""Where the scenarios come from: the canonical set, plus whatever an adopter adds.

An adopter's own scenarios run **inside** the canonical suite -- against the
same provider instance, in the same backend lifecycle, with the same step
vocabulary available. pytest collects ``conftest.py`` on its own and pytest-bdd
resolves step definitions through the fixture system, so the only thing it
cannot find by itself is the feature files, which is what this module finds: a
directory named ``extensions`` beside the adopter's test module.

That leaves one line, the same whether or not there are extensions::

    scenarios(*feature_paths())

**An extension can never stand in for a canonical scenario.** The two are told
apart by the uri each feature file is identified by, and :func:`uri_for` derives
that uri from where the file *is* rather than taking what the runner offers:
``gherkin/…`` is the packaged canonical assets and nothing else, and
``extensions/…`` is a discovered extension.

The derivation is public, and the two problems it cannot rule out --
:func:`reserved_prefix_problem` and :func:`uri_collisions` -- are reported rather
than raised, because the consumer of all of this is a conformance report and that
is not written here.
"""

from __future__ import annotations

import importlib.resources
import inspect
import re
import typing
from pathlib import Path

__all__ = [
    "CANONICAL_DIRECTORY",
    "EXTENSIONS_DIRECTORY",
    "EXTENSIONS_URI_PREFIX",
    "canonical_root",
    "canonical_tags",
    "collision_problem",
    "extension_root",
    "feature_paths",
    "is_canonical",
    "is_canonical_uri",
    "reserved_prefix_problem",
    "uri_collisions",
    "uri_for",
]

_PACKAGE = "openfeature.contrib.tools.tck"

_TAG = re.compile(r"@[\w-]+")
"""One Gherkin tag, as it appears on a tag line."""

CANONICAL_DIRECTORY = "gherkin"
"""The packaged directory the canonical feature files live in.

Also the uri prefix they are identified by, which is why it is reserved: anyone
reading ``gherkin/errors.feature`` is entitled to assume it is the
specification's file rather than a local one that happened to land in a directory
of that name.

The name is not chosen here. Appendix F fixes it: a canonical feature is
identified by its path **relative to the specification's asset directory**, and
``gherkin`` is the directory it occupies there.
"""

EXTENSIONS_DIRECTORY = "extensions"
"""Where an adopter puts feature files of their own, beside their test module.

Deliberately not the canonical name: a directory sharing it is how an extension
comes to occupy a canonical file's identity. It is also the directory Java's TCK
scans for on the classpath, so an adopter who ships a provider in both languages
puts the same directory in both repositories.
"""

EXTENSIONS_URI_PREFIX = "extensions"
"""The uri prefix an extension's scenarios are identified by.

The Go and JavaScript suites mount extensions under the same prefix, so a
consumer holding reports from several languages applies one rule to tell an
adopter's scenario from the specification's.

Equal to :data:`EXTENSIONS_DIRECTORY` today, and still a constant of its own: the
directory this suite scans and the prefix a report is keyed by are two separate
facts, and only the second is fixed by Appendix F.
"""


def _canonical_path() -> str:
    """The packaged directory holding the canonical feature files.

    Deliberately not public: a public single-directory call sits one character
    away from ``scenarios(*feature_paths())`` at the call site and silently drops
    the extensions directory, producing a green run that examined fewer scenarios
    than the adopter believes it did.

    :func:`canonical_root` is the supported way to reach the directory for
    anything that is not "the scenarios to run".
    """
    return str(importlib.resources.files(_PACKAGE) / CANONICAL_DIRECTORY)


def feature_paths() -> tuple[str, ...]:
    """Return every feature directory this adoption should run.

    The canonical set, always, and an ``extensions`` directory beside the
    calling module if there is one. Hand the result to pytest-bdd's
    ``scenarios()``::

        scenarios(*feature_paths())

    The calling module is located from the caller's frame, which is how
    pytest-bdd locates it for ``scenarios()`` itself, so the two agree about
    which module is adopting the suite. Call it from the test module rather than
    from a helper: a helper's directory is what a helper would find. A caller
    with no ``__file__`` gets the canonical set alone.
    """
    paths = [_canonical_path()]
    directory = _caller_directory()
    if directory is not None:
        extensions = extension_root(directory)
        if extensions is not None:
            paths.append(str(extensions))
    return tuple(paths)


def extension_root(module_directory: Path) -> Path | None:
    """The extension directory beside a test module, or ``None`` if there is none."""
    candidate = module_directory / EXTENSIONS_DIRECTORY
    return candidate if candidate.is_dir() else None


def canonical_root() -> Path | None:
    """The packaged canonical features directory, as a real path.

    ``None`` if the assets are not on the filesystem -- an installation from a
    zipimport, say -- so everything built on this degrades to "cannot tell".
    """
    try:
        return _resolve(Path(_canonical_path()))
    except (OSError, TypeError):  # pragma: no cover - assets outside a filesystem
        return None


def canonical_tags() -> frozenset[str]:
    """Every Gherkin tag the packaged canonical feature files carry.

    The specification's half of what a reservation is checked against. Read off
    the packaged files rather than off a collected run, so a ``-k`` or a
    ``--deselect`` cannot narrow a run past it. See
    :func:`~.capability.expired_reservations`.

    **Tag lines only**, which is what tells a tag apart from the same word
    written in prose: a canonical feature file mentions a reserved tag in a
    comment, so a scan that read the whole file would report the reservation as
    expired on the strength of a sentence about it.

    Recursive, because the shape of the canonical directory is the
    specification's to change, and a flat scan would silently under-collect.

    Empty when the assets are not reachable as files -- an installation from a
    zipimport, say -- so everything built on this degrades to "cannot tell".
    """
    root = canonical_root()
    if root is None or not root.is_dir():
        return frozenset()

    tags: set[str] = set()
    for feature in sorted(root.rglob("*.feature")):
        for line in feature.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("@"):
                tags.update(_TAG.findall(stripped))
    return frozenset(tags)


def is_canonical(path: Path) -> bool:
    """Whether a feature file is one of the packaged canonical ones."""
    canonical = canonical_root()
    return canonical is not None and _resolve(path).is_relative_to(canonical)


def is_canonical_uri(uri: str) -> bool:
    """Whether a uri names a canonical feature file.

    Derived from the uri rather than carried beside it, so there is no second
    fact to disagree with the first.
    """
    return uri.startswith(f"{CANONICAL_DIRECTORY}/")


def uri_for(path: Path) -> str | None:
    """The uri a feature file should be identified by.

    ``None`` when the file is neither canonical nor under an extension
    directory, in which case the caller falls back to what pytest-bdd named it.

    Derived from the file's location rather than from pytest-bdd's
    ``rel_filename``, which is the parent directory's name joined to the file's
    own -- and so would let ``extensions/gherkin/errors.feature`` present itself
    under a canonical file's uri.
    """
    resolved = _resolve(path)

    canonical = canonical_root()
    if canonical is not None and resolved.is_relative_to(canonical):
        return _uri(Path(CANONICAL_DIRECTORY) / resolved.relative_to(canonical))

    for parent in resolved.parents:
        if parent.name == EXTENSIONS_DIRECTORY:
            return _uri(Path(EXTENSIONS_URI_PREFIX) / resolved.relative_to(parent))
    return None


def reserved_prefix_problem(uri: str, path: Path) -> str | None:
    """Report a feature file claiming the canonical uri prefix without being canonical.

    The one thing the naming convention cannot rule out on its own: an adopter
    who hands ``scenarios()`` a directory of their own named ``gherkin``. The
    file is then named exactly as a canonical one would be.

    Returned rather than raised. The scenarios run either way and they are the
    adopter's to run, so this is for whatever writes a record of the run to
    refuse to publish one.
    """
    if not is_canonical_uri(uri) or is_canonical(path):
        return None
    return (
        f"{uri} is not a canonical feature file -- it is {path} -- but it would be "
        f"reported under the {CANONICAL_DIRECTORY}/ prefix, which is reserved for "
        f"the packaged conformance assets. Move it into a directory named "
        f"{EXTENSIONS_DIRECTORY} beside the test module, which feature_paths() "
        f"finds on its own"
    )


def uri_collisions(
    identified: typing.Iterable[tuple[str, Path]],
) -> dict[str, tuple[Path, ...]]:
    """Feature files that would share one uri, keyed by that uri.

    Deriving the uri from the file's location removes the collision an adopter is
    likely to hit but does not make one impossible: two extension roots
    contributing the same relative path to a single suite still collide, and so
    does an ``extensions`` directory nested inside another one.

    That has to be refused rather than resolved. A record of what ran holds one
    copy of a feature file per uri, so the second file is never read: its
    scenarios are attributed to the first file's where the names happen to match,
    and go missing where they do not. The first is silent, and the one a consumer
    cannot detect from the outside.

    Compared by resolved path, so the same file reached by two routes is one
    file rather than a collision.
    """
    files: dict[str, dict[Path, None]] = {}
    for uri, path in identified:
        files.setdefault(uri, {})[_resolve(path)] = None
    return {uri: tuple(paths) for uri, paths in files.items() if len(paths) > 1}


def collision_problem(uri: str, paths: typing.Sequence[Path]) -> str:
    """Say which files collided and what to do about it."""
    listed = ", ".join(str(path) for path in sorted(paths))
    return (
        f"{uri} is the uri of {len(paths)} different feature files -- {listed} -- "
        f"and a record of what ran holds one copy of a feature file per uri, so "
        f"one of them would be reported against the other's. Give them paths that "
        f"differ below their {EXTENSIONS_DIRECTORY} directory"
    )


def _caller_directory() -> Path | None:
    """The directory of the module two frames up, if it has a file."""
    frame = inspect.currentframe()
    for _ in range(2):
        if frame is None:  # pragma: no cover - no Python frames to walk
            return None
        frame = frame.f_back
    if frame is None:  # pragma: no cover - called with no caller above
        return None
    file_name: typing.Any = frame.f_globals.get("__file__")
    if not isinstance(file_name, str) or not file_name:
        return None
    return _resolve(Path(file_name)).parent


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:  # pragma: no cover - a path that cannot be resolved at all
        return path


def _uri(path: Path) -> str:
    """A relative path as a uri: slash-separated on every platform.

    ``pathlib`` yields backslashes on Windows, and the same string has to
    identify a feature file wherever the suite ran or a run on Windows is not
    comparable with one on Linux.
    """
    return path.as_posix()

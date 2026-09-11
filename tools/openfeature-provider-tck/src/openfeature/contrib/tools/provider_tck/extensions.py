"""Where the scenarios come from: the canonical set, plus whatever an adopter adds.

A provider is rarely only a provider. flagd has ``fractional`` targeting, another
vendor has a proprietary rollout rule, and the behaviour of those is as worth
pinning as the contract they sit on top of. Verifying them used to mean standing
up a second harness: a second backend lifecycle, a second set of fixtures, a
second thing to keep working. The canonical suite ran, then something else ran,
and nothing tied the two together.

So an adopter's own scenarios run **inside** the canonical suite instead --
against the same provider instance, in the same backend lifecycle, with the same
step vocabulary available. Almost nothing is needed to make that happen, because
pytest already scans. It collects ``conftest.py`` on its own and pytest-bdd
resolves step definitions through the fixture system, so a step defined in the
adopter's ``conftest.py`` -- or in the test module itself -- is in scope for the
scenarios ``scenarios()`` generates there. The only thing pytest cannot find by
itself is the feature files, which is what this module finds: a directory named
``extensions`` beside the adopter's test module.

That leaves one line, and it is the same line whether or not there are
extensions::

    scenarios(*feature_paths())

**An extension can never stand in for a canonical scenario.** The two are told
apart by the uri each feature file is identified by, and this module derives that
uri from where the file *is* rather than taking what the runner offers:

* ``gherkin/…`` is the packaged canonical assets, and nothing else;
* ``extensions/…`` is a discovered extension, whatever the adopter's own
  directory layout under ``extensions`` looks like.

The derivation is not decoration. pytest-bdd names a feature file by its parent
directory joined to its own name, so ``extensions/gherkin/errors.feature``
arrives as ``gherkin/errors.feature`` -- the same uri as a canonical file. A
record of what ran holds one copy of a feature file per uri, so the second file
is never read and its scenarios are attributed to the first one's or to nothing
at all. Java hit the same thing by a different route: a same-named feature file
in a second classpath root replaced the canonical one outright and the suite went
green having run the adopter's version.

The derivation is public, and the two problems it cannot rule out are reported
rather than raised, because the consumer of all of this is a conformance report
and that is not written here. Appendix F requires a report to say which scenarios
ran; nothing else can tell an adopter's question from the specification's.
"""

from __future__ import annotations

import importlib.resources
import inspect
import typing
from pathlib import Path

__all__ = [
    "CANONICAL_DIRECTORY",
    "EXTENSIONS_DIRECTORY",
    "EXTENSIONS_URI_PREFIX",
    "canonical_root",
    "collision_problem",
    "extension_root",
    "feature_paths",
    "features_path",
    "is_canonical",
    "is_canonical_uri",
    "reserved_prefix_problem",
    "uri_collisions",
    "uri_for",
]

_PACKAGE = "openfeature.contrib.tools.provider_tck"

CANONICAL_DIRECTORY = "gherkin"
"""The packaged directory the canonical feature files live in.

Also the uri prefix they are identified by, which is why it is reserved: anyone
reading ``gherkin/errors.feature`` is entitled to assume it is the
specification's file rather than a local one that happened to land in a directory
of that name.

The name is no longer chosen here. Appendix F fixes it: a canonical feature is
identified by its path **relative to the specification's asset directory**, and
``gherkin`` is the directory it occupies there. This suite used to vendor those
assets under a local name of its own and report that name instead, which is how
it came to answer ``features/errors.feature`` where Go -- consuming the same
assets as a module whose root *is* that directory -- answered
``gherkin/errors.feature``. A consumer joining two languages' results keys on the
uri and the scenario name, so the local name was the whole of the divergence.
"""

EXTENSIONS_DIRECTORY = "extensions"
"""Where an adopter puts feature files of their own, beside their test module.

Deliberately not the canonical name: a directory sharing it is how an extension
comes to occupy a canonical file's identity, and a convention that cannot collide
is worth more than one that reads slightly better. ``gherkin`` and ``extensions``
are distinct, so that still holds. The name is the one Java's TCK scans for on the
classpath -- renamed to ``extensions`` there in the same round as here -- so an
adopter who ships a provider in both languages still puts the same directory in
both repositories.
"""

EXTENSIONS_URI_PREFIX = "extensions"
"""The uri prefix an extension's scenarios are identified by.

The Go and JavaScript suites mount extensions under the same prefix, so a
consumer holding reports from several languages applies one rule to tell an
adopter's scenario from the specification's.

Equal to :data:`EXTENSIONS_DIRECTORY` today, and still a constant of its own: the
directory this suite scans and the prefix a report is keyed by are two separate
facts, and only the second is fixed by Appendix F. Collapsing them is exactly what
went wrong on the canonical half, where one name did both jobs and the reported
uri inherited a local choice.
"""


def features_path() -> str:
    """Return the directory holding the canonical feature files.

    Packaged with this distribution, so a consumer needs no submodule and no
    particular directory layout. This is the canonical set on its own; prefer
    :func:`feature_paths`, which also picks up an adopter's own scenarios.
    """
    return str(importlib.resources.files(_PACKAGE) / CANONICAL_DIRECTORY)


def feature_paths() -> tuple[str, ...]:
    """Return every feature directory this adoption should run.

    The canonical set, always, and an ``extensions`` directory beside the
    calling module if there is one. Hand the result to pytest-bdd's
    ``scenarios()``::

        scenarios(*feature_paths())

    That line does not change when an adopter adds an extension, which is what
    makes adding one a matter of creating a directory rather than of configuring
    anything.

    The calling module is located from the caller's frame, which is how
    pytest-bdd locates it for ``scenarios()`` itself, so the two agree about
    which module is adopting the suite. Call it from the test module rather than
    from a helper: a helper's directory is what a helper would find. A caller
    with no ``__file__`` -- an interactive session, an exec'd string -- gets the
    canonical set alone.
    """
    paths = [features_path()]
    directory = _caller_directory()
    if directory is not None:
        extensions = extension_root(directory)
        if extensions is not None:
            paths.append(str(extensions))
    return tuple(paths)


def extension_root(module_directory: Path) -> Path | None:
    """The extension directory beside a test module, or ``None`` if there is none.

    ``None`` rather than a path that contributes nothing, so that an adopter
    without extensions hands ``scenarios()`` exactly what they handed it before:
    same scenarios, same count, same report.
    """
    candidate = module_directory / EXTENSIONS_DIRECTORY
    return candidate if candidate.is_dir() else None


def canonical_root() -> Path | None:
    """The packaged canonical features directory, as a real path.

    ``None`` if the assets are not on the filesystem -- an installation from a
    zipimport, say. Everything built on this degrades to "cannot tell", which is
    the honest answer and never a false accusation.
    """
    try:
        return _resolve(Path(features_path()))
    except (OSError, TypeError):  # pragma: no cover - assets outside a filesystem
        return None


def is_canonical(path: Path) -> bool:
    """Whether a feature file is one of the packaged canonical ones."""
    canonical = canonical_root()
    return canonical is not None and _resolve(path).is_relative_to(canonical)


def is_canonical_uri(uri: str) -> bool:
    """Whether a uri names a canonical feature file.

    The discriminator between a canonical scenario and an adopter's own wherever
    it matters. Derived from the uri rather than carried beside it, so there is
    no second fact to disagree with the first.
    """
    return uri.startswith(f"{CANONICAL_DIRECTORY}/")


def uri_for(path: Path) -> str | None:
    """The uri a feature file should be identified by.

    ``None`` when the file is neither canonical nor under an extension
    directory, in which case the caller falls back to what pytest-bdd named it.

    Derived from the file's location rather than from pytest-bdd's
    ``rel_filename``, which is the parent directory's name joined to the file's
    own. That is what let ``extensions/gherkin/errors.feature`` present
    itself as ``gherkin/errors.feature``: the same uri as a canonical file, and
    a record of what ran holds one copy of a feature file per uri.
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
    file is then named exactly as a canonical one would be, and a reader has no
    way to tell that the specification did not write it.

    Returned rather than raised. The suite itself has no use for the answer --
    the scenarios run either way, and they are the adopter's to run -- so this is
    for whatever writes a record of the run to refuse to publish one.
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

    Deriving the uri from the file's location removes the collision an adopter
    is actually likely to hit, but it does not make one impossible. Two
    extension roots contributing the same relative path to a single suite -- two
    test modules sharing one ``tck_config`` from a conftest, each with an
    ``extensions/vendor.feature`` -- still land on ``extensions/vendor.feature``
    twice, and so does an ``extensions`` directory nested inside another one.

    That has to be refused rather than resolved. A record of what ran holds one
    copy of a feature file per uri, so the second file is never read: its
    scenarios are attributed to the first file's where the names happen to
    match, and go missing where they do not. The first is the silent form of
    exactly the failure Java measured, and it is the one a consumer cannot
    detect from the outside.

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

    These paths are assembled with ``pathlib``, so on Windows they arrive
    backslash-separated. A uri is not, and the same string has to identify a
    feature file wherever the suite ran or a run on Windows is not comparable
    with one on Linux.
    """
    return path.as_posix()

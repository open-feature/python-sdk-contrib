"""Where the conformance assets came from, and that it is the revision claimed.

The assets are not this repository's. They arrive through a submodule, the pin is
the only record of which revision a run asked its questions at, and the copies in
the package are gitignored -- so the one thing that can go wrong silently is the
copies being from a different revision than the pin names.

It has gone wrong. A rebase moves the gitlink and not the submodule's working
tree, so a sync after a rebase copied the *previous* pin's Gherkin over the
capability the suite had just been given, and only a self-test comparing the enum
against the assets noticed. That guard fires for one symptom -- a declarable
capability no scenario carries. A pin that changes nothing but the content of a
scenario would pass every guard in this package and still run the wrong suite,
which is what happened in another language: an entire adoption suite ran against
stale assets and reported byte-identical numbers to the previous run.

So the checkout is wired into the copy, the copy is a dependency of the test
task, and this is what holds both ends of that to their promise.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from pathlib import Path

import hatch_build_sync
import pytest
from hatch_build_sync import (
    SPEC_ROOT,
    UNPINNED_ENV,
    checkout_pinned_spec,
    pinned_revision,
)

PIN = "1111111111111111111111111111111111111111"
OTHER = "2222222222222222222222222222222222222222"


class _FakeGit:
    """A git that answers from a script and remembers what it was asked.

    Enough to pin the decision without a fixture repository: the three questions
    the checkout asks are the gitlink in the index, ``HEAD`` in the submodule,
    and the update itself, and what matters is which of them are asked and in
    what order.
    """

    def __init__(self, *, pin: str | None, heads: Sequence[str | None]) -> None:
        self.pin = pin
        self.heads = list(heads)
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str], cwd: Path) -> str | None:
        self.calls.append(list(args))
        if args[0] == "ls-files":
            return f"160000 {self.pin} 0\tspec" if self.pin else None
        if args[0] == "rev-parse":
            return self.heads.pop(0) if self.heads else None
        return ""

    @property
    def updated(self) -> bool:
        return any(call[0] == "submodule" for call in self.calls)


# -- against the real checkout ------------------------------------------------


def test_the_assets_on_disk_are_the_revision_the_pin_names() -> None:
    """The invariant itself, measured against this very checkout.

    ``poe test`` runs the sync first, so by the time this runs the checkout has
    already been brought to the pin -- which makes this a check that it really
    was, rather than a check of something the sync would have had to do anyway.
    It is also the assertion that would have failed in the pass where the stale
    Gherkin got through.

    Skipped, loudly, where the pin cannot be read at all. That is an unpacked
    sdist, which has no repository and no pin, and a linked git worktree whose
    ``.git`` file names a path this process's filesystem namespace cannot follow
    -- git inside the submodule answers there and git in the superproject does
    not. The guarantee is genuinely not in force in those environments, and a
    skip that says so is the honest report; a pass would not be.
    """
    pinned = pinned_revision()
    if pinned is None:
        pytest.skip(
            "no submodule pin is readable from here, so which revision these "
            "assets came from cannot be established -- see checkout_pinned_spec"
        )

    head = hatch_build_sync._run_git(["rev-parse", "HEAD"], SPEC_ROOT)
    assert head == pinned, (
        f"the spec submodule is checked out at {head} and the pin names "
        f"{pinned}, so the assets this run tested against are not the ones it "
        f"claims. Run `poe sync-spec-assets`"
    )


def test_only_a_gitlink_counts_as_a_pin() -> None:
    """A plain directory checked in under that name is not a revision.

    Reading the second field of whatever ``ls-files -s`` printed would turn a
    blob's hash into a commit id and compare it against the submodule's HEAD
    forever after, which fails in a way that explains nothing.
    """
    assert pinned_revision(lambda args, cwd: "100644 abc123 0\tspec") is None
    assert pinned_revision(lambda args, cwd: "") is None
    assert pinned_revision(lambda args, cwd: None) is None
    assert pinned_revision(lambda args, cwd: f"160000 {PIN} 0\tspec") == PIN


# -- the decision -------------------------------------------------------------


def test_a_working_tree_behind_the_pin_is_checked_out() -> None:
    """The case this exists for: a rebase moved the gitlink and nothing else."""
    git = _FakeGit(pin=PIN, heads=[OTHER, PIN])

    assert checkout_pinned_spec(git) == PIN

    assert git.updated, "the stale working tree was left where it was"
    assert git.calls[-1][0] == "rev-parse", (
        "the checkout was not confirmed after being asked for"
    )


def test_a_working_tree_already_at_the_pin_is_left_alone() -> None:
    """No git writes on the ordinary path.

    Every ``poe test`` runs this, including in a checkout somebody is midway
    through something in. Moving a submodule that is already where it should be
    is a write nobody asked for.
    """
    git = _FakeGit(pin=PIN, heads=[PIN])

    assert checkout_pinned_spec(git) == PIN

    assert not git.updated
    assert [call[0] for call in git.calls] == ["ls-files", "rev-parse"]


def test_a_checkout_that_does_not_reach_the_pin_stops_the_build() -> None:
    """Refused rather than warned, because here the answer is known and wrong.

    Unlike the unreadable-pin case, nothing is in doubt: the pin says one
    revision, the working tree is at another, and the update did not close the
    gap -- the commit is probably not in the local object store. Copying now
    would produce assets from a revision the build is about to claim it did not
    use.
    """
    git = _FakeGit(pin=PIN, heads=[OTHER, OTHER])

    with pytest.raises(RuntimeError) as raised:
        checkout_pinned_spec(git)

    message = str(raised.value)
    assert PIN in message and OTHER in message
    assert "nothing is copied" in message
    assert "fetch" in message, "the likely cause is named"
    assert UNPINNED_ENV in message, "so is the deliberate way round it"


def test_an_unreadable_pin_warns_and_lets_the_build_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two environments reach this and only one of them is a problem.

    An unpacked sdist has no repository, no pin and no submodule, and the assets
    are already in the tree: nothing to say. A checkout whose superproject this
    process cannot reach has all three and no way to check them, which is worth
    a warning every time -- it is the only signal that the guarantee is off.
    """
    git = _FakeGit(pin=None, heads=[])

    monkeypatch.setattr(hatch_build_sync, "SPEC_ROOT", Path("/no/such/submodule"))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert checkout_pinned_spec(git) is None
    assert not caught, f"an sdist build has nothing to warn about: {caught}"

    monkeypatch.setattr(hatch_build_sync, "SPEC_ROOT", SPEC_ROOT)
    with pytest.warns(UserWarning, match="copied from the submodule working tree"):
        assert checkout_pinned_spec(git) is None
    assert not git.updated


def test_the_escape_hatch_says_which_revision_it_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drafting a spec change locally is legitimate; doing it quietly is not.

    The revision is named because the point of the pin is that a report can say
    what it ran against, and a run in this mode cannot.
    """
    monkeypatch.setenv(UNPINNED_ENV, "1")
    git = _FakeGit(pin=PIN, heads=[OTHER])

    with pytest.warns(UserWarning, match=OTHER):
        assert checkout_pinned_spec(git) is None

    assert not git.updated
    assert [call[0] for call in git.calls] == ["rev-parse"], (
        "the pin is not consulted, which is the whole of what the flag does"
    )

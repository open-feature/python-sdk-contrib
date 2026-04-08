# Backward-compatible re-exports from openfeature-flagd-core.
# The canonical implementation now lives in openfeature.contrib.tools.flagd.core.
import typing

from openfeature.contrib.tools.flagd.core.model.flag import (  # noqa: F401
    Flag,
    _validate_metadata,
)
from openfeature.contrib.tools.flagd.core.model.flag_store import (
    FlagStore as _CoreFlagStore,
)
from openfeature.event import ProviderEventDetails


class FlagStore(_CoreFlagStore):
    """Backward-compatible FlagStore that supports an optional event callback."""

    def __init__(
        self,
        emit_provider_configuration_changed: typing.Optional[
            typing.Callable[[ProviderEventDetails], None]
        ] = None,
    ):
        super().__init__()
        self._emit_provider_configuration_changed = emit_provider_configuration_changed

    def update(self, flags_data: dict) -> typing.List[str]:
        changed_keys = super().update(flags_data)
        if self._emit_provider_configuration_changed is not None:
            self._emit_provider_configuration_changed(
                ProviderEventDetails(
                    flags_changed=list(self.flags.keys()),
                    metadata=dict(self.flag_set_metadata),
                )
            )
        return changed_keys

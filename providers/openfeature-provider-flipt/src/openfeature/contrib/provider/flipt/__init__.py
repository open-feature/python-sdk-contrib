from typing import Callable, Optional

from openfeature.contrib.provider.ofrep import OFREPProvider
from openfeature.provider import Metadata

# Only export the FliptProvider class symbol form the package
__all__ = ["FliptProvider"]


class FliptProvider(OFREPProvider):
    """A provider for Flipt feature flags service that extends the OFREP Provider for interacting with Flipt's OFREP API"""

    def __init__(
        self,
        base_url: str,
        namespace: str,
        *,
        headers_factory: Optional[Callable[[], dict[str, str]]] = None,
        timeout: float = 5.0,
    ):
        """Override the OFREPProvider constructor to add a namespace parameter"""

        # Build a headers factory function that includes the Flipt namespace header
        headers_factory = self._resolve_header_factory(namespace, headers_factory)
        super().__init__(base_url, headers_factory=headers_factory, timeout=timeout)

    def _resolve_header_factory(
        self, namespace: str, headers_factory: Optional[Callable[[], dict[str, str]]]
    ) -> Callable[[], dict[str, str]]:
        """
        Resolves and returns a headers factory callable that includes the "X-Flipt-Namespace" header.

        If a headers factory is provided, it will be called and its headers will be merged with the
        "X-Flipt-Namespace" header. If no headers factory is provided, a new factory will be created
        that only includes the "X-Flipt-Namespace" header.

        Args:
            namespace (str): The namespace value to be included in the "X-Flipt-Namespace" header.
            headers_factory (Optional[Callable[[], Dict[str, str]]]): An optional callable that returns
                a dictionary of headers.

        Returns:
            Callable[[], Dict[str, str]]: A callable that returns a dictionary of headers including
            the "X-Flipt-Namespace" header.
        """
        if headers_factory is None:
            headers = {"X-Flipt-Namespace": namespace}
        else:
            headers = {
                **headers_factory(),
                "X-Flipt-Namespace": namespace,
            }

        return lambda: headers

    def get_metadata(self) -> Metadata:
        return Metadata(name="Flipt Provider")

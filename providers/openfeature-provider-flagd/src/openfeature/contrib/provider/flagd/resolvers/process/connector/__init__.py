import typing

from openfeature.evaluation_context import EvaluationContext


class FlagStateConnector(typing.Protocol):
    def initialize(
        self, evaluation_context: EvaluationContext
    ) -> None: ...  # pragma: no cover

    def shutdown(self) -> None: ...  # pragma: no cover

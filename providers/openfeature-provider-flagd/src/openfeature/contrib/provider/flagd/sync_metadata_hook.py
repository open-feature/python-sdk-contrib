import typing

from openfeature.evaluation_context import EvaluationContext
from openfeature.hook import Hook, HookContext, HookHints


class SyncMetadataHook(Hook):
    def __init__(self, context_supplier: typing.Callable[[], EvaluationContext]):
        self.context_supplier = context_supplier

    def before(
        self, hook_context: HookContext, hints: HookHints
    ) -> typing.Optional[EvaluationContext]:
        return self.context_supplier()

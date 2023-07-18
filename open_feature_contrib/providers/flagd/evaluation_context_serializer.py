import typing

from open_feature.evaluation_context.evaluation_context import EvaluationContext


class EvaluationContextSerializer:
    def to_dict(ctx: typing.Optional[EvaluationContext]):
        return (
            {
                **ctx.attributes,
                **(EvaluationContextSerializer.__extract_key(ctx)),
            }
            if ctx
            else {}
        )

    def __extract_key(ctx: EvaluationContext):
        return {"targetingKey": ctx.targeting_key} if ctx.targeting_key is str else {}

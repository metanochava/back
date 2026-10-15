


def _entity_id(serializer):
    return getattr(serializer.context.get("request"), "entity_id", None)

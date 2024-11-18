def to_bool(s: str) -> bool:
    return s.lower() == "true"


def to_list(s: str) -> list:
    values = s.replace('"', "").split(",")
    return [s.strip() for s in values]

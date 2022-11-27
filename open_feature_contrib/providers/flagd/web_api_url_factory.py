from .flag_type import FlagType


class WebApiUrlFactory:
    BOOLEAN = "schema.v1.Service/ResolveBoolean"
    STRING = "schema.v1.Service/ResolveString"
    FLOAT = "schema.v1.Service/ResolveFloat"
    INTEGER = "schema.v1.Service/ResolveInteger"
    OBJECT = "schema.v1.Service/ResolveObject"

    def __init__(self, schema, host, port):
        self.root = f"{schema}://{host}:{port}"

    def get_boolean_path(self):
        return self.__format_url(self.BOOLEAN)

    def get_string_path(self):
        return self.__format_url(self.STRING)

    def get_float_path(self):
        return self.__format_url(self.FLOAT)

    def get_integer_path(self):
        return self.__format_url(self.INTEGER)

    def get_object_path(self):
        return self.__format_url(self.OBJECT)

    def get_path_for(self, flag_type: FlagType):
        if (flag_type == FlagType.BOOLEAN):
            return self.get_boolean_path()

        if (flag_type == FlagType.STRING):
            return self.get_string_path()

        if (flag_type == FlagType.FLOAT):
            return self.get_float_path()

        if (flag_type == FlagType.INTEGER):
            return self.get_integer_path()

        if (flag_type == FlagType.OBJECT):
            return self.get_object_path()

        raise Exception("Invalid flag type passed to WebApiUrlFactory")

    def __format_url(self, path: str):
        return f"{self.root}/{path}"

from .flag_type import FlagType


class WebApiUrlFactory:
    BOOLEAN = "schema.v1.Service/ResolveBoolean"
    STRING = "schema.v1.Service/ResolveString"
    FLOAT = "schema.v1.Service/ResolveFloat"
    INTEGER = "schema.v1.Service/ResolveInteger"
    OBJECT = "schema.v1.Service/ResolveObject"

    # provides dynamic dictionary-based resolution by flag type
    __mapping = {
        FlagType.BOOLEAN: "get_boolean_path",
        FlagType.STRING: "get_string_path",
        FlagType.FLOAT: "get_float_path",
        FlagType.INTEGER: "get_integer_path",
        FlagType.OBJECT: "get_object_path",
    }
    __default_mapping_key = "_invalid_flag_type_method"

    def __init__(self, schema, host, port):
        self.root = f"{schema}://{host}:{port}"

    def get_boolean_path(self):
        return self._format_url(self.BOOLEAN)

    def get_string_path(self):
        return self._format_url(self.STRING)

    def get_float_path(self):
        return self._format_url(self.FLOAT)

    def get_integer_path(self):
        return self._format_url(self.INTEGER)

    def get_object_path(self):
        return self._format_url(self.OBJECT)

    def get_path_for(self, flag_type: FlagType):
        method_name = self.__mapping.get(
            flag_type, WebApiUrlFactory.__default_mapping_key
        )
        return getattr(self, method_name)()

    def _format_url(self, path: str):
        return f"{self.root}/{path}"

    def _invalid_flag_type_method(self):
        raise Exception("Invalid flag type passed to factory")

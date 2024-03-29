# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: schema/v1/schema.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import struct_pb2 as google_dot_protobuf_dot_struct__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x16schema/v1/schema.proto\x12\tschema.v1\x1a\x1cgoogle/protobuf/struct.proto\"F\n\x11ResolveAllRequest\x12\x31\n\x07\x63ontext\x18\x01 \x01(\x0b\x32\x17.google.protobuf.StructR\x07\x63ontext\"\xa2\x01\n\x12ResolveAllResponse\x12>\n\x05\x66lags\x18\x01 \x03(\x0b\x32(.schema.v1.ResolveAllResponse.FlagsEntryR\x05\x66lags\x1aL\n\nFlagsEntry\x12\x10\n\x03key\x18\x01 \x01(\tR\x03key\x12(\n\x05value\x18\x02 \x01(\x0b\x32\x12.schema.v1.AnyFlagR\x05value:\x02\x38\x01\"\xed\x01\n\x07\x41nyFlag\x12\x16\n\x06reason\x18\x01 \x01(\tR\x06reason\x12\x18\n\x07variant\x18\x02 \x01(\tR\x07variant\x12\x1f\n\nbool_value\x18\x03 \x01(\x08H\x00R\tboolValue\x12#\n\x0cstring_value\x18\x04 \x01(\tH\x00R\x0bstringValue\x12#\n\x0c\x64ouble_value\x18\x05 \x01(\x01H\x00R\x0b\x64oubleValue\x12<\n\x0cobject_value\x18\x06 \x01(\x0b\x32\x17.google.protobuf.StructH\x00R\x0bobjectValueB\x07\n\x05value\"e\n\x15ResolveBooleanRequest\x12\x19\n\x08\x66lag_key\x18\x01 \x01(\tR\x07\x66lagKey\x12\x31\n\x07\x63ontext\x18\x02 \x01(\x0b\x32\x17.google.protobuf.StructR\x07\x63ontext\"\x95\x01\n\x16ResolveBooleanResponse\x12\x14\n\x05value\x18\x01 \x01(\x08R\x05value\x12\x16\n\x06reason\x18\x02 \x01(\tR\x06reason\x12\x18\n\x07variant\x18\x03 \x01(\tR\x07variant\x12\x33\n\x08metadata\x18\x04 \x01(\x0b\x32\x17.google.protobuf.StructR\x08metadata\"d\n\x14ResolveStringRequest\x12\x19\n\x08\x66lag_key\x18\x01 \x01(\tR\x07\x66lagKey\x12\x31\n\x07\x63ontext\x18\x02 \x01(\x0b\x32\x17.google.protobuf.StructR\x07\x63ontext\"\x94\x01\n\x15ResolveStringResponse\x12\x14\n\x05value\x18\x01 \x01(\tR\x05value\x12\x16\n\x06reason\x18\x02 \x01(\tR\x06reason\x12\x18\n\x07variant\x18\x03 \x01(\tR\x07variant\x12\x33\n\x08metadata\x18\x04 \x01(\x0b\x32\x17.google.protobuf.StructR\x08metadata\"c\n\x13ResolveFloatRequest\x12\x19\n\x08\x66lag_key\x18\x01 \x01(\tR\x07\x66lagKey\x12\x31\n\x07\x63ontext\x18\x02 \x01(\x0b\x32\x17.google.protobuf.StructR\x07\x63ontext\"\x93\x01\n\x14ResolveFloatResponse\x12\x14\n\x05value\x18\x01 \x01(\x01R\x05value\x12\x16\n\x06reason\x18\x02 \x01(\tR\x06reason\x12\x18\n\x07variant\x18\x03 \x01(\tR\x07variant\x12\x33\n\x08metadata\x18\x04 \x01(\x0b\x32\x17.google.protobuf.StructR\x08metadata\"a\n\x11ResolveIntRequest\x12\x19\n\x08\x66lag_key\x18\x01 \x01(\tR\x07\x66lagKey\x12\x31\n\x07\x63ontext\x18\x02 \x01(\x0b\x32\x17.google.protobuf.StructR\x07\x63ontext\"\x91\x01\n\x12ResolveIntResponse\x12\x14\n\x05value\x18\x01 \x01(\x03R\x05value\x12\x16\n\x06reason\x18\x02 \x01(\tR\x06reason\x12\x18\n\x07variant\x18\x03 \x01(\tR\x07variant\x12\x33\n\x08metadata\x18\x04 \x01(\x0b\x32\x17.google.protobuf.StructR\x08metadata\"d\n\x14ResolveObjectRequest\x12\x19\n\x08\x66lag_key\x18\x01 \x01(\tR\x07\x66lagKey\x12\x31\n\x07\x63ontext\x18\x02 \x01(\x0b\x32\x17.google.protobuf.StructR\x07\x63ontext\"\xad\x01\n\x15ResolveObjectResponse\x12-\n\x05value\x18\x01 \x01(\x0b\x32\x17.google.protobuf.StructR\x05value\x12\x16\n\x06reason\x18\x02 \x01(\tR\x06reason\x12\x18\n\x07variant\x18\x03 \x01(\tR\x07variant\x12\x33\n\x08metadata\x18\x04 \x01(\x0b\x32\x17.google.protobuf.StructR\x08metadata\"V\n\x13\x45ventStreamResponse\x12\x12\n\x04type\x18\x01 \x01(\tR\x04type\x12+\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32\x17.google.protobuf.StructR\x04\x64\x61ta\"\x14\n\x12\x45ventStreamRequest2\xcd\x04\n\x07Service\x12K\n\nResolveAll\x12\x1c.schema.v1.ResolveAllRequest\x1a\x1d.schema.v1.ResolveAllResponse\"\x00\x12W\n\x0eResolveBoolean\x12 .schema.v1.ResolveBooleanRequest\x1a!.schema.v1.ResolveBooleanResponse\"\x00\x12T\n\rResolveString\x12\x1f.schema.v1.ResolveStringRequest\x1a .schema.v1.ResolveStringResponse\"\x00\x12Q\n\x0cResolveFloat\x12\x1e.schema.v1.ResolveFloatRequest\x1a\x1f.schema.v1.ResolveFloatResponse\"\x00\x12K\n\nResolveInt\x12\x1c.schema.v1.ResolveIntRequest\x1a\x1d.schema.v1.ResolveIntResponse\"\x00\x12T\n\rResolveObject\x12\x1f.schema.v1.ResolveObjectRequest\x1a .schema.v1.ResolveObjectResponse\"\x00\x12P\n\x0b\x45ventStream\x12\x1d.schema.v1.EventStreamRequest\x1a\x1e.schema.v1.EventStreamResponse\"\x00\x30\x01\x42t\n\rcom.schema.v1B\x0bSchemaProtoP\x01Z\x11schema/service/v1\xa2\x02\x03SXX\xaa\x02\tSchema.V1\xca\x02\tSchema\\V1\xe2\x02\x15Schema\\V1\\GPBMetadata\xea\x02\nSchema::V1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'schema.v1.schema_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\rcom.schema.v1B\013SchemaProtoP\001Z\021schema/service/v1\242\002\003SXX\252\002\tSchema.V1\312\002\tSchema\\V1\342\002\025Schema\\V1\\GPBMetadata\352\002\nSchema::V1'
  _RESOLVEALLRESPONSE_FLAGSENTRY._options = None
  _RESOLVEALLRESPONSE_FLAGSENTRY._serialized_options = b'8\001'
  _globals['_RESOLVEALLREQUEST']._serialized_start=67
  _globals['_RESOLVEALLREQUEST']._serialized_end=137
  _globals['_RESOLVEALLRESPONSE']._serialized_start=140
  _globals['_RESOLVEALLRESPONSE']._serialized_end=302
  _globals['_RESOLVEALLRESPONSE_FLAGSENTRY']._serialized_start=226
  _globals['_RESOLVEALLRESPONSE_FLAGSENTRY']._serialized_end=302
  _globals['_ANYFLAG']._serialized_start=305
  _globals['_ANYFLAG']._serialized_end=542
  _globals['_RESOLVEBOOLEANREQUEST']._serialized_start=544
  _globals['_RESOLVEBOOLEANREQUEST']._serialized_end=645
  _globals['_RESOLVEBOOLEANRESPONSE']._serialized_start=648
  _globals['_RESOLVEBOOLEANRESPONSE']._serialized_end=797
  _globals['_RESOLVESTRINGREQUEST']._serialized_start=799
  _globals['_RESOLVESTRINGREQUEST']._serialized_end=899
  _globals['_RESOLVESTRINGRESPONSE']._serialized_start=902
  _globals['_RESOLVESTRINGRESPONSE']._serialized_end=1050
  _globals['_RESOLVEFLOATREQUEST']._serialized_start=1052
  _globals['_RESOLVEFLOATREQUEST']._serialized_end=1151
  _globals['_RESOLVEFLOATRESPONSE']._serialized_start=1154
  _globals['_RESOLVEFLOATRESPONSE']._serialized_end=1301
  _globals['_RESOLVEINTREQUEST']._serialized_start=1303
  _globals['_RESOLVEINTREQUEST']._serialized_end=1400
  _globals['_RESOLVEINTRESPONSE']._serialized_start=1403
  _globals['_RESOLVEINTRESPONSE']._serialized_end=1548
  _globals['_RESOLVEOBJECTREQUEST']._serialized_start=1550
  _globals['_RESOLVEOBJECTREQUEST']._serialized_end=1650
  _globals['_RESOLVEOBJECTRESPONSE']._serialized_start=1653
  _globals['_RESOLVEOBJECTRESPONSE']._serialized_end=1826
  _globals['_EVENTSTREAMRESPONSE']._serialized_start=1828
  _globals['_EVENTSTREAMRESPONSE']._serialized_end=1914
  _globals['_EVENTSTREAMREQUEST']._serialized_start=1916
  _globals['_EVENTSTREAMREQUEST']._serialized_end=1936
  _globals['_SERVICE']._serialized_start=1939
  _globals['_SERVICE']._serialized_end=2528
# @@protoc_insertion_point(module_scope)

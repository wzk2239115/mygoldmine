; Deserialization sinks for Java
; Detects ObjectInputStream.readObject(), Jackson/XStream/SnakeYAML deserialization

; ObjectInputStream.readObject() and readUnshared()
(method_invocation
  object: (identifier) @var
  name: (identifier) @method
  (#match? @method "^(readObject|readUnshared)$")
)

; Jackson ObjectMapper.readValue()
(method_invocation
  object: (identifier) @var
  name: (identifier) @method
  (#match? @method "readValue")
)

; XStream.fromXML()
(method_invocation
  object: (identifier) @var
  name: (identifier) @method
  (#eq? @method "fromXML")
)

; SnakeYAML Yaml.load()
(method_invocation
  object: (identifier) @var
  name: (identifier) @method
  (#eq? @method "load")
)

; Constructor-based instantiation with Class.forName() - potential deserialization
(method_invocation
  name: (identifier) @method
  (#match? @method "^(forName|newInstance)$")
)

; Commons Lang SerializationUtils
(method_invocation
  name: (identifier) @method
  (#match? @method "^(deserialize)$")
)

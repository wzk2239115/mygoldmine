; Deserialization sinks for Go
; Detects unsafe serialization/deserialization patterns

; encoding/gob
(call_expression
  function: (selector_expression
    operand: (identifier) @pkg
    field: (field_identifier) @method
  )
  (#match? @pkg "^gob$")
  (#match? @method "^(NewDecoder|Decode)$")
)

; encoding/json
(call_expression
  function: (selector_expression
    operand: (identifier) @pkg
    field: (field_identifier) @method
  )
  (#match? @pkg "json")
  (#match? @method "^(Unmarshal|Decode)$")
)

; encoding/xml
(call_expression
  function: (selector_expression
    operand: (identifier) @pkg
    field: (field_identifier) @method
  )
  (#match? @pkg "xml")
  (#match? @method "^(Unmarshal|Decode)$")
)

; encoding/yaml
(call_expression
  function: (selector_expression
    operand: (identifier) @pkg
    field: (field_identifier) @method
  )
  (#match? @pkg "yaml")
  (#match? @method "^(Unmarshal|Decode)$")
)

; Unsafe pointer operations
(call_expression
  function: (selector_expression
    operand: (identifier) @pkg
    field: (field_identifier) @method
  )
  (#match? @pkg "unsafe")
  (#match? @method "^(Pointer)$")
)

; pickle-like operations
(call_expression
  function: (identifier) @func
  (#match? @func "^(UnmarshalBinary|UnmarshalText)$")
)

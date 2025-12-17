; Deserialization sinks for C++
; Detects unsafe serialization/deserialization patterns

; std::memcpy and similar functions
(call_expression
  function: (identifier) @func
  (#match? @func "^(memcpy|memmove|memset|strcpy|strncpy)$")
)

; Stream operations
(call_expression
  function: (field_expression
    field: (field_identifier) @method
  )
  (#match? @method "^(read|readObject|deserialize)$")
)

; Socket operations
(call_expression
  function: (identifier) @func
  (#match? @func "^(recv|recvfrom|read)$")
)

; Boost serialization
(call_expression
  function: (qualified_identifier
    name: (identifier) @method
  )
  (#match? @method "^(load|loads)$")
)

; std::vector/array copy
(call_expression
  function: (field_expression
    field: (field_identifier) @method
  )
  (#match? @method "assign")
)

; Unsafe pointer casts
(cast_expression
  type: (pointer_declarator)
)

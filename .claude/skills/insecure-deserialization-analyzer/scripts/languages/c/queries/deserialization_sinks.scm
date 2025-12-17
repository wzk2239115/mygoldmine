; Deserialization sinks for C
; Detects unsafe serialization/deserialization patterns

; memcpy/memmove with untrusted data
(function_call
  function: (identifier) @func
  (#match? @func "^(memcpy|memmove|memset|strcpy|strncpy)$")
)

; fread operations
(function_call
  function: (identifier) @func
  (#match? @func "^fread$")
)

; Socket recv operations
(function_call
  function: (identifier) @func
  (#match? @func "^(recv|recvfrom|read)$")
)

; Deserialization of structs
(function_call
  function: (identifier) @func
  (#match? @func "^(marshal_loads|unmarshal)$")
)

; Unsafe casting
(cast_expression
  type: (type_identifier) @type
)

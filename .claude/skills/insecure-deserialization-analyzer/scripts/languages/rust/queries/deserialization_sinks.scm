; Deserialization sinks for Rust
; Detects unsafe serialization/deserialization patterns

; serde deserialization
(call_expression
  function: (field_expression
    field: (field_identifier) @method
  )
  (#match? @method "^(deserialize|from_str|from_slice)$")
)

; serde_json
(call_expression
  function: (generic_function
    function: (scoped_identifier
      path: (identifier) @crate
      name: (identifier) @method
    )
  )
  (#match? @crate "json")
  (#match? @method "^(from_str|from_slice)$")
)

; bincode
(call_expression
  function: (field_expression
    field: (field_identifier) @method
  )
  (#match? @method "^(deserialize|decode)$")
)

; Unsafe pointer operations
(call_expression
  function: (identifier) @func
  (#match? @func "^(from_raw_parts|from_raw)$")
)

; Unsafe memory operations
(call_expression
  function: (identifier) @func
  (#match? @func "^(copy_nonoverlapping|copy|write)$")
)

; transmute - type punning
(call_expression
  function: (identifier) @func
  (#match? @func "^transmute")
)

; Unsafe blocks with deserialization
(unsafe_block
  (call_expression
    function: (field_expression
      field: (field_identifier) @method
    )
    (#match? @method "^(deserialize|decode)$")
  )
)

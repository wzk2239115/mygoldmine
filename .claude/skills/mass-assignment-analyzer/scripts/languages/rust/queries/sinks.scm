;; Rust Mass Assignment Sink Detection
;; Detects dangerous data binding and serialization patterns

;; serde_json deserialization
(call_expression
  function: (scoped_identifier
    path: (identifier) @module
    name: (identifier) @method))
(#match? @module "serde_json")
(#match? @method "^(from_str|from_slice|from_value)$")

;; diesel operations
(call_expression
  function: (scoped_identifier
    path: (_) @table
    name: (identifier) @method))
(#match? @method "^(insert_into|execute|load)$")

;; Into/From trait implementations
(call_expression
  function: (scoped_identifier
    path: (_) @module
    name: (identifier) @method))
(#match? @method "^(into|from)$")

;; Unsafe block with ptr operations
(call_expression
  function: (scoped_identifier
    path: (identifier) @ptr
    name: (identifier) @method))
(#match? @ptr "ptr")
(#match? @method "^(copy_nonoverlapping|write|copy)$")

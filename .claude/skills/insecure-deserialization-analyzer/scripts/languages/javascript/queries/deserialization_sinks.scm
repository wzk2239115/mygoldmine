; Deserialization sinks for JavaScript
; Detects vm.runInContext(), eval(), Function constructor, and similar dangerous patterns

; vm.runInContext() and vm.runInNewContext()
(call_expression
  function: (member_expression
    object: (identifier) @module
    property: (property_identifier) @method
  )
  (#match? @module "^vm$")
  (#match? @method "^(runInContext|runInNewContext|run)$")
)

; eval() calls
(call_expression
  function: (identifier) @func
  (#eq? @func "eval")
)

; Function() constructor
(new_expression
  constructor: (identifier) @constructor
  (#eq? @constructor "Function")
)

; setTimeout/setInterval with string (code injection)
(call_expression
  function: (identifier) @func
  arguments: (arguments
    (string) @code_arg
  )
  (#match? @func "^(setTimeout|setInterval)$")
)

; require() with dynamic path - can load arbitrary modules
(call_expression
  function: (identifier) @func
  (#eq? @func "require")
)

; dynamic import() - potential deserialization vector
(import
  source: (string) @source
)

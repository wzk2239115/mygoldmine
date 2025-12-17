; Deserialization sinks for TypeScript
; Same as JavaScript but with type annotations

; eval() function
(call_expression
  function: (identifier) @func
  (#eq? @func "eval")
)

; Function constructor
(new_expression
  constructor: (identifier) @func
  (#eq? @func "Function")
)

; vm.runInContext and vm.runInNewContext
(call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (identifier) @method
  )
  (#eq? @obj "vm")
  (#match? @method "^runIn(Context|NewContext)$")
)

; setTimeout/setInterval with string code
(call_expression
  function: (identifier) @func
  (#match? @func "^(setTimeout|setInterval)$")
  arguments: (arguments
    (string) @arg
  )
)

; Dynamic require/import
(call_expression
  function: (identifier) @func
  (#eq? @func "require")
  arguments: (arguments
    (string) @arg
  )
)

; Dynamic import()
(import_call
  (string) @arg
)

; Worker constructor
(new_expression
  constructor: (identifier) @ctor
  (#match? @ctor "^(Worker|SharedWorker)$")
)

; MessagePort.onmessage with eval
(assignment_expression
  left: (member_expression
    property: (identifier) @prop
  )
  (#eq? @prop "onmessage")
  right: (function) @handler
)

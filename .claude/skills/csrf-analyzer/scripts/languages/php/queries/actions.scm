;; PHP POST routes - used for CSRF detection
;; Matches common POST endpoint patterns

;; Laravel routes with POST method
((method_invocation
  object: (variable_name) @obj
  method: (name) @method
  arguments: (arguments
    (string (string_value) @route)
    .
  )
) (#eq? @method "post") @match)

;; Laravel routes with 'post' method variant
((method_invocation
  object: (variable_name) @obj
  method: (name) @method
  arguments: (arguments
    . as @first_arg
  )
) (#eq? @method "post") @match)

;; Slim framework POST routes
((method_invocation
  object: (variable_name) @obj
  method: (name) @method
  arguments: (arguments
    (string (string_value) @route)
    .
  )
) (#eq? @method "post") @match)

;; Generic function calls with POST pattern
((function_call_expression
  function: (name) @func
  arguments: (arguments
    (string (string_value) @route)
    .
  )
) (#match? @func "^post") @match)

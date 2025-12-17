;; Python Flask/Django POST routes - used for CSRF detection
;; Matches Flask @app.route(methods=['POST']) and Django patterns

;; Flask route decorator with POST method
((decorator
  "@" @at
  (dotted_name
    (identifier) @obj
    (identifier) @method
  )
  (arguments
    (string (string_value) @route)
    .
    (keyword_argument
      name: (identifier) @kwarg_name
      value: (list
        (string (string_value) @method_value)
      )
    )
  )
) (#eq? @method "route") (#eq? @kwarg_name "methods") (#match? @method_value "POST") @match)

;; Flask route decorator with 'methods' parameter
((decorator
  "@" @at
  (attribute
    object: (identifier) @obj
    attribute: (identifier) @method
  )
  (arguments
    (string (string_value) @route)
    (keyword_argument
      name: (identifier) @kwarg_name
      value: (list
        (string (string_value) @method_value)
      )
    )
  )
) (#eq? @method "route") (#match? @method_value "POST") @match)

;; Django path with POST handling
((function_call
  function: (identifier) @func
  arguments: (arguments
    (string (string_value) @pattern)
    (identifier) @view
  )
) (#eq? @func "path") @match)

;; Flask methods=['POST']
((keyword_argument
  name: (identifier) @name
  value: (list
    (string (string_value) @method)
  )
) (#eq? @name "methods") (#match? @method "POST") @match)

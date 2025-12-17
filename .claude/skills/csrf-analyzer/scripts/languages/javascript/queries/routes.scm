;; JavaScript Express/Koa POST routes - used for CSRF detection
;; Matches app.post(), router.post(), etc.

;; Express app.post() calls
((call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (property_identifier) @method
  )
  arguments: (arguments
    (string (string_fragment)* @route)?
    .
  )
) (#eq? @method "post") @match)

;; Express router.post() calls
((call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (property_identifier) @method
  )
  arguments: (arguments
    (string (string_fragment)* @route)?
    .
  )
) (#eq? @method "post") @match)

;; Koa router.post() calls
((call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (property_identifier) @method
  )
  arguments: (arguments
    (string (string_fragment)* @route)?
    .
  )
) (#eq? @method "post") @match)

;; Generic app.post pattern
((call_expression
  function: (member_expression
    property: (property_identifier) @method
  )
  arguments: (arguments
    (string)? @route
    .
  )
) (#eq? @method "post") @match)

;; app.put() for state changes
((call_expression
  function: (member_expression
    object: (identifier)
    property: (property_identifier) @method
  )
  arguments: (arguments)
) (#eq? @method "put") @match)

;; app.delete() for state changes
((call_expression
  function: (member_expression
    object: (identifier)
    property: (property_identifier) @method
  )
  arguments: (arguments)
) (#eq? @method "delete") @match)

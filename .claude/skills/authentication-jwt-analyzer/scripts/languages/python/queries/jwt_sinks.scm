;; Python JWT sink detection query
;; Detects: jwt.decode(), PyJWT().decode(), token.verify(), etc.

;; Direct function calls to jwt.decode()
(call
  function: (attribute
    object: (identifier) @object
    attribute: (identifier) @method)
  (#match? @method "^(decode|verify)$")
  (#match? @object "^(jwt|token)$")
) @jwt_sink

;; jwt.decode() with module reference
(call
  function: (attribute
    object: (attribute
      object: (identifier) @module
      attribute: (identifier) @submodule)
    attribute: (identifier) @method)
  (#match? @method "^(decode|verify)$")
  (#match? @module "^(jwt|auth)$")
) @jwt_sink

;; PyJWT class instantiation and decode
(call
  function: (attribute
    object: (call
      function: (identifier) @class_name)
    attribute: (identifier) @method)
  (#match? @class_name "^(PyJWT|JWT)$")
  (#match? @method "^(decode|verify)$")
) @jwt_sink

;; Direct PyJWT.decode() static call
(call
  function: (attribute
    object: (identifier) @class_name
    attribute: (identifier) @method)
  (#match? @class_name "^(PyJWT|JWT)$")
  (#match? @method "^(decode|verify)$")
) @jwt_sink

;; Subscript access like jwt["decode"]
(call
  function: (subscript
    value: (identifier) @object
    subscript: (string) @method_name)
  (#match? @object "^(jwt|token)$")
) @jwt_sink

;; JavaScript/TypeScript JWT sink detection query
;; Detects: jwt.verify(), jsonwebtoken.verify(), decode(), etc.

;; Method call: jwt.verify() or token.verify()
(call_expression
  function: (member_expression
    object: (identifier) @object
    property: (property_identifier) @method)
  (#match? @method "^(verify|decode|sign)$")
  (#match? @object "^(jwt|token|jwtToken|payload)$")
) @jwt_sink

;; Nested member call: jsonwebtoken.verify()
(call_expression
  function: (member_expression
    object: (member_expression
      object: (identifier) @module
      property: (property_identifier) @submodule)
    property: (property_identifier) @method)
  (#match? @method "^(verify|decode|sign)$")
) @jwt_sink

;; Direct function call: verifyToken(), decodeToken(), etc.
(call_expression
  function: (identifier) @func_name
  (#match? @func_name "^(verifyToken|verifyJWT|decodeToken|verifyJWToken|verify|decode)$")
) @jwt_sink

;; Arrow function or function call with member access
(call_expression
  function: (member_expression
    object: (identifier)
    property: (property_identifier) @method)
  (#match? @method "^(verify|decode|sign|validateToken)$")
) @jwt_sink

;; Require/import based call
(call_expression
  function: (member_expression
    object: (call_expression
      function: (identifier) @req_func)
    property: (property_identifier) @method)
  (#match? @req_func "^(require)$")
  (#match? @method "^(verify|decode|sign)$")
) @jwt_sink

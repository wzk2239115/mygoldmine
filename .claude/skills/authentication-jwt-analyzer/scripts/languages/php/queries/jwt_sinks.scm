;; PHP JWT sink detection query
;; Detects: Firebase\JWT\JWT::decode(), verify(), etc.

;; Static method call: JWT::decode(), Token::verify(), etc.
(scoped_call_expression
  name: (name) @method_name
  (#match? @method_name "^(decode|verify|validate|sign)$")
) @jwt_sink

;; Direct function calls with JWT-related names
(function_call_expression
  function: (name) @func_name
  (#match? @func_name "^(decode|verify|jwt_decode|decode_token|verify_jwt)$")
) @jwt_sink

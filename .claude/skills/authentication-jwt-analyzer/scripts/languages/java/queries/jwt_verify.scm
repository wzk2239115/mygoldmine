;; Java JWT sink detection query
;; Detects: Jwts.parser(), parseClaimsJws(), verify(), etc.

;; Static method call: Jwts.parser()
(method_invocation
  object: (identifier) @object
  method: (identifier) @method
  arguments: (argument_list) @args
  (#match? @object "^(Jwts|JWT|JWTVerifier)$")
  (#match? @method "^(parser|verify|parseClaimsJws|parsePlaintextJws)$")
) @jwt_sink

;; Chained method calls: Jwts.parser().setSigningKey()...parseClaimsJws()
(method_invocation
  object: (method_invocation) @chain
  method: (identifier) @method
  arguments: (argument_list) @args
  (#match? @method "^(setSigningKey|parseClaimsJws|parseClaimsJwt|parsePlaintextJwt|verify)$")
) @jwt_sink

;; Constructor call: new JWTVerifier()
(object_creation_expression
  type: (type_identifier) @class_name
  arguments: (argument_list) @args
  (#match? @class_name "^(JWTVerifier|JWT|JwtDecoder)$")
) @jwt_sink

;; Instance method: verifier.verify()
(method_invocation
  object: (identifier) @var_name
  method: (identifier) @method
  arguments: (argument_list) @args
  (#match? @method "^(verify|decode|validateToken|checkSignature)$")
) @jwt_sink

;; Field access: algorithm.verify()
(method_invocation
  object: (field_access
    object: (identifier)
    field: (identifier) @field_name)
  method: (identifier) @method
  arguments: (argument_list) @args
  (#match? @method "^(verify|decode|parseClaimsJws)$")
) @jwt_sink

;; Library method: JwtClaims claims = Jwts.parserBuilder()...build().parseClaimsJws()
(method_invocation
  object: (method_invocation) @chain
  method: (identifier) @method
  arguments: (argument_list) @args
  (#match? @method "^(parseClaimsJws|parseClaimsJwt|verify)$")
) @jwt_sink

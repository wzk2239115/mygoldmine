; Deserialization sinks for PHP
; Detects dangerous unserialize() calls, __wakeup(), and __destruct() methods

; unserialize() function call
(function_call_expression
  function: (name) @function
  arguments: (arguments) @args
  (#eq? @function "unserialize")
)

; Object deserialization with potentially dangerous methods
(method_declaration
  name: (name) @method_name
  (#match? @method_name "(__wakeup|__destruct|__unserialize)")
)

; Type juggling deserialization patterns
(function_call_expression
  function: (name) @function
  (#match? @function "^(json_decode|simplexml_load_string)$")
)

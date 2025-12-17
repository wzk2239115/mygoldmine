;; C Mass Assignment Sink Detection
;; Detects dangerous memory copy and structure assignment patterns

;; Function calls to dangerous functions
(call_expression
  function: (identifier) @func)
(#match? @func "^(memcpy|strcpy|strncpy|sprintf|snprintf|strcpy_s|strncpy_s|sprintf_s|snprintf_s)$")

;; memcpy with untrusted data
(call_expression
  function: (identifier) @func
  arguments: (argument_list
    (_) @dest
    (_) @src
    (_) @size))
(#match? @func "^memcpy$")

;; strcpy/strncpy operations
(call_expression
  function: (identifier) @func
  arguments: (argument_list
    (_) @dest
    (_) @src))
(#match? @func "^(strcpy|strncpy)$")

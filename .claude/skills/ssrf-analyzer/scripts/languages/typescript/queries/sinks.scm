;; TypeScript SSRF Sink Detection Queries
;; Same patterns as JavaScript since TypeScript is a superset

;; http/https module
(call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (identifier) @sink
  )
  (#match? @obj "^https?$")
  (#match? @sink "^(request|get|createConnection|createServer)$")
)

;; axios
(call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (identifier) @sink
  )
  (#match? @obj "^axios$")
  (#match? @sink "^(get|post|put|delete|patch|request|head)$")
)

;; fetch
(call_expression
  function: (identifier) @sink
  (#match? @sink "^fetch$")
)

;; XMLHttpRequest
(call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (identifier) @sink
  )
  (#match? @sink "^(open|send)$")
)

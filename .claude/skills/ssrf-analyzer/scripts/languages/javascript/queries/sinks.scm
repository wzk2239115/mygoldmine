;; JavaScript SSRF Sink Detection Queries
;; Detects dangerous HTTP request functions and methods

;; http.request() and http.get()
(call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (identifier) @sink
  )
  (#match? @obj "^https?$")
  (#match? @sink "^(request|get|createConnection|createServer)$")
)

;; axios methods
(call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (identifier) @sink
  )
  (#match? @obj "^axios$")
  (#match? @sink "^(get|post|put|delete|patch|request|head)$")
)

;; fetch function
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

;; got library
(call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (identifier) @sink
  )
  (#match? @obj "^got$")
  (#match? @sink "^(get|post|put|delete|patch|stream)$")
)

;; superagent
(call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (identifier) @sink
  )
  (#match? @obj "^request$")
  (#match? @sink "^(end|pipe)$")
)

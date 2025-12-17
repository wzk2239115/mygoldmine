;; Go SSRF Sink Detection Queries
;; Detects dangerous HTTP and network functions

;; http.Get, http.Post, etc
(call_expression
  function: (selector_expression
    operand: (identifier) @obj
    field: (identifier) @sink
  )
  (#match? @obj "^http$")
  (#match? @sink "^(Get|Post|Put|Delete|Head|Do)$")
)

;; net.Dial and related
(call_expression
  function: (selector_expression
    operand: (identifier) @obj
    field: (identifier) @sink
  )
  (#match? @obj "^net$")
  (#match? @sink "^(Dial|DialTCP|DialUDP|DialUnix|Listen)$")
)

;; net.LookupIP
(call_expression
  function: (selector_expression
    operand: (identifier) @obj
    field: (identifier) @sink
  )
  (#match? @obj "^net$")
  (#match? @sink "^(LookupIP|LookupHost|LookupAddr|LookupCNAME|LookupSRV|LookupMX)$")
)

;; url.Parse
(call_expression
  function: (selector_expression
    operand: (identifier) @obj
    field: (identifier) @sink
  )
  (#match? @obj "^url$")
  (#match? @sink "^Parse$")
)

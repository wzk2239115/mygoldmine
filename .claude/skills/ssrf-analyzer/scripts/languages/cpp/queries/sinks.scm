;; C++ SSRF Sink Detection Queries
;; Detects dangerous network and file access functions

;; curl functions
(call_expression
  function: (identifier) @sink
  (#match? @sink "^(curl_easy_perform|curl_easy_init|curl_easy_setopt)$")
)

;; Standard library streams
(call_expression
  function: (qualified_identifier
    scope: (namespace_identifier) @ns
    name: (identifier) @sink
  )
  (#match? @ns "^std$")
  (#match? @sink "^(ifstream|ofstream|fstream)$")
)

;; socket operations
(call_expression
  function: (identifier) @sink
  (#match? @sink "^(socket|connect|getaddrinfo|gethostbyname|inet_addr|gethostbyaddr)$")
)

;; ASIO library
(call_expression
  function: (qualified_identifier
    scope: (namespace_identifier) @ns
  )
  (#match? @ns "^asio$")
)

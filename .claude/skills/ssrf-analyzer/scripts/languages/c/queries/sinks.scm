;; C SSRF Sink Detection Queries
;; Detects dangerous network and file access functions

;; curl functions
(call_expression
  function: (identifier) @sink
  (#match? @sink "^(curl_easy_perform|curl_easy_init|curl_easy_setopt)$")
)

;; socket operations
(call_expression
  function: (identifier) @sink
  (#match? @sink "^(socket|connect|getaddrinfo|gethostbyname|inet_addr|gethostbyaddr)$")
)

;; file operations
(call_expression
  function: (identifier) @sink
  (#match? @sink "^(fopen|fread|fscanf|getc|fgets)$")
)

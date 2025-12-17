;; Java SSRF Sink Detection Queries
;; Detects dangerous HTTP request methods and URL operations

;; URL.openConnection()
(method_invocation
  object: (identifier) @obj
  method: (identifier) @sink
  (#match? @sink "^openConnection$")
)

;; URL.openStream()
(method_invocation
  object: (identifier) @obj
  method: (identifier) @sink
  (#match? @sink "^openStream$")
)

;; URLConnection.getInputStream()
(method_invocation
  object: (identifier) @obj
  method: (identifier) @sink
  (#match? @sink "^(getInputStream|connect)$")
)

;; RestTemplate methods
(method_invocation
  object: (identifier) @obj
  method: (identifier) @sink
  (#match? @obj "^restTemplate$")
  (#match? @sink "^(exchange|getForObject|getForEntity|postForObject|postForEntity|execute)$")
)

;; OkHttp client
(method_invocation
  object: (identifier) @obj
  method: (identifier) @sink
  (#match? @obj "^client$")
  (#match? @sink "^(newCall|execute)$")
)

;; HttpClient methods
(method_invocation
  object: (identifier) @obj
  method: (identifier) @sink
  (#match? @obj "^(httpClient|client)$")
  (#match? @sink "^(send|execute)$")
)

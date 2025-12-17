;; PHP SSRF Sink Detection Queries
;; Detects dangerous HTTP request functions

;; Simple function calls
(function_call_expression
  function: (name) @sink
  (#match? @sink "^(file_get_contents|fopen|readfile|curl_exec|curl_multi_exec|fsockopen|pfsockopen)$")
)


;; Rust SSRF Sink Detection Queries
;; Detects dangerous HTTP and network functions

;; reqwest library
(call_expression
  function: (field_expression
    value: (identifier) @obj
    field: (identifier) @sink
  )
  (#match? @obj "^reqwest$")
  (#match? @sink "^(get|post|put|delete|patch|head)$")
)

;; hyper library
(call_expression
  function: (field_expression
    value: (identifier) @obj
    field: (identifier) @sink
  )
  (#match? @obj "^hyper$")
)

;; std::net module
(call_expression
  function: (scoped_identifier
    path: (scoped_identifier
      path: (identifier) @ns
      name: (identifier) @module
    )
    name: (identifier) @sink
  )
  (#match? @ns "^std$")
  (#match? @module "^net$")
  (#match? @sink "^(TcpStream|UdpSocket|TcpListener)$")
)

;; tokio async runtime
(call_expression
  function: (field_expression
    value: (scoped_identifier
      path: (identifier) @obj
    )
    field: (identifier) @sink
  )
  (#match? @obj "^tokio$")
  (#match? @sink "^(net)$")
)

;; http crate
(call_expression
  function: (scoped_identifier
    path: (identifier) @obj
    name: (identifier) @sink
  )
  (#match? @obj "^http$")
)

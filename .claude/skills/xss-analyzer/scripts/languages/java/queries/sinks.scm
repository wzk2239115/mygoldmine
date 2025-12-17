;; Java XSS Sink Queries
;; 检测可能导致XSS的危险函数调用

;; response.getWriter().write() 和 response.getWriter().println()
(method_invocation
  object: (method_invocation
    object: (identifier) @obj
    name: (identifier) @method
    (#eq? @obj "response")
    (#eq? @method "getWriter")
  )
  name: (identifier) @sink_method
  (#match? @sink_method "^(write|println|print|append)$")
) @xss_sink_writer

;; response.getOutputStream().write()
(method_invocation
  object: (method_invocation
    object: (identifier) @obj
    name: (identifier) @method
    (#eq? @obj "response")
    (#eq? @method "getOutputStream")
  )
  name: (identifier) @sink_method
  (#match? @sink_method "^(write|append)$")
) @xss_sink_output_stream

;; HttpServletResponse.setHeader()
(method_invocation
  object: (identifier) @obj
  name: (identifier) @method
  (#match? @obj "^(response|resp|httpResponse)$")
  (#match? @method "^(setHeader|addHeader|sendRedirect)$")
) @xss_sink_set_header

;; Model.addAttribute() - 虽然Thymeleaf会转义，但需要监控
(method_invocation
  object: (identifier) @obj
  name: (identifier) @method
  (#match? @obj "^(model|Model)$")
  (#eq? @method "addAttribute")
) @xss_sink_model_attribute

;; System.out.println (用于日志可能被显示)
(method_invocation
  object: (field_access
    object: (identifier) @obj
    field: (identifier) @field
  )
  name: (identifier) @method
  (#eq? @obj "System")
  (#eq? @field "out")
  (#match? @method "^(println|print)$")
) @xss_sink_stdout

;; StringBuffer.append() 当用于构建HTML
(method_invocation
  object: (identifier) @obj
  name: (identifier) @method
  (#match? @obj "^(sb|buffer|html|content)$")
  (#eq? @method "append")
) @xss_sink_buffer_append

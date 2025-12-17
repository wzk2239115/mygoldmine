;; Python XSS Sink Queries
;; 检测可能导致XSS的危险函数调用

;; Flask/Django响应输出
(call
  function: (attribute
    object: (identifier) @obj
    attribute: (identifier) @method
    (#match? @method "^(write|render_template|render_template_string)$")
  )
) @xss_sink_response

;; print语句（用于Web框架）
(call
  function: (identifier) @func
  (#eq? @func "print")
) @xss_sink_print

;; 模板渲染
(call
  function: (attribute
    object: (identifier)
    attribute: (identifier) @method
    (#match? @method "^(render|format)$")
  )
) @xss_sink_template

;; eval和exec
(call
  function: (identifier) @func
  (#match? @func "^(eval|exec|compile)$")
) @xss_sink_eval

;; Response对象
(call
  function: (attribute
    object: (identifier) @obj
    attribute: (identifier) @method
    (#match? @method "^(set_data|set_cookie)$")
  )
) @xss_sink_response_obj

;; HTML.escape不使用的字符串输出
(call
  function: (identifier) @func
  (#match? @func "^(str|repr|format)$")
) @xss_sink_string_ops

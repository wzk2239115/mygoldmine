;; JavaScript XSS Sink Queries
;; 检测可能导致XSS的危险函数调用和属性赋值

;; innerHTML和outerHTML
(assignment_expression
  left: (member_expression
    object: (identifier)
    property: (property_identifier) @prop
    (#match? @prop "^(innerHTML|outerHTML)$")
  )
) @xss_sink_html_property

;; document.write和document.writeln
(call_expression
  function: (member_expression
    object: (member_expression
      object: (identifier) @obj
      property: (property_identifier) @method1
    )
    property: (property_identifier) @method2
    (#eq? @obj "document")
    (#match? @method2 "^(write|writeln)$")
  )
) @xss_sink_document_write

;; eval
(call_expression
  function: (identifier) @func
  (#eq? @func "eval")
) @xss_sink_eval

;; Function构造函数
(call_expression
  function: (identifier) @func
  (#eq? @func "Function")
) @xss_sink_function_constructor

;; setTimeout/setInterval with string
(call_expression
  function: (identifier) @func
  (#match? @func "^(setTimeout|setInterval)$")
) @xss_sink_timer

;; insertAdjacentHTML
(call_expression
  function: (member_expression
    object: (identifier)
    property: (property_identifier) @method
    (#eq? @method "insertAdjacentHTML")
  )
) @xss_sink_adjacent_html

;; textContent（低风险但监控）
(assignment_expression
  left: (member_expression
    object: (identifier)
    property: (property_identifier) @prop
    (#eq? @prop "textContent")
  )
) @xss_sink_text_content_assign

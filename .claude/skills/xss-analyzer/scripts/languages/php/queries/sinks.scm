;; PHP XSS Sink Queries
;; 检测可能导致XSS的危险函数调用

;; 直接输出函数（echo, print, var_dump等）
(function_call_expression
  function: (name) @sink
  (#match? @sink "^(echo|print|var_dump|print_r|var_export)$")
) @xss_sink_output

;; header()函数（Content-Type设置）
(function_call_expression
  function: (name) @sink
  (#eq? @sink "header")
) @xss_sink_header

;; 模板渲染函数（Blade, Twig等）
(function_call_expression
  function: (name) @sink
  (#match? @sink "^(render|view|display|output)$")
) @xss_sink_template

;; 动态代码执行
(function_call_expression
  function: (name) @sink
  (#match? @sink "^(eval|assert|create_function)$")
) @xss_sink_eval

;; 输出缓冲函数
(function_call_expression
  function: (name) @sink
  (#match? @sink "^(ob_get_contents|ob_get_clean|ob_get_flush)$")
) @xss_sink_output_buffer

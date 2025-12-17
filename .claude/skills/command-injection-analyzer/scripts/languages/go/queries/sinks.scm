(call_expression
  function: (identifier) @function
  arguments: (argument_list) @args)

(call_expression
  function: (selector_expression
    operand: (identifier)
    field: (field_identifier) @method)
  arguments: (argument_list) @args)

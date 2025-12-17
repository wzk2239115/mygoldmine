(call_expression
  function: (identifier) @function
  arguments: (arguments) @args)

(call_expression
  function: (member_expression
    object: (identifier)
    property: (property_identifier) @method)
  arguments: (arguments) @args)

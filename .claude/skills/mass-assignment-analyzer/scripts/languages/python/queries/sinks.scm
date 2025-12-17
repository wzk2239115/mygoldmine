;; Python Mass Assignment Sink Detection
;; Detects Django ORM, SQLAlchemy, and similar patterns

;; Django Model.objects.create() with keyword arguments
(call
  function: (attribute
    object: (attribute
      object: (identifier) @model
      attribute: (identifier) @objects)
    attribute: (identifier) @create_method)
  arguments: (argument_list
    (keyword_argument
      name: (identifier)
      value: (_) @data_source)))
(#match? @create_method "^(create|get_or_create|update_or_create)$")

;; Django Model.objects.create() with dict unpacking
(call
  function: (attribute
    object: (attribute
      object: (identifier) @model
      attribute: (identifier) @objects)
    attribute: (identifier) @method)
  arguments: (argument_list
    (dictionary
      (_) @data)))
(#match? @method "^(create|filter|update|bulk_create)$")

;; SQLAlchemy session.add() with model instantiation
(call
  function: (attribute
    object: (identifier) @session
    attribute: (identifier) @add_method)
  arguments: (argument_list
    (call
      function: (identifier) @model_class
      arguments: (argument_list
        (keyword_argument
          value: (_) @data)))))
(#match? @add_method "^(add|merge)$")

;; SQLAlchemy Model(**data) instantiation
(call
  function: (identifier) @model
  arguments: (argument_list
    (keyword_argument
      value: (identifier) @data)))

;; Direct attribute assignment in loop
(for_statement
  body: (block
    (expression_statement
      (assignment
        left: (attribute
          object: (identifier) @obj
          attribute: (identifier) @attr)
        right: (subscript
          value: (identifier) @data)))))

;; Pydantic model assignment with parse_obj
(call
  function: (attribute
    object: (identifier) @model
    attribute: (identifier) @parse_method)
  arguments: (argument_list
    (_) @data))
(#match? @parse_method "^(parse_obj|construct)$")

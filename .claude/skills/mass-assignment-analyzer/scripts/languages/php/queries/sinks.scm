;; PHP Mass Assignment Sink Detection
;; Detects dangerous ORM/framework methods that allow mass assignment

;; Function calls like create(), firstOrCreate()
(function_call_expression
  function: (name) @function
  arguments: (arguments
    (_) @data_source))
(#match? @function "^(create|firstOrCreate|firstOrCreateOrFail|updateOrCreate|forceCreate|make)$")

;; Member method calls (Object->method() or $obj->method())
(member_call_expression
  object: (_) @obj
  name: (name) @method
  arguments: (arguments
    (_) @data))
(#match? @method "^(fill|setAttribute|setAttributes|save|update|create|firstOrCreate|updateOrCreate)$")

;; Go Mass Assignment Sink Detection
;; Detects dangerous ORM and data binding patterns

;; GORM create/save operations
(call_expression
  function: (selector_expression
    operand: (identifier) @db
    field: (field_identifier) @method))
(#match? @method "^(Create|Save|Updates|CreateInBatches|Clauses|Model)$")

;; json.Unmarshal operations
(call_expression
  function: (selector_expression
    operand: (identifier) @pkg
    field: (field_identifier) @method))
(#match? @pkg "^json$")
(#match? @method "^(Unmarshal|UnmarshalJSON)$")

;; copier.Copy operations
(call_expression
  function: (selector_expression
    operand: (identifier) @pkg
    field: (field_identifier) @method))
(#match? @pkg "copier")
(#match? @method "Copy")

;; binary.Unmarshal operations
(call_expression
  function: (selector_expression
    operand: (identifier) @pkg
    field: (field_identifier) @method))
(#match? @pkg "binary")
(#match? @method "Unmarshal")

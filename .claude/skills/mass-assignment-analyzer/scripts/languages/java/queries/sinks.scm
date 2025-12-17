;; Java Mass Assignment Sink Detection
;; Detects Spring Data JPA, Hibernate, and similar patterns

;; Spring BeanUtils.copyProperties(source, target)
(method_invocation
  object: (identifier) @class
  name: (identifier) @method
  arguments: (argument_list
    (identifier) @source
    (identifier) @target))
(#match? @class "BeanUtils")
(#match? @method "copyProperties")

;; Hibernate/JPA entity.setProperty() patterns
(method_invocation
  object: (identifier) @entity
  name: (identifier) @setter
  arguments: (argument_list
    (_) @value))
(#match? @setter "^set[A-Z]")

;; Spring Data JPA save() with DTO mapping
(method_invocation
  object: (identifier) @repository
  name: (identifier) @save_method
  arguments: (argument_list
    (method_invocation
      object: (identifier) @mapper
      name: (identifier) @map_method
      arguments: (argument_list
        (_) @dto))))
(#match? @save_method "^(save|saveAll|saveAndFlush)$")

;; MapStruct mapping
(method_invocation
  object: (identifier) @mapper
  name: (identifier) @map_method
  arguments: (argument_list
    (_) @source))
(#match? @map_method "^(toEntity|fromDto)$")

;; ModelMapper
(method_invocation
  object: (identifier) @model_mapper
  name: (identifier) @map_method
  arguments: (argument_list
    (_) @source
    (class_literal) @target))
(#match? @map_method "map")

;; JPA @EntityListeners or direct entity property loop
(for_statement
  body: (block
    (expression_statement
      (method_invocation
        object: (identifier) @entity
        name: (identifier) @setter))))
(#match? @setter "^set[A-Z]")

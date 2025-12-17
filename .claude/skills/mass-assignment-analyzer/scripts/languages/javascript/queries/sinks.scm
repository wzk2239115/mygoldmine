;; JavaScript/TypeScript Mass Assignment Sink Detection
;; JavaScript/TypeScript Mass Assignment Sink Detection
;; Detects Sequelize, Mongoose, TypeORM, Prisma patterns

;; Basic patterns - match common mass assignment methods
(call_expression
  function: (member_expression
    object: (identifier) @model
    property: (property_identifier) @method)
  arguments: (arguments
    (_) @data))
(#match? @method "^(create|findByIdAndUpdate|update|updateOne|updateMany|findOneAndUpdate|save|assign)$")

;; Object.assign() pattern
(call_expression
  function: (member_expression
    object: (identifier) @object
    property: (property_identifier) @assign)
  arguments: (arguments
    (_) @target
    (_) @source))
(#match? @object "Object")
(#match? @assign "assign")

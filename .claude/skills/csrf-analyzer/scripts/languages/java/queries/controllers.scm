;; Java Spring POST endpoints - used for CSRF detection
;; Matches @PostMapping, @RequestMapping(method=POST), etc.

;; @PostMapping annotation
((modifiers
  (annotation
    name: (identifier) @anno_name
    arguments: (annotation_arguments
      (string_literal (string_fragment) @path)?
    )?
  )
) (#eq? @anno_name "PostMapping") @match)

;; @RequestMapping with POST method
((modifiers
  (annotation
    name: (identifier) @anno_name
    arguments: (annotation_arguments
      (member_value_pair
        key: (identifier) @key
        value: (member_value
          (field_access
            object: (identifier) @obj
            field: (identifier) @method
          )
        )
      )
    )
  )
) (#eq? @anno_name "RequestMapping") (#eq? @method "POST") @match)

;; @PutMapping annotation (state-changing)
((modifiers
  (annotation
    name: (identifier) @anno_name
  )
) (#eq? @anno_name "PutMapping") @match)

;; @DeleteMapping annotation (state-changing)
((modifiers
  (annotation
    name: (identifier) @anno_name
  )
) (#eq? @anno_name "DeleteMapping") @match)

;; @RequestMapping with explicit POST
((modifiers
  (annotation
    name: (identifier) @anno_name
    arguments: (annotation_arguments
      (member_value_pair
        key: (identifier) @key
        value: (array_literal
          (field_access
            object: (identifier) @obj
            field: (identifier) @method
          )
        )
      )
    )
  )
) (#eq? @anno_name "RequestMapping") (#eq? @method "POST") @match)

; Deserialization sinks for Python
; Detects dangerous pickle.loads(), yaml.load(), and related functions

; pickle.loads() and pickle.load()
(call
  function: (attribute
    object: (identifier) @module
    attribute: (identifier) @method
  ) @func
  (#match? @module "pickle|dill|cloudpickle")
  (#match? @method "^(loads|load)$")
)

; yaml.load() - potentially dangerous
(call
  function: (attribute
    object: (identifier) @module
    attribute: (identifier) @method
  ) @func
  (#eq? @module "yaml")
  (#match? @method "^(load|unsafe_load|full_load)$")
)

; marshal.loads()
(call
  function: (attribute
    object: (identifier) @module
    attribute: (identifier) @method
  ) @func
  (#eq? @module "marshal")
  (#match? @method "^(loads|load)$")
)

; shelve module operations
(call
  function: (attribute
    object: (identifier) @module
    attribute: (identifier) @method
  ) @func
  (#eq? @module "shelve")
  (#match? @method "^(open|DbfilenameShelf)$")
)

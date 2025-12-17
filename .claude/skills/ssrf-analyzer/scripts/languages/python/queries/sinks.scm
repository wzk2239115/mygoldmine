;; Python SSRF Sink Detection Queries
;; Simple patterns for dangerous HTTP functions

;; requests library functions like requests.get()
(call
  function: (attribute
    object: (identifier) @obj
    attribute: (identifier) @sink
  )
  (#match? @obj "^requests$")
  (#match? @sink "^(get|post|put|delete|patch|request|head|options)$")
)

;; urllib operations like urlopen()
(call
  function: (identifier) @sink
  (#match? @sink "^urlopen$")
)

;; Any call to common HTTP sink functions
(call
  function: (identifier) @sink
  (#match? @sink "^(urlopen|urlretrieve|getURL|getURL)$")
)


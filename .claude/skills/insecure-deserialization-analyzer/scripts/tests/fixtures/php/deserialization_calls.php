<?php
// Test fixtures for PHP deserialization vulnerabilities

// VULNERABLE: Direct unserialize() of user input
function vulnerable_unserialize($data) {
    return unserialize($data);
}

// VULNERABLE: unserialize() in constructor
class VulnerableClass {
    public function __construct($serialized_data) {
        $this->data = unserialize($serialized_data);
    }

    // Magic methods that are called during deserialization
    public function __wakeup() {
        echo "Object is being unserialized";
    }

    public function __destruct() {
        echo "Object is being destroyed";
    }
}

// VULNERABLE: unserialize with user input
if (isset($_GET['data'])) {
    $object = unserialize(base64_decode($_GET['data']));
}

// VULNERABLE: Type juggling with serialize()
class DangerousClass {
    public $command;

    public function __unserialize($data) {
        $this->command = $data['cmd'];
    }
}

// SEMI-VULNERABLE: json_decode can sometimes lead to deserialization issues
$json_data = json_decode($_POST['json'], true);

// SAFE: Using filter_var and validation before deserialization
function safe_example($data) {
    if (is_string($data) && preg_match('/^[a-zA-Z0-9]+$/', $data)) {
        return unserialize($data);
    }
}
?>

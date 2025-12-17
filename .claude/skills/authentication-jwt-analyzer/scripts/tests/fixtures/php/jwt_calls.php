<?php
// Test fixture: PHP JWT operations

use Firebase\JWT\JWT;
use Firebase\JWT\Key;

class AuthController {
    public function verifyToken($token) {
        try {
            // This should be detected as a JWT sink
            $decoded = JWT::decode($token, new Key('secret', 'HS256'));
            return $decoded;
        } catch (Exception $e) {
            return null;
        }
    }

    public function validateJWT($jwt) {
        // Another variant that should be detected
        $verified = $this->decoder->verify($jwt);
        return $verified;
    }

    public function processToken($input) {
        // Direct decode function call
        $payload = decode_token($input);
        return $payload;
    }
}

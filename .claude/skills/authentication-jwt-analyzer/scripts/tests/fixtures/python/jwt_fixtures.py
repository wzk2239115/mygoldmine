"""
Test fixtures for JWT sink detection.
"""

import jwt
from jwt import PyJWT

# Test 1: Direct jwt.decode() call
def verify_user_token(token):
    try:
        payload = jwt.decode(token, 'secret-key', algorithms=['HS256'])
        return payload
    except jwt.InvalidTokenError:
        return None

# Test 2: PyJWT instance
class TokenValidator:
    def __init__(self):
        self.encoder = PyJWT()

    def validate(self, token):
        # This should be detected as JWT sink
        data = self.encoder.decode(token, 'secret', algorithms=['HS256'])
        return data

# Test 3: jwt.verify() variant
def check_signature(token, key):
    # Another variant
    result = jwt.verify(token, key)
    return result

# Test 4: Token object pattern
class Token:
    def verify(self, token, secret):
        # Instance method that looks like JWT verify
        decoded = self.token.verify(token, secret)
        return decoded

# Test 5: Subscript access pattern
def process_auth_header(header):
    jwt_handlers = {
        'decode': jwt['decode'],
    }
    return jwt_handlers

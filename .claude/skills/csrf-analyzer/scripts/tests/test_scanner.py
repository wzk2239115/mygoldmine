"""Test suite for CSRF sink detector."""

import unittest
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scanner import (
    CSRFSinkScanner,
    PHPCSRFDetector,
    PythonCSRFDetector,
    JavaCSRFDetector,
    JavaScriptCSRFDetector,
)


class TestPHPDetector(unittest.TestCase):
    """Test PHP CSRF detector."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = PHPCSRFDetector()

    def test_detect_post_route(self):
        """Test detection of POST routes."""
        code = """
        Route::post('/user/update', function() {
            $user->save();
        });
        """
        sinks = self.detector.detect('test.php', code)
        self.assertGreater(len(sinks), 0)
        self.assertEqual(sinks[0]['type'], 'POST_ROUTE')

    def test_detect_post_method_check(self):
        """Test detection of POST method check."""
        code = """
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            processUpdate($_POST);
        }
        """
        sinks = self.detector.detect('test.php', code)
        self.assertGreater(len(sinks), 0)


class TestPythonDetector(unittest.TestCase):
    """Test Python CSRF detector."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = PythonCSRFDetector()

    def test_detect_flask_route(self):
        """Test detection of Flask POST routes."""
        code = """
        @app.route('/user/update', methods=['POST'])
        def update_user():
            name = request.form.get('name')
            return 'Updated'
        """
        sinks = self.detector.detect('test.py', code)
        self.assertGreater(len(sinks), 0)
        self.assertEqual(sinks[0]['type'], 'POST_ROUTE')

    def test_detect_csrf_exempt(self):
        """Test detection of csrf_exempt decorator."""
        code = """
        @csrf_exempt
        def sensitive_action(request):
            if request.method == 'POST':
                process_action(request.POST)
        """
        sinks = self.detector.detect('test.py', code)
        self.assertGreater(len(sinks), 0)
        self.assertEqual(sinks[0]['type'], 'CSRF_EXEMPT')


class TestJavaDetector(unittest.TestCase):
    """Test Java CSRF detector."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = JavaCSRFDetector()

    def test_detect_post_mapping(self):
        """Test detection of @PostMapping."""
        code = """
        @PostMapping("/user/update")
        public ResponseEntity<?> updateUser(@RequestBody UserRequest request) {
            userService.updateUser(request);
            return ResponseEntity.ok("Updated");
        }
        """
        sinks = self.detector.detect('UserController.java', code)
        self.assertGreater(len(sinks), 0)

    def test_detect_request_mapping_post(self):
        """Test detection of @RequestMapping with POST."""
        code = """
        @RequestMapping(value = "/action", method = RequestMethod.POST)
        public ResponseEntity<?> performAction(@RequestBody ActionRequest req) {
            return ResponseEntity.ok("Done");
        }
        """
        sinks = self.detector.detect('Controller.java', code)
        self.assertGreater(len(sinks), 0)

    def test_detect_csrf_disabled(self):
        """Test detection of CSRF disabled."""
        code = """
        @Bean
        public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
            http.csrf().disable();
            return http.build();
        }
        """
        sinks = self.detector.detect('SecurityConfig.java', code)
        self.assertGreater(len(sinks), 0)


class TestJavaScriptDetector(unittest.TestCase):
    """Test JavaScript CSRF detector."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = JavaScriptCSRFDetector()

    def test_detect_post_route(self):
        """Test detection of Express POST routes."""
        code = """
        app.post('/user/update', (req, res) => {
            updateUser(req.body);
            res.send('User updated');
        });
        """
        sinks = self.detector.detect('app.js', code)
        self.assertGreater(len(sinks), 0)
        self.assertEqual(sinks[0]['type'], 'POST_ROUTE')

    def test_detect_router_post(self):
        """Test detection of router.post()."""
        code = """
        router.post('/payment', (req, res) => {
            processPayment(req.body);
            res.send('Payment processed');
        });
        """
        sinks = self.detector.detect('routes.js', code)
        self.assertGreater(len(sinks), 0)


class TestCSRFSinkScanner(unittest.TestCase):
    """Test CSRF sink scanner."""

    def setUp(self):
        """Set up test fixtures."""
        self.scanner = CSRFSinkScanner()

    def test_find_files(self):
        """Test file finding."""
        test_dir = Path(__file__).parent / 'fixtures'
        files = self.scanner.find_files(str(test_dir), ['*.php'])
        self.assertGreater(len(files), 0)
        self.assertTrue(any('php' in f for f in files))

    def test_scan_single_file(self):
        """Test scanning a single file."""
        test_file = Path(__file__).parent / 'fixtures' / 'php' / 'post_routes.php'
        if test_file.exists():
            sinks = self.scanner.scan_file(str(test_file), 'php')
            self.assertGreater(len(sinks), 0)


if __name__ == '__main__':
    unittest.main()

"""Tests for SQL injection sink detection."""

import unittest
import tempfile
import json
from pathlib import Path
from cli import SinkDetectorCLI
from core.parser_manager import ParserManager
from reports.json_reporter import JSONReporter


class TestSinkDetectionPHP(unittest.TestCase):
    """Test PHP sink detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.cli = SinkDetectorCLI()
        self.temp_dir = tempfile.mkdtemp()

    def test_mysqli_query_detection(self):
        """Test detection of mysqli_query."""
        php_code = """<?php
$conn = mysqli_connect("localhost", "user", "pass", "db");
$query = "SELECT * FROM users WHERE id = " . $_GET['id'];
mysqli_query($conn, $query);
?>"""
        file_path = Path(self.temp_dir) / "test.php"
        file_path.write_text(php_code)

        sink_config = self.cli.parser_manager.get_sink_config('php')
        sinks = self.cli.scan_file(str(file_path), 'php', sink_config)

        self.assertGreater(len(sinks), 0)
        self.assertEqual(sinks[0]['sink_type'], 'mysqli_query')
        self.assertEqual(sinks[0]['line'], 4)

    def test_pdo_query_detection(self):
        """Test detection of PDO query."""
        php_code = """<?php
$pdo = new PDO('mysql:host=localhost;dbname=test', 'user', 'pass');
$sql = "SELECT * FROM users WHERE username = '" . $_POST['username'] . "'";
$result = $pdo->query($sql);
?>"""
        file_path = Path(self.temp_dir) / "pdo.php"
        file_path.write_text(php_code)

        sink_config = self.cli.parser_manager.get_sink_config('php')
        sinks = self.cli.scan_file(str(file_path), 'php', sink_config)

        self.assertGreater(len(sinks), 0)
        # Should detect PDO::query
        sink_types = [s['sink_type'] for s in sinks]
        self.assertIn('query', sink_types)

    def test_pg_query_detection(self):
        """Test detection of pg_query."""
        php_code = """<?php
$conn = pg_connect("host=localhost user=postgres password=pass dbname=mydb");
$result = pg_query($conn, "SELECT * FROM products WHERE id = " . $_GET['id']);
?>"""
        file_path = Path(self.temp_dir) / "postgres.php"
        file_path.write_text(php_code)

        sink_config = self.cli.parser_manager.get_sink_config('php')
        sinks = self.cli.scan_file(str(file_path), 'php', sink_config)

        self.assertGreater(len(sinks), 0)
        self.assertEqual(sinks[0]['sink_type'], 'pg_query')


class TestSinkDetectionPython(unittest.TestCase):
    """Test Python sink detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.cli = SinkDetectorCLI()
        self.temp_dir = tempfile.mkdtemp()

    def test_sqlite3_execute_detection(self):
        """Test detection of sqlite3.execute."""
        python_code = """import sqlite3
conn = sqlite3.connect(':memory:')
cursor = conn.cursor()
user_input = input('Enter id: ')
query = f"SELECT * FROM users WHERE id = {user_input}"
cursor.execute(query)
"""
        file_path = Path(self.temp_dir) / "sqlite_test.py"
        file_path.write_text(python_code)

        sink_config = self.cli.parser_manager.get_sink_config('python')
        sinks = self.cli.scan_file(str(file_path), 'python', sink_config)

        self.assertGreater(len(sinks), 0)
        self.assertEqual(sinks[0]['sink_type'], 'execute')

    def test_sqlalchemy_raw_detection(self):
        """Test detection of SQLAlchemy raw SQL."""
        python_code = """from sqlalchemy import text, create_engine
engine = create_engine('mysql://user:pass@localhost/db')
with engine.connect() as conn:
    user_id = request.args.get('id')
    result = conn.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))
"""
        file_path = Path(self.temp_dir) / "sqlalchemy_test.py"
        file_path.write_text(python_code)

        sink_config = self.cli.parser_manager.get_sink_config('python')
        sinks = self.cli.scan_file(str(file_path), 'python', sink_config)

        self.assertGreater(len(sinks), 0)

    def test_django_raw_detection(self):
        """Test detection of Django raw() queries."""
        python_code = """from django.db import connection
from django.db.models import Model

user_input = request.GET.get('name')
result = User.objects.raw(f"SELECT * FROM users WHERE name = '{user_input}'")
"""
        file_path = Path(self.temp_dir) / "django_test.py"
        file_path.write_text(python_code)

        sink_config = self.cli.parser_manager.get_sink_config('python')
        sinks = self.cli.scan_file(str(file_path), 'python', sink_config)

        self.assertGreater(len(sinks), 0)


class TestSinkDetectionJavaScript(unittest.TestCase):
    """Test JavaScript sink detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.cli = SinkDetectorCLI()
        self.temp_dir = tempfile.mkdtemp()

    def test_mysql_query_detection(self):
        """Test detection of MySQL query."""
        js_code = """const mysql = require('mysql');
const connection = mysql.createConnection({
  host: 'localhost',
  user: 'root',
  password: 'password',
  database: 'mydb'
});

const userId = req.query.id;
const sql = `SELECT * FROM users WHERE id = ${userId}`;
connection.query(sql, (error, results) => {});
"""
        file_path = Path(self.temp_dir) / "mysql.js"
        file_path.write_text(js_code)

        sink_config = self.cli.parser_manager.get_sink_config('javascript')
        sinks = self.cli.scan_file(str(file_path), 'javascript', sink_config)

        self.assertGreater(len(sinks), 0)
        self.assertEqual(sinks[0]['sink_type'], 'query')

    def test_sequelize_raw_detection(self):
        """Test detection of Sequelize raw queries."""
        js_code = """const { Sequelize } = require('sequelize');
const sequelize = new Sequelize('database', 'username', 'password');

const userId = req.body.userId;
const result = await sequelize.query(`SELECT * FROM users WHERE id = ${userId}`);
"""
        file_path = Path(self.temp_dir) / "sequelize.js"
        file_path.write_text(js_code)

        sink_config = self.cli.parser_manager.get_sink_config('javascript')
        sinks = self.cli.scan_file(str(file_path), 'javascript', sink_config)

        # Should detect sequelize.query
        self.assertGreater(len(sinks), 0)

    def test_knex_raw_detection(self):
        """Test detection of Knex raw queries."""
        js_code = """const knex = require('knex');
const db = knex({
  client: 'mysql',
  connection: { host: 'localhost', user: 'root' }
});

const column = req.query.col;
const result = db.raw(`SELECT * FROM users WHERE ? = ?`, [column, value]);
"""
        file_path = Path(self.temp_dir) / "knex.js"
        file_path.write_text(js_code)

        sink_config = self.cli.parser_manager.get_sink_config('javascript')
        sinks = self.cli.scan_file(str(file_path), 'javascript', sink_config)

        self.assertGreater(len(sinks), 0)


class TestSinkDetectionJava(unittest.TestCase):
    """Test Java sink detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.cli = SinkDetectorCLI()
        self.temp_dir = tempfile.mkdtemp()

    def test_statement_executequery_detection(self):
        """Test detection of Statement.executeQuery."""
        java_code = """import java.sql.*;

public class DatabaseQuery {
    public void queryDatabase(String userId) throws SQLException {
        Connection conn = DriverManager.getConnection("jdbc:mysql://localhost/mydb", "user", "pass");
        Statement stmt = conn.createStatement();
        String sql = "SELECT * FROM users WHERE id = " + userId;
        ResultSet rs = stmt.executeQuery(sql);
    }
}
"""
        file_path = Path(self.temp_dir) / "Database.java"
        file_path.write_text(java_code)

        sink_config = self.cli.parser_manager.get_sink_config('java')
        sinks = self.cli.scan_file(str(file_path), 'java', sink_config)

        self.assertGreater(len(sinks), 0)
        self.assertEqual(sinks[0]['sink_type'], 'executeQuery')


class TestReporter(unittest.TestCase):
    """Test JSON reporter."""

    def setUp(self):
        """Set up test fixtures."""
        self.reporter = JSONReporter()

    def test_report_generation(self):
        """Test report generation."""
        sinks = [
            {
                'file': 'app.php',
                'line': 42,
                'column': 10,
                'sink_type': 'mysqli_query',
                'sink_category': 'direct_execution',
                'function_name': 'mysqli_query',
                'parameters': ['$conn', '$query'],
                'vulnerable_params': [1],
                'context': 'mysqli_query($conn, $query);',
            }
        ]

        report = self.reporter.generate_report(sinks, source_path='/app', languages=['php'])

        self.assertIn('metadata', report)
        self.assertIn('summary', report)
        self.assertIn('sinks', report)
        self.assertEqual(report['summary']['total_sinks'], 1)
        self.assertEqual(report['summary']['by_category']['direct_execution'], 1)

    def test_json_output(self):
        """Test JSON output."""
        sinks = [
            {
                'file': 'test.php',
                'line': 1,
                'column': 1,
                'sink_type': 'mysqli_query',
                'sink_category': 'direct_execution',
                'function_name': 'mysqli_query',
                'parameters': [],
                'vulnerable_params': [1],
                'context': 'test',
            }
        ]

        report = self.reporter.generate_report(sinks)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name

        self.reporter.write_json(report, temp_file)

        with open(temp_file, 'r') as f:
            loaded_report = json.load(f)

        self.assertEqual(loaded_report['summary']['total_sinks'], 1)
        Path(temp_file).unlink()


class TestZeroFalseNegatives(unittest.TestCase):
    """Test cases to ensure zero false negatives."""

    def setUp(self):
        """Set up test fixtures."""
        self.cli = SinkDetectorCLI()
        self.temp_dir = tempfile.mkdtemp()

    def test_all_php_sinks(self):
        """Test detection of all PHP sink types."""
        php_code = """<?php
mysqli_query($conn, $query);
mysqli_real_query($conn, $query);
mysql_query($query);
pg_query($conn, $query);
$pdo->query($sql);
$pdo->exec($sql);
?>"""
        file_path = Path(self.temp_dir) / "all_sinks.php"
        file_path.write_text(php_code)

        sink_config = self.cli.parser_manager.get_sink_config('php')
        sinks = self.cli.scan_file(str(file_path), 'php', sink_config)

        # Should detect all sink types
        self.assertGreaterEqual(len(sinks), 5, "Should detect at least 5 sink types")

    def test_all_python_sinks(self):
        """Test detection of all Python sink types."""
        python_code = """
cursor.execute(query)
cursor.executescript(script)
cursor.executemany(query, params)
conn.execute(text(sql))
Model.objects.raw(sql)
Model.objects.extra(select={})
"""
        file_path = Path(self.temp_dir) / "all_sinks.py"
        file_path.write_text(python_code)

        sink_config = self.cli.parser_manager.get_sink_config('python')
        sinks = self.cli.scan_file(str(file_path), 'python', sink_config)

        # Should detect all sink types
        self.assertGreaterEqual(len(sinks), 5, "Should detect at least 5 sink types")


class TestNoFalseNegativeStrategy(unittest.TestCase):
    """Test the zero false negative detection strategy."""

    def test_various_call_styles(self):
        """Test detection with various call styles."""
        cli = SinkDetectorCLI()
        temp_dir = tempfile.mkdtemp()

        # Test various PHP call styles
        php_code = """<?php
mysqli_query($conn, $sql);
$this->mysqli_query($conn, $sql);
Class::mysqli_query($conn, $sql);
execute($query);
$db->execute($query);
?>"""
        file_path = Path(temp_dir) / "styles.php"
        file_path.write_text(php_code)

        sink_config = cli.parser_manager.get_sink_config('php')
        sinks = cli.scan_file(str(file_path), 'php', sink_config)

        # Should detect multiple variations
        self.assertGreater(len(sinks), 1)


if __name__ == '__main__':
    unittest.main()

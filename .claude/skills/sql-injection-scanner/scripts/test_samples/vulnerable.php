<?php
// Sample vulnerable PHP code for testing

// Test 1: mysqli_query
$conn = mysqli_connect("localhost", "user", "password", "database");
$user_id = $_GET['id'];
$query = "SELECT * FROM users WHERE id = " . $user_id;
$result = mysqli_query($conn, $query);

// Test 2: PDO query
$pdo = new PDO('mysql:host=localhost;dbname=test');
$username = $_POST['username'];
$sql = "SELECT * FROM users WHERE username = '" . $username . "'";
$result = $pdo->query($sql);

// Test 3: mysqli_real_query
$search = $_GET['search'];
mysqli_real_query($conn, "SELECT * FROM products WHERE name LIKE '%$search%'");

// Test 4: PostgreSQL pg_query
$pg_conn = pg_connect("host=localhost");
$table = $_GET['table'];
pg_query($pg_conn, "SELECT * FROM " . $table);

// Test 5: PDO exec
$delete_query = "DELETE FROM users WHERE id = " . $_GET['uid'];
$pdo->exec($delete_query);
?>

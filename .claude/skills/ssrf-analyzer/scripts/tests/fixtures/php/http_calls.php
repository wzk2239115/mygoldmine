<?php

// SSRF vulnerable code examples

// Example 1: file_get_contents with user input
$url = $_GET['url'];
$content = file_get_contents($url);  // VULNERABLE

// Example 2: fopen with user input
$file = $_POST['file'];
$handle = fopen($file, 'r');  // VULNERABLE

// Example 3: curl_exec with user input
$curl_url = $_REQUEST['url'];
$ch = curl_init($curl_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$result = curl_exec($ch);  // VULNERABLE

// Example 4: readfile with user input
$file_path = $_GET['file'];
readfile($file_path);  // VULNERABLE

// Example 5: fsockopen with user input
$host = $_GET['host'];
$port = $_GET['port'];
$fp = fsockopen($host, $port);  // VULNERABLE

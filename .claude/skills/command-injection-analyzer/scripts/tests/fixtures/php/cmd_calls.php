<?php
// Vulnerable command injection examples

// Direct system execution
$filename = $_GET['file'];
system("cat /tmp/" . $filename);

// Using exec
$command = $_POST['cmd'];
exec($command, $output);

// Shell execution
$userInput = $_GET['search'];
$result = shell_exec("grep -r '$userInput' /var/www");

// Process control
$command = "ping -c 5 " . $_GET['host'];
popen($command, 'r');

// Backtick operator
$version = `python --version`;

// exec with unescaped input
$host = $_GET['hostname'];
exec("nslookup " . $host);

// passthru - passes output directly
passthru("ls -la " . $_GET['dir']);

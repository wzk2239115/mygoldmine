<?php
// POST route with form handling
Route::post('/user/update', function() {
    // Update user data
    $user->name = $_POST['name'];
    $user->save();
});

// POST route without explicit protection
app('router')->post('/admin/delete', 'AdminController@delete');

// Direct POST handling
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Process form submission
    $action = $_POST['action'];
}

// Vulnerable: missing CSRF token verification
function handlePostRequest() {
    if (!empty($_POST['token'])) {
        // Only checks existence, not validity
        processUpdate($_POST);
    }
}

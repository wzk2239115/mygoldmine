<?php
// PHP Test Fixtures - Mass Assignment Vulnerabilities

namespace App\Http\Controllers;

use App\Models\User;
use Illuminate\Http\Request;

class UserController extends Controller
{
    // VULNERABLE: Direct create() with request data
    public function store(Request $request)
    {
        $user = User::create($request->all());
        return response()->json($user);
    }

    // VULNERABLE: fill() method with user input
    public function update(Request $request, $id)
    {
        $user = User::find($id);
        $user->fill($request->all());
        $user->save();
        return response()->json($user);
    }

    // VULNERABLE: firstOrCreate with user data
    public function getOrCreate(Request $request)
    {
        $user = User::firstOrCreate($request->all());
        return response()->json($user);
    }

    // VULNERABLE: updateOrCreate with user data
    public function upsert(Request $request, $id)
    {
        $user = User::updateOrCreate(
            ['id' => $id],
            $request->all()
        );
        return response()->json($user);
    }

    // VULNERABLE: Direct property assignment in loop
    public function bulkUpdate(Request $request)
    {
        $data = $request->all();
        foreach ($data['users'] as $userData) {
            $user = new User();
            foreach ($userData as $key => $value) {
                $user->$key = $value;
            }
            $user->save();
        }
    }

    // VULNERABLE: setAttribute method
    public function setAttribute(Request $request)
    {
        $user = User::find($request->id);
        foreach ($request->all() as $key => $value) {
            $user->setAttribute($key, $value);
        }
        $user->save();
    }

    // SAFE: Explicitly set only allowed fields
    public function storeSafe(Request $request)
    {
        $user = User::create([
            'name' => $request->input('name'),
            'email' => $request->input('email'),
        ]);
        return response()->json($user);
    }
}

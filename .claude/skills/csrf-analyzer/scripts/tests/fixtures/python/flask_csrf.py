from flask import Flask, request
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

app = Flask(__name__)

# Flask POST route
@app.route('/user/update', methods=['POST'])
def update_user():
    name = request.form.get('name')
    # Update user without CSRF token verification
    return 'Updated'

# Flask route without explicit methods (accepts all)
@app.route('/admin/delete')
def delete_admin():
    # This could be vulnerable
    return 'Deleted'

# Django view with CSRF exempt (suspicious)
@csrf_exempt
def sensitive_action(request):
    if request.method == 'POST':
        # Dangerous: CSRF protection explicitly disabled
        process_action(request.POST)
    return HttpResponse('Done')

# Flask route with POST handling
@app.route('/api/settings', methods=['POST'])
def update_settings():
    settings = request.get_json()
    # Missing CSRF token check
    save_settings(settings)
    return {'status': 'ok'}

# Vulnerable token check
@app.route('/change-password', methods=['POST'])
def change_password():
    # Only checks if token exists, not validity
    if 'csrf_token' in request.form:
        update_password(request.form.get('password'))
    return 'Password changed'

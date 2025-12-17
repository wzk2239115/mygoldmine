const express = require('express');
const app = express();

// Express POST route
app.post('/user/update', (req, res) => {
    // Update user without CSRF token verification
    const user = req.body;
    updateUser(user);
    res.send('User updated');
});

// Express PUT route (state-changing)
app.put('/api/settings', (req, res) => {
    // Update settings
    updateSettings(req.body);
    res.json({ status: 'ok' });
});

// Express DELETE route (state-changing)
app.delete('/api/user/:id', (req, res) => {
    deleteUser(req.params.id);
    res.json({ deleted: true });
});

// Router POST route
const router = express.Router();

router.post('/payment', (req, res) => {
    // Process payment without CSRF protection
    processPayment(req.body);
    res.send('Payment processed');
});

// Vulnerable: no CSRF token check
app.post('/change-password', (req, res) => {
    const newPassword = req.body.password;

    // Only checks if password exists
    if (newPassword) {
        updatePassword(req.user.id, newPassword);
        res.send('Password changed');
    }
});

app.use(router);

// Koa example
const Koa = require('koa');
const koaApp = new Koa();

koaApp.use(async (ctx) => {
    if (ctx.method === 'POST' && ctx.path === '/action') {
        // Handle action without CSRF verification
        await processAction(ctx.request.body);
        ctx.body = 'Action completed';
    }
});

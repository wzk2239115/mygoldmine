/**
 * Test fixtures for JavaScript deserialization vulnerabilities
 */

const vm = require('vm');

// VULNERABLE: vm.runInContext()
function vulnerableRunInContext(code, context) {
    return vm.runInContext(code, context);
}

// VULNERABLE: vm.runInNewContext()
function vulnerableRunInNewContext(code, context) {
    return vm.runInNewContext(code, context);
}

// VULNERABLE: vm.run()
function vulnerableRun(code) {
    const script = new vm.Script(code);
    return script.runInThisContext();
}

// VULNERABLE: eval() with user input
function vulnerableEval(data) {
    return eval(data);
}

// VULNERABLE: Function constructor
function vulnerableFunction(code) {
    return new Function(code)();
}

// VULNERABLE: Function constructor with dynamic arguments
function vulnerableFunctionWithArgs(args, body) {
    return new Function(...args, body)();
}

// VULNERABLE: setTimeout with string code
function vulnerableSetTimeout(code, delay) {
    setTimeout(code, delay);
}

// VULNERABLE: setInterval with string code
function vulnerableSetInterval(code, interval) {
    setInterval(code, interval);
}

// VULNERABLE: require() with dynamic path
function vulnerableRequire(modulePath) {
    return require(modulePath);
}

// VULNERABLE: Dynamic import
async function vulnerableDynamicImport(modulePath) {
    return import(modulePath);
}

// VULNERABLE: eval in JSON.parse reviver (can execute code)
function vulnerableJSONParse(jsonString) {
    return JSON.parse(jsonString, (key, value) => {
        if (key === 'code') {
            return eval(value);  // This executes arbitrary code
        }
        return value;
    });
}

// VULNERABLE: Object.assign can merge malicious properties
function vulnerableObjectAssign(target, source) {
    return Object.assign(target, source);
}

// SEMI-VULNERABLE: Using vm without proper context isolation
function semiVulnerableVM(code) {
    const sandbox = {};
    vm.createContext(sandbox);
    return vm.runInContext(code, sandbox, {timeout: 1000});
}

// SAFE: Validating input before eval
function safeExample(data) {
    // Only allow numeric operations
    if (/^[\d\s+\-*/()]+$/.test(data)) {
        return eval(data);
    }
    throw new Error('Invalid input');
}

// SAFE: Using JSON.parse without eval
function safeParse(jsonString) {
    return JSON.parse(jsonString);
}

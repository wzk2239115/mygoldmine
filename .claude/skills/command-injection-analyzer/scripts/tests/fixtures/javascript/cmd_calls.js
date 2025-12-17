const { exec, execSync, spawn } = require('child_process');

// Using exec
const filename = process.argv[2];
exec(`cat /tmp/${filename}`, (error, stdout, stderr) => {
    console.log(stdout);
});

// Using execSync
const hostname = process.argv[3];
const result = execSync(`ping -c 5 ${hostname}`);

// Using spawn with shell
const command = process.argv[4];
const child = spawn('sh', ['-c', command]);

// Using exec with user input
const userInput = process.argv[5];
exec(`grep -r '${userInput}' /var/www`, (err, out) => {
    console.log(out);
});

// execFile (safer - doesn't use shell by default)
const { execFile } = require('child_process');
execFile('cat', [`/tmp/${filename}`], (err, stdout) => {
    console.log(stdout);
});

// spawnSync
const { spawnSync } = require('child_process');
spawnSync('sh', ['-c', `ls -la ${process.argv[6]}`]);

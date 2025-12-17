#!/usr/bin/env python3
# Vulnerable command injection examples

import os
import subprocess
import sys

# Using os.system
user_input = sys.argv[1]
os.system(f"echo {user_input}")

# Using os.popen
filename = input("Enter filename: ")
os.popen(f"cat {filename}")

# Using subprocess.run with shell=True
command = sys.argv[1]
subprocess.run(command, shell=True)

# Using subprocess.Popen
user_dir = input("Directory: ")
subprocess.Popen(f"ls -la {user_dir}", shell=True)

# Using subprocess.call
search_term = sys.argv[1]
subprocess.call(f"grep -r '{search_term}' /var/www", shell=True)

# Using subprocess.check_output
hostname = input("Hostname: ")
result = subprocess.check_output(f"ping -c 5 {hostname}", shell=True)

# os.execv with user input
cmd = sys.argv[1]
os.execv('/bin/sh', ['/bin/sh', '-c', cmd])

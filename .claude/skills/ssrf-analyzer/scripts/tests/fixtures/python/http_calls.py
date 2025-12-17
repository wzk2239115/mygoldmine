"""Python SSRF vulnerable code examples for testing."""

import requests
import urllib.request
from urllib.request import urlopen
import socket
from http.client import HTTPConnection, HTTPSConnection

# Example 1: requests.get with user input
url = input("Enter URL: ")
response = requests.get(url)  # VULNERABLE

# Example 2: requests.post with user input
user_url = input("URL: ")
response = requests.post(user_url, data={'key': 'value'})  # VULNERABLE

# Example 3: urllib.request.urlopen with user input
target_url = input("Target: ")
response = urllib.request.urlopen(target_url)  # VULNERABLE

# Example 4: urlopen shorthand
url = input("Enter URL: ")
content = urlopen(url)  # VULNERABLE

# Example 5: HTTPConnection with user input
host = input("Host: ")
conn = HTTPConnection(host)
conn.request("GET", "/")  # VULNERABLE

# Example 6: socket.create_connection
address = input("Address: ")
sock = socket.create_connection(address)  # VULNERABLE

# Example 7: requests.request with user input
method = input("Method: ")
url = input("URL: ")
response = requests.request(method, url)  # VULNERABLE

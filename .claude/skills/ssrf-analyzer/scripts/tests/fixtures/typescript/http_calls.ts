// TypeScript example - SSRF vulnerabilities

import axios from 'axios';
import * as http from 'http';
import * as https from 'https';

// VULNERABLE: axios.get with user input
async function fetchUserData(userUrl: string): Promise<void> {
    try {
        const response = await axios.get(userUrl);  // VULNERABLE
        console.log(response.data);
    } catch (error) {
        console.error('Error:', error);
    }
}

// VULNERABLE: fetch with user input
async function fetchData(url: string): Promise<void> {
    const response = await fetch(url);  // VULNERABLE
    const data = await response.json();
    console.log(data);
}

// VULNERABLE: http.get
function makeHttpRequest(url: string): void {
    http.get(url, (response) => {  // VULNERABLE
        console.log(`Got response: ${response.statusCode}`);
    });
}

// VULNERABLE: XMLHttpRequest
function xmlHttpRequest(url: string): void {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url);  // VULNERABLE
    xhr.send();
}

export { fetchUserData, fetchData, makeHttpRequest, xmlHttpRequest };

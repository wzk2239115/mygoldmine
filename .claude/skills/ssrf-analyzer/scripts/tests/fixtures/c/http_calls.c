#include <stdio.h>
#include <curl/curl.h>
#include <sys/socket.h>
#include <netdb.h>

int main() {
    // VULNERABLE: curl operations
    CURL *curl = curl_easy_init();
    if(curl) {
        curl_easy_setopt(curl, CURLOPT_URL, "http://example.com");
        curl_easy_perform(curl);  // VULNERABLE
    }

    // VULNERABLE: socket operations
    int sock = socket(AF_INET, SOCK_STREAM, 0);

    struct hostent *host = gethostbyname("example.com");  // VULNERABLE

    struct addrinfo hints, *result;
    getaddrinfo("example.com", "80", &hints, &result);  // VULNERABLE

    // VULNERABLE: file operations
    FILE *file = fopen("remote_file.txt", "r");

    return 0;
}

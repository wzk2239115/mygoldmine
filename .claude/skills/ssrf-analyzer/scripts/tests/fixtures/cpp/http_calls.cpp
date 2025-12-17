#include <iostream>
#include <fstream>
#include <curl/curl.h>
#include <sys/socket.h>

int main() {
    // VULNERABLE: C++ file stream
    std::ifstream infile("remote_file.txt");
    std::string content((std::istreambuf_iterator<char>(infile)),
                        std::istreambuf_iterator<char>());

    // VULNERABLE: curl operations
    CURL *curl = curl_easy_init();
    if(curl) {
        curl_easy_perform(curl);  // VULNERABLE
    }

    // VULNERABLE: socket operations
    int sock = socket(AF_INET, SOCK_STREAM, 0);

    return 0;
}

package main

import (
	"fmt"
	"net/http"
)

func main() {
	// VULNERABLE: Using user input in http.Get
	userURL := "http://example.com"
	resp, err := http.Get(userURL)
	if err != nil {
		fmt.Println("Error:", err)
		return
	}
	defer resp.Body.Close()
}

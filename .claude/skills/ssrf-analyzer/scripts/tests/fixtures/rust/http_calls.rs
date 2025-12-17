use reqwest::Client;
use std::net::TcpStream;

#[tokio::main]
async fn main() {
    // VULNERABLE: Using user input in reqwest
    let client = Client::new();
    let user_url = "http://example.com";

    match client.get(user_url).send().await {
        Ok(response) => println!("Status: {}", response.status()),
        Err(e) => println!("Error: {}", e),
    }

    // VULNERABLE: Direct TCP connection
    match TcpStream::connect("127.0.0.1:8080") {
        Ok(_) => println!("Connected"),
        Err(e) => println!("Error: {}", e),
    }
}

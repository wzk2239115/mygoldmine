use std::process::Command;
use std::process::Stdio;

fn main() {
    // Command with user input
    let filename = std::env::args().nth(1).unwrap_or_default();
    let output = Command::new("cat")
        .arg(format!("/tmp/{}", filename))
        .output()
        .expect("Failed to execute");

    // Using shell with arguments
    let hostname = std::env::args().nth(2).unwrap_or_default();
    let output = Command::new("sh")
        .arg("-c")
        .arg(format!("ping -c 5 {}", hostname))
        .output()
        .expect("Failed to execute");

    // Using spawn
    let user_input = std::env::args().nth(3).unwrap_or_default();
    let child = Command::new("grep")
        .args(&["-r", &user_input, "/var/www"])
        .spawn()
        .expect("Failed to spawn");

    // Using status
    let dir = std::env::args().nth(4).unwrap_or_default();
    let status = Command::new("ls")
        .arg(format!("-la {}", dir))
        .status()
        .expect("Failed to get status");

    // Using CombinedOutput equivalent
    let search = std::env::args().nth(5).unwrap_or_default();
    Command::new("sh")
        .arg("-c")
        .arg(format!("find /tmp -name '*{}*'", search))
        .output()
        .expect("Failed to execute");
}

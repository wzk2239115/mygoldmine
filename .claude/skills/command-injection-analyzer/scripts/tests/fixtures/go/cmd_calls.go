package main

import (
	"fmt"
	"os"
	"os/exec"
	"log"
)

func main() {
	// os/exec Command with user input
	filename := os.Args[1]
	cmd := exec.Command("cat", "/tmp/" + filename)
	cmd.Run()

	// Using shell
	hostname := os.Args[2]
	cmd = exec.Command("sh", "-c", fmt.Sprintf("ping -c 5 %s", hostname))
	output, _ := cmd.Output()
	fmt.Println(string(output))

	// execSync equivalent
	userInput := os.Args[3]
	cmd = exec.Command("grep", "-r", userInput, "/var/www")
	out, _ := cmd.CombinedOutput()
	fmt.Println(string(out))

	// Using Command with string concatenation (vulnerable)
	search := os.Args[4]
	cmd = exec.Command("sh", "-c", "find /tmp -name '*" + search + "*'")
	cmd.Run()
}

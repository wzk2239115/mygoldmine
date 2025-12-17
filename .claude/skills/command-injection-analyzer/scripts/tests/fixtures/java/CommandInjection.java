import java.io.IOException;
import java.io.BufferedReader;
import java.io.InputStreamReader;

public class CommandInjection {
    public static void main(String[] args) throws IOException {
        // Runtime.exec with user input
        String filename = args[0];
        Runtime.getRuntime().exec("cat /tmp/" + filename);

        // Runtime.exec with command array (safer)
        Runtime.getRuntime().exec(new String[]{"cat", "/tmp/" + filename});

        // ProcessBuilder with user input
        String hostname = args[1];
        new ProcessBuilder("ping", "-c", "5", hostname).start();

        // ProcessBuilder with shell command
        String command = args[2];
        new ProcessBuilder("/bin/sh", "-c", command).start();

        // Runtime.exec with shell wrapping
        String userInput = args[3];
        Runtime.getRuntime().exec(new String[]{"/bin/bash", "-c", "grep -r " + userInput + " /var/www"});
    }
}

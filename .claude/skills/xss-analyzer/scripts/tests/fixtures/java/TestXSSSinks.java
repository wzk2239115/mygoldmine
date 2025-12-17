// XSS Sink测试文件 - Java

import javax.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class XSSSinkTestController {

    @GetMapping("/test")
    public String testXSSSinks(String userInput, HttpServletResponse response) throws Exception {
        // response.getWriter().write() - 高危
        response.getWriter().write(userInput);
        response.getWriter().println(userInput);
        response.getWriter().append("<div>" + userInput + "</div>");

        // response.getOutputStream() - 危险
        response.getOutputStream().write(userInput.getBytes());

        // setHeader - 可能导致HTTP头注入
        response.setHeader("X-Custom-Header", userInput);
        response.addHeader("Set-Cookie", userInput);

        // sendRedirect - 开放重定向风险
        response.sendRedirect(userInput);

        return "redirect:" + userInput;
    }

    @GetMapping("/model")
    public String testModelAttribute(String data, Model model) {
        // Model.addAttribute - 需要监控（Thymeleaf会转义）
        model.addAttribute("content", data);
        model.addAttribute("userInput", data);

        return "template";
    }

    @GetMapping("/buffer")
    public String testStringBuffer(String input) {
        // StringBuffer.append - 用于构建HTML时危险
        StringBuffer sb = new StringBuffer();
        sb.append("<html>");
        sb.append("<div>");
        sb.append(input);  // 高危
        sb.append("</div>");
        sb.append("</html>");

        System.out.println(sb.toString());  // 日志输出
        return sb.toString();
    }

    @GetMapping("/stdout")
    public void testStdout(String message) {
        // System.out.println - 可能被看到
        System.out.println("User message: " + message);
        System.out.print(message);
    }
}

# Java 登录后 returnUrl 重定向未验证

## Details

### 核心代码示例

登录成功后根据 returnUrl 参数重定向，未进行目标地址验证的典型表现：

```java
// 危险模式：直接使用用户输入进行重定向
@PostMapping("/login")
public String login(String username, String password, String returnUrl, HttpServletResponse response) {
    if (authenticate(username, password)) {
        // 【审计重点】未验证 returnUrl 合法性，攻击者可指向恶意域名
        response.sendRedirect(returnUrl);
        return null;
    }
    return "login";
}
```

**快速定位到核心操作的技巧** 【L1:关键词扫描】
- 扫描 `returnUrl`、`redirect`、`referrer` 等参数名称
- 查找 `sendRedirect()`、`forward()`、`RedirectView` 等重定向方法调用
- 定位参数从请求中取值的源头（`getParameter()`、`getAttribute()` 等）
- 观察登录验证成功分支中是否存在重定向逻辑

**快速定位到保护机制的技巧** 【L2:跳读】
- 检查重定向前是否存在 URL 验证逻辑（whitelist/blacklist）
- 查找是否有 `isValidRedirectUrl()`、`isSafeUrl()` 等验证方法
- 检查是否限制重定向目标为相对 URL（`startsWith("/")`）或本站域名
- 查看是否使用了安全库（如 Spring Security 的 `RedirectView`）进行自动转义
- 查找配置文件中是否定义了允许的重定向域名列表

## Classify

### 研判流程

1. **确认参数来源**：returnUrl 是否完全来自用户输入（GET/POST/Cookie）
2. **检查验证策略**：
   - 无任何验证 → 确认漏洞
   - 仅检查格式（如 isURI）→ 代码异味（格式检查不能防止跨域重定向）
   - 仅客户端验证 → 代码异味（易被绕过）
   - 使用白名单验证本站域名 → 安全
3. **考察业务上下文**：
   - 认证流程中的重定向是否必要？
   - 是否必须支持任意 URL 重定向？
4. **验证绕过可能**：
   - URL 编码：`returnUrl=http%3A%2F%2Fevil.com`
   - 协议利用：`//evil.com`、`javascript:alert()`
   - 相对路径：`../../evil.com` 或 `evil.com@yoursite.com`

### 漏洞判定标准

**确认漏洞**：无任何验证或仅进行弱验证，允许跨域重定向至外部网站

**误报情形**：
- returnUrl 为固定值，非用户输入
- 通过白名单方式限制为本域 URL
- 强制转换为相对 URL（如 `if (!url.startsWith("/")) throw error`）

**代码异味**：
- 仅进行格式或协议检查，缺少域名验证
- 存在客户端脚本验证但无服务端校验
- 验证逻辑过于简单（如仅检查 `!url.contains("://")` 绕过 `//` 形式）

## Low risk

### 低风险评级条件

1. **严格的白名单控制**
   - 使用显式域名列表或正则表达式，仅允许特定域名
   - 白名单采用黑盒测试方式穷举验证

2. **强制相对 URL**
   - returnUrl 限制为 `/` 开头的相对路径
   - 且服务器未配置 URL rewriting 规则可逃逸

3. **框架级自动保护**
   - 使用 Spring Security RedirectView 等框架组件
   - 框架已内置对相对 URL 的自动转换

4. **业务风险评估**
   - 重定向目标仅为本组织内其他系统，且信任关系明确
   - 用户可自行意识到点击链接的风险（如登录后的欢迎页面提示）

5. **额外防御层**
   - 结合 HTTP-only Cookie、同源策略等防御
   - 虽不能彻底阻止重定向，但可降低利用价值

### 审计关注点

即使为低风险，仍需确认：
- 白名单是否为易于维护的结构
- 是否有绕过的遗漏案例（如新增域名未更新白名单）
- 登录重定向流程是否真正必要，可否简化为固定跳转

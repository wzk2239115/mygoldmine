# 案例研究：Java Spring Boot 博客平台中的 XSS

> **难度等级：** ★★★★☆ (中高级)
> **审计时间：** 60-80 分钟 (完整链路)
> **框架：** Spring Boot + Thymeleaf + MySQL

## 漏洞场景

Spring Boot 博客应用允许用户发布文章，前台显示文章和评论。

## 漏洞代码

### 后端：Java Controller

```java
@RestController
@RequestMapping("/api/articles")
public class ArticleController {
    @PostMapping
    public ResponseEntity<?> create(@RequestBody ArticleDTO dto) {
        // ❌ 问题 1：没有验证或净化输入
        Article article = new Article();
        article.setTitle(dto.getTitle());
        article.setContent(dto.getContent());  // 直接保存
        articleRepository.save(article);
        return ResponseEntity.ok(article);
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> getById(@PathVariable Long id) {
        Article article = articleRepository.findById(id).orElse(null);
        return ResponseEntity.ok(article);  // ❌ 返回原始数据
    }
}
```

### Thymeleaf 模板

```html
<!-- ❌ 问题 2：Thymeleaf 默认自动转义，但使用了 th:utext 绕过 -->
<div>
    <h1 th:text="${article.title}">标题</h1>
    <!-- th:text 自动转义，是安全的 -->

    <div th:utext="${article.content}">
        <!-- ❌ th:utext 不转义，直接输出原始 HTML -->
    </div>
</div>
```

### 评论功能

```java
@RestController
@RequestMapping("/api/comments")
public class CommentController {
    @PostMapping
    public ResponseEntity<?> create(@RequestBody CommentDTO dto) {
        Comment comment = new Comment();
        comment.setText(dto.getText());  // ❌ 直接保存
        commentRepository.save(comment);
        return ResponseEntity.ok(comment);
    }
}

// 模板显示评论
/*
<div th:each="comment : ${article.comments}">
    <p th:utext="${comment.text}"></p>  <!-- ❌ 危险！ -->
</div>
*/
```

## 修复方案

### 方案 1：使用 Spring Security + HTML Encoding

```java
import org.springframework.security.web.firewall.StrictHttpFirewall;
import org.owasp.esapi.ESAPI;

@RestController
@RequestMapping("/api/articles")
public class ArticleController {
    @PostMapping
    public ResponseEntity<?> create(@RequestBody ArticleDTO dto) {
        // 1. 验证
        if (dto.getTitle() == null || dto.getContent() == null) {
            return ResponseEntity.badRequest().build();
        }

        // 2. 在后端进行净化（使用 OWASP ESAPI 或 JSoup）
        String cleanContent = cleanHtml(dto.getContent());

        Article article = new Article();
        article.setTitle(ESAPI.encoder().encodeForHTML(dto.getTitle()));
        article.setContent(cleanContent);  // ✅ 保存已净化的内容

        articleRepository.save(article);
        return ResponseEntity.ok(article);
    }

    private String cleanHtml(String content) {
        // 使用 JSoup 净化 HTML
        org.jsoup.nodes.Document doc =
            org.jsoup.Jsoup.parse(content);
        org.jsoup.safety.Whitelist whitelist =
            org.jsoup.safety.Whitelist.basicWithImages();
        return org.jsoup.safety.Cleaner
            .clean(doc, whitelist)
            .getElementsContainingOwnText("")
            .text();
    }
}
```

### 方案 2：修正 Thymeleaf 模板

```html
<!-- 使用 th:text 而不是 th:utext（自动转义） -->
<div>
    <!-- ✅ 安全：自动转义特殊字符 -->
    <h1 th:text="${article.title}"></h1>

    <!-- 如果必须输出 HTML，先在后端净化再标记为 th:utext -->
    <!-- 或改用 th:text + Fragment 方式 -->
    <div th:utext="${article.contentHtml}"></div>
</div>
```

### 方案 3：使用 HtmlEscaper Utility

```java
public class HtmlEscaper {
    public static String escape(String input) {
        if (input == null) return null;
        return input
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&#39;");
    }
}

// 在模板中使用
<p th:text="${@htmlEscaper.escape(comment.text)}"></p>
```

## 审计检查清单

- [ ] 是否使用了 `th:text`（安全）而不是 `th:utext`（危险）？
- [ ] 后端是否对用户输入进行了净化？
- [ ] 是否使用了成熟的净化库（JSoup、OWASP ESAPI）？
- [ ] 是否有 SQL 注入防护？
- [ ] 是否启用了 Spring Security 的 CSRF 保护？
- [ ] 是否有 Content Security Policy (CSP) 头？

## 修复优先级

1. **立即改正：** `th:utext` → `th:text` (前端修复)
2. **快速修复：** 后端添加 JSoup 净化 (1-2 小时)
3. **长期改善：** 构建企业级富文本编辑系统 (几周)


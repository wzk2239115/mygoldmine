# C/C++｜CGI 参数反射型 XSS

## 基本信息

- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-30分钟（单个漏洞点）
- **先决知识：** CGI 标准、环境变量、C/C++ 字符串处理、HTML 编码
- **复杂度评估：**
  - 简单场景（单个 CGI 参数）：15-20分钟
  - 复杂场景（多个参数、复杂逻辑）：30-40分钟

## 🚀 30秒快速清单

- [ ] CGI 脚本是否获取并使用了 `QUERY_STRING`、`REQUEST_METHOD` 等环境变量？
- [ ] 这些参数是否直接输出到 HTML 响应中？
- [ ] 输出前是否进行了 HTML 实体编码或参数验证？
- [ ] 是否使用了不安全的字符串函数（如 `strcpy`、`sprintf` 的 `%s` 格式化）？
- [ ] 是否存在多个 CGI 入口点，编码方式是否一致？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，需要进行 L2+ 深度分析

## Details

### 漏洞成因
早期 CGI 程序或使用 C/C++ 编写的 Web 服务常直接读取 QUERY_STRING、POST 数据，并用 `printf`、`fprintf`、`snprintf` 等函数将参数输出到 HTML。若未进行 HTML 实体编码，攻击者可构造恶意请求，诱导访问页面的用户执行脚本。

### 代码示例

**易受攻击的代码：**
```c
#include <stdio.h>
int main(void) {
    char *query = getenv("QUERY_STRING");
    printf("Content-Type: text/html\r\n\r\n");
    printf("<h1>Search: %s</h1>", query ? query : ""); // 未转义
    return 0;
}
```

**安全示例：**
```c
#include <stdio.h>

void html_escape(const char *src, char *dest, size_t size);

int main(void) {
    char *query = getenv("QUERY_STRING");
    char escaped[2048];
    html_escape(query ? query : "", escaped, sizeof(escaped));
    printf("Content-Type: text/html\r\n\r\n");
    printf("<h1>Search: %s</h1>", escaped);
    return 0;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `printf("<`, `fprintf`, `snprintf`, `QUERY_STRING`, `cgiParam`, `cgicc`。

**定位步骤：**
1. 搜索输出 HTML 的 `printf`；
2. 跳读（L2）确认格式化字符串中插入的变量；
3. 检查是否有自定义转义函数。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 使用 `cgicc::HTTPHTMLHeader`、`cgicc::escapeHTML`；
- 自定义 HTML 转义函数；
- 输出改为 JSON 并由前端负责编码；
- 使用现代 Web 框架处理输出。

**定位技巧：**
- 逐行读（L3）确认所有输出路径均经过转义；
- 跨模块追踪（L4）命令行或脚本入口是否复用相同函数。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 输出统一调用转义函数 | **L0（快速跳过）** | 风险低 |
| 少数输出遗漏编码 | **L2（跳读）** | 快速修补 |
| 广泛使用 printf 直接输出参数 | **L3（逐行读）** | 高风险 |
| 输出函数被多处重用 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. CGI 输出用户可控参数未编码；
2. 可构造 payload 执行脚本；
3. 页面对外可访问。

#### 误报
1. 输出非 HTML（纯文本下载）；
2. 参数来源受控或经过转义；
3. 功能仅用于内部诊断。

#### 代码异味
1. 自定义转义函数未处理引号；
2. 对个别参数转义，其余直接输出；
3. 使用 `system()` 拼接 HTML 再输出。

## Low risk

### 低风险评级场景

#### 1. 服务部署在受控环境
- 攻击面小，可暂降级。

#### 2. 输出仅供调试
- 影响有限，但建议转义。

#### 3. 已计划迁移到现代框架
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 受控环境 | 攻击面小 | 中 |
| 调试用途 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |

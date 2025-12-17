---
title: CSP 通用配置缺陷审计小抄
description: Web 应用 CSP 配置缺陷的通用审计指南和检查清单
---

# CSP 通用配置缺陷审计小抄

任何需要防护 XSS 的 Web 应用项目都必须审计以下 CSP 配置缺陷，这些问题与编程语言无关，属于策略配置层面。

## 1. CSP 响应头缺失或未启用

**检查方法：** 在浏览器开发者工具 Network 标签中查看 HTTP 响应头，或在源代码中搜索 `Content-Security-Policy` 的设置位置。

### 1.1 完全缺失 CSP 响应头
应用的 HTTP 响应中完全没有 `Content-Security-Policy` 响应头。
- 危害：无任何 XSS 防护
- 检查：确认所有返回 HTML 的响应都设置了 CSP 头

### 1.2 部分路由缺失 CSP 响应头
只有部分页面或路由设置了 CSP，其他页面未保护。
- 危害：保护不完整，攻击者可从未保护的路由注入脚本
- 检查：遍历所有返回 HTML 的路由，确认都有 CSP 头

### 1.3 仅使用 Report-Only 模式
使用 `Content-Security-Policy-Report-Only` 而非强制执行的 `Content-Security-Policy`。
- 危害：违规脚本不被阻止，只记录日志
- 检查：确认生产环境使用强制执行的 CSP，而非仅 Report-Only

## 2. 使用不安全的 CSP 指令

### 2.1 允许 unsafe-inline

在 `script-src` 或 `style-src` 中使用 `'unsafe-inline'`。

**危险配置示例：**
```
Content-Security-Policy: script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'
```

**问题分析：**
- `script-src 'unsafe-inline'`：允许所有内联脚本执行，完全失去 XSS 防护
- `style-src 'unsafe-inline'`：允许内联样式，可被用于样式注入攻击
- 内联脚本无法通过 nonce 或 hash 白名单单独控制

**检查要点：**
- 搜索 CSP 定义中的 `'unsafe-inline'` 关键字
- 如确实需要内联脚本，应使用 `nonce` 或 `hash` 替代

**安全配置示例：**
```
Content-Security-Policy: script-src 'self' 'nonce-abc123'; style-src 'self' 'hash-...'
```

### 2.2 允许 unsafe-eval

在 `script-src` 中使用 `'unsafe-eval'`。

**危险配置示例：**
```
Content-Security-Policy: script-src 'self' 'unsafe-eval'
```

**问题分析：**
- 允许 `eval()` 动态执行代码
- 允许 `Function()` 构造函数动态创建函数
- 允许 `setTimeout/setInterval` 执行字符串代码
- 攻击者注入的字符串可被动态执行

**检查要点：**
- 搜索 CSP 定义中的 `'unsafe-eval'` 关键字
- 检查代码中是否调用 `eval()`、`new Function()`、`setTimeout(string)` 等

## 3. 白名单配置过于宽松

### 3.1 使用通配符源

在指令中使用 `*` 或仅 `https:`/`http:` 协议限制。

**危险配置示例：**
```
Content-Security-Policy: script-src *;
Content-Security-Policy: default-src *;
Content-Security-Policy: script-src https:
```

**问题分析：**
- `script-src *`：允许任意来源加载脚本
- `default-src *`：后备策略过于宽松
- `script-src https:`：允许任何 HTTPS 域名，包括攻击者控制的域
- 等同于没有白名单

**检查要点：**
- 搜索 CSP 中 `*` 通配符的使用
- 搜索仅协议限制（`https:`、`http:`）的使用
- 验证白名单中都是可信的具体域名

### 3.2 白名单包含不可信域名

白名单中包含攻击者可控制的域名。

**危险配置示例：**
```
Content-Security-Policy: script-src 'self' https://cdn.example.com https://user-uploads.example.com
```
若 `user-uploads.example.com` 允许用户上传任意文件，攻击者可上传恶意脚本。

**检查要点：**
- 检查白名单中所有域名的可信度
- 特别注意用户可控的文件存储域名

### 3.3 白名单包含已知绕过域名

某些公共服务可被用于绕过 CSP：
- **CDN**：Google Fonts (`googleapis.com`)、Bootstrap CDN 等可能存在上传恶意文件的风险
- **JSONP 端点**：可被利用返回任意脚本
- **重定向服务**：可用于重定向到攻击者控制的域

**检查要点：**
- 审查白名单中所有公共 CDN、第三方域名
- 确认这些服务不存在用户可控的文件上传功能

## 4. 关键 CSP 指令缺失

### 4.1 缺少 script-src 指令

如果 CSP 中没有 `script-src` 而只有 `default-src`，脚本加载策略遵循默认指令。

**检查方法：**
```
Content-Security-Policy: default-src 'self'  # 缺少显式 script-src
```
应改为：
```
Content-Security-Policy: default-src 'self'; script-src 'self'
```

### 4.2 缺少 style-src 指令

样式来源不受限制，可能导致样式注入。

### 4.3 缺少 default-src 指令

默认没有后备策略，其他未显式定义的资源类型无限制。

### 4.4 缺少 frame-src 或 frame-ancestors 指令

应用可被嵌入到其他网站（Clickjacking）。

### 4.5 缺少 connect-src 限制

Fetch/XHR 请求可发送到任意域，导致数据泄露。

**检查要点：**
- 列举 CSP 中的所有指令
- 至少应有：`default-src`、`script-src`、`style-src`、`frame-ancestors`、`connect-src`

## 5. Nonce 或 Hash 机制实现不当

### 5.1 Nonce 值固定或可预测

**危险配置示例：**
```html
<script nonce="static123">console.log('test')</script>
```
同一个 nonce 值被重复使用。

**检查要点：**
- nonce 值应在每次请求时随机生成（使用强随机数生成器）
- nonce 值不应出现在客户端可见的源码中或日志中
- 确认使用了密码学安全的随机数生成器（如 `crypto.getRandomValues()`）

### 5.2 Nonce 未在每次请求重新生成

nonce 值在会话期间保持不变，可被重放攻击。

### 5.3 Hash 值过期或错误

**危险配置示例：**
```
Content-Security-Policy: script-src 'hash-sha256-xyz123'
```
脚本内容更新后，hash 值未同步更新。

**检查要点：**
- 每当受保护脚本内容变更时，hash 值必须重新计算
- 使用自动化工具确保 hash 同步

## 6. CSP 报告机制缺失

### 6.1 缺少 report-uri 或 report-to 指令

CSP 违规无法被监控和记录。

**检查方法：**
```
# 不安全 - 无报告
Content-Security-Policy: script-src 'self'

# 安全 - 配置报告
Content-Security-Policy: script-src 'self'; report-uri /csp-report
```

**检查要点：**
- 确认 CSP 配置包含 `report-uri` 或 `report-to`
- 验证报告端点是否可用并正确处理报告
- 确认报告被正确记录和监控

### 6.2 报告端点配置错误

报告端点返回错误或不存在。

## 审计检查清单

- [ ] **必检**：所有返回 HTML 的响应都有 `Content-Security-Policy` 头（非 Report-Only）
- [ ] **必检**：CSP 中没有 `'unsafe-inline'` 或 `'unsafe-eval'`
- [ ] **必检**：CSP 白名单不包含 `*` 通配符或仅协议限制
- [ ] **必检**：CSP 定义了 `default-src`、`script-src`、`style-src`
- [ ] **必检**：如使用 nonce，验证每次请求都生成新的随机 nonce
- [ ] **必检**：如使用 hash，验证与脚本内容同步
- [ ] **必检**：CSP 包含 `report-uri` 或 `report-to` 用于监控
- [ ] **推荐**：`frame-ancestors` 限制应用的嵌入
- [ ] **推荐**：`connect-src` 限制 XHR/Fetch 目标

---

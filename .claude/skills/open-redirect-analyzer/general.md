---
title: 通用开放重定向漏洞审计小抄
description: 开放重定向漏洞的通用审计指南，涵盖漏洞模式、绕过技巧和研判标准
category: 安全审计
---

# 通用开放重定向漏洞审计小抄

任何实现重定向功能的应用都必须审计以下漏洞模式。这些问题源于重定向目标未经验证，与编程语言无关。

## 1. 用户输入直接用于重定向

### 动态重定向目标

**危险代码特征**

```python
redirect_url = request.get('url')
response.redirect(redirect_url)
```

**快速定位**（L1: 关键词扫描）：
- 搜索重定向函数：`redirect()`、`location`、`Location`、`window.location`
- PHP：`header('Location:')`
- Python：`redirect()`、`HttpResponseRedirect`
- Java：`sendRedirect()`、`forward()`
- JavaScript：`window.location`、`location.href`

**快速定位保护机制**（L2-L3: 跳读/逐行读）：
- **URL 白名单**（L2）：检查重定向目标是否通过白名单验证
- **协议验证**（L2）：检查是否限制了允许的协议（仅 http/https）
- **域名验证**（L3）：检查是否验证了重定向目标的域名属于可信列表
- **完整链路**（L4）：追踪重定向参数从输入到使用的完整过程

---

## 2. 特殊重定向场景

### 认证和授权流程中的重定向

**风险位置**
- OAuth redirect_uri：未严格验证重定向地址
- 登录后重定向：next、return_url 等参数
- 授权回调：第三方服务回调 URL

**快速定位**（L2: 跳读）：
- 搜索 OAuth 相关的参数：redirect_uri、callback、return_url、next
- 检查这些参数是否进行了严格的白名单验证

---

## 3. 重定向绕过技巧

### 常见绕过方式

**协议相对 URL**
- 形式：//attacker.com
- 问题：检查仅限制 http/https 时，此形式可绕过

**URL 编码绕过**
- 形式：%68ttp://attacker.com（h 被编码）
- 问题：解码后才用于重定向，但检查在解码前进行

**IPv6 地址**
- 形式：http://[::1]/
- 问题：某些白名单验证方式不支持 IPv6

**DNS 重绑定**
- 形式：http://trusted-domain-attacker.com
- 问题：域名验证时指向可信域名，实际访问时被重绑定

---

## 4. 研判标准

### 确认为漏洞

**必须满足**
1. 重定向目标可由用户控制
2. 未进行有效的 URL 白名单验证
3. 攻击者可重定向到任意外部网站
4. 用于钓鱼、窃取凭证或恶意软件分发

**应用场景**
- 登录重定向：/login?next=http://attacker.com
- OAuth 回调：redirect_uri=http://attacker.com
- 跳转接口：/api/redirect?url=http://attacker.com

### 判定为误报

**如果满足以下情况之一，可判定为误报**
1. **完整白名单**：重定向目标严格限制在预定义的列表中
2. **相对路径**：仅允许相对路径重定向，不允许绝对 URL
3. **协议限制**：明确验证了协议只能是 http/https
4. **域名限制**：验证了重定向目标属于本域或可信域名列表

---

## 5. 低风险指标

### 以下情况应给予低风险评级

1. **完整的白名单**：重定向目标必须在明确定义的白名单中
2. **相对路径限制**：应用仅支持相对路径重定向
3. **协议白名单**：明确验证了协议为 http 或 https
4. **域名验证**：重定向目标必须属于本域或可信域名
5. **防御深度**：即使成功重定向，目标网站也不会进行恶意操作

---

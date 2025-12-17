# Go 弱随机数生成CAPTCHA验证码

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-25分钟
- **关键指标：** 随机源强度 | 会话绑定 | 一次性验证 | 有效期

## 🎯 快速审计清单
- [ ] 使用 `math/rand`（必漏）还是 `crypto/rand`（安全）？
- [ ] 种子初始化位置：函数内（每次可预测）还是init（并发重复）？
- [ ] CAPTCHA是否强绑定session？验证后是否立即删除？
- [ ] 有无效期检查（≤5分钟为佳）？
- [ ] 验证次数是否限制？错误后是否计数？
- [ ] 字符集复杂度：纯数字≈危险，混合字符≈安全
- [ ] 图像生成是否有有效的干扰（线、点、扭曲）？

## Details

### 漏洞成因（三个核心问题）

**1. 随机源强度**：`math/rand` 是伪随机生成器，周期有限且可被推算。基于时间戳的种子(`time.Now().UnixNano()`)在毫秒级精度内是可预测的。攻击者若知道服务器时间，可在秒级内遍历所有可能的种子值，破解验证码。

**2. 状态管理缺陷**：全局种子初始化或验证后不删除导致验证码可重用。CAPTCHA未与特定session绑定，可被其他用户重放。多个并发请求可能获取相同的伪随机序列（PRNG周期性）。

**3. 验证逻辑漏洞**：空值绕过（未检查expected=="则验证通过）、大小写不敏感（降低搜索空间）、无有效期（慢速暴力破解）、字符集过简单（纯数字10^4=10000种可能，100分钟内遍历）。

### 代码示例

**漏洞1：math/rand + 时间种子（可预测）**
```go
func generateCaptcha() string {
    rand.Seed(time.Now().UnixNano())  // ⚠️ 毫秒精度，秒内可穷举
    return fmt.Sprintf("%04d", rand.Intn(10000))
}
```
**攻击**：获取服务器时间→遍历UnixNano()值→本地生成验证码→匹配

**漏洞2：全局种子初始化，并发生成重复码**
```go
func init() { rand.Seed(time.Now().UnixNano()) }
func gen() string {
    return fmt.Sprintf("%04d", rand.Intn(10000))  // 并发调用可能相同
}
```
**攻击**：快速并发请求→捕获相同验证码→重放多次

**漏洞3：全局存储，验证后未删除**
```go
var captchas = make(map[string]string)
func verify(id, input string) bool {
    return captchas[id] == input  // 验证成功仍存在，可重用
}
```
**攻击**：获得有效ID后，无限次穷举10000种可能

**漏洞4：验证逻辑缺陷**
```go
if session.Values["captcha"] == userInput {  // 空==空通过！
    ok = true
}
if strings.ToLower(a) == strings.ToLower(b) {  // 大小写不敏感
    ok = true  // 搜索空间减半
}
```
**攻击**：清空session→提交空串；或忽略大小写→搜索空间减半

### 快速定位核心操作

**搜索关键词**：`math/rand`, `rand.Seed`, `rand.Intn`, `captcha`, `verify`, `session.Values["captcha"]`

**代码位置识别**：
- 导入语句：`import "math/rand"` (⚠️) vs `import "crypto/rand"` (✓)
- 生成函数：`generate*`, `create*`, 函数体内 `rand.Seed(time.Now()` (⚠️)
- 验证函数：变量对比前检查是否有 `if expected == ""` 或 `if expected != ""`
- Session操作：搜索 `session.Save()` 是否设置了 `Options.MaxAge`（有效期）
- 删除操作：验证成功后是否有 `delete(session.Values, "captcha")` 或 `session.Values["captcha"] = ""`

### 审计等级判定（快速分类）

| 等级 | 标志 | 审计深度 |
|------|------|---------|
| **P0漏洞** | `math/rand` + `rand.Seed(time.Now()` + 无删除 | 5分钟内确认，立即上报 |
| **P1漏洞** | `crypto/rand` 但无有效期 / 字符集纯数字 | 10分钟审查配置参数 |
| **P2问题** | 有基本防护但存在异常（验证次数无限制） | 检查整体防御策略 |
| **低风险** | 使用reCAPTCHA / base64Captcha库 + 正确配置 | 仅验证集成方式 |

---

## Classify

### 确认漏洞（需满足以下任一条件）

**必漏（P0）**：
- 导入 `"math/rand"` 用于生成CAPTCHA
- `rand.Seed()` 在生成函数内部（每次执行都重新初始化，导致可预测）
- 验证函数中无任何删除操作（验证后仍可重用）
- 使用全局map存储CAPTCHA（可跨用户重放）

**高危（P1）**：
- 使用 `crypto/rand` 但字符集仅数字（4-5位=10000种可能）
- 无有效期检查或超过30分钟
- 验证失败后未递增计数，可无限尝试
- 验证逻辑中使用 `strings.ToLower()` 进行大小写不敏感比较

**代码异味（需进一步验证）**：
- 字符集长度<6或仅使用数字
- Session无 `Options.MaxAge` 设置
- 验证前未检查 `expected == ""`（空值绕过）
- 图像生成无任何干扰（纯背景+固定字体）

### 误报排除（低风险场景）

✗ 使用 `crypto/rand.Int()` / `crypto/rand.Read()` 生成
✗ 字符集混合大小写+数字，长度≥6
✗ 验证成功后立即删除或标记，验证失败限制次数≤3
✗ 有效期≤5分钟，存储creation_time并检查
✗ 使用成熟库：`github.com/dchest/captcha` 或 `github.com/mojocn/base64Captcha`（<1年内发布版本）
✗ 已集成Google reCAPTCHA v3或Cloudflare Turnstile
✗ 非关键业务（newsletter订阅）+ IP白名单限制

---

## Low Risk

### 低风险评级条件

**1. 使用第三方成熟库**
- `base64Captcha`：支持数字/字符/算术多种类型，内置 `crypto/rand`，<1年版本
- `dchest/captcha`：数字验证码，音频支持，MIT license
- 版本要求：<6个月内发布 OR 无已知安全漏洞

**2. 集成第三方服务（推荐）**
- Google reCAPTCHA v3（无用户交互，行为分析，分数0-1判定）
- Cloudflare Turnstile（隐私友好，零交互）
- hCaptcha（GDPR合规，隐私优先）

**3. 完善的自实现检查清单**
```go
// ✓ 随机源：使用crypto/rand
num, err := rand.Int(rand.Reader, big.NewInt(charset_len))

// ✓ 字符集：大小写+数字，排除0/O/1/I/l，长度6+
charset = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz"

// ✓ 有效期：≤5分钟
session.Options.MaxAge = 300

// ✓ 一次性删除
delete(session.Values, "captcha_code")

// ✓ 尝试限制
if attempts >= 3 { return false }

// ✓ 时间戳验证
if time.Since(created) > duration { return false }

// ✓ 常量时间比较
subtle.ConstantTimeCompare([]byte(expected), []byte(input))
```

**4. 多层防御加分**
- CAPTCHA + 速率限制（10次/分钟）
- CAPTCHA + 账户锁定（5次失败）
- 渐进式防护（仅3次失败后显示CAPTCHA）
- 监控与告警（CAPTCHA失败率>30%）

**评级建议**：使用 `math/rand` 即使配置良好也至少中危；登录类关键功能弱CAPTCHA至少高危

---

## 安全实现

### 方案A：使用crypto/rand自实现

```go
const secureCharset = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz"

func Generate(length int) string {
    result := make([]byte, length)
    for i := 0; i < length; i++ {
        num, _ := rand.Int(rand.Reader, big.NewInt(int64(len(secureCharset))))
        result[i] = secureCharset[num.Int64()]
    }
    return string(result)
}

func Verify(w http.ResponseWriter, r *http.Request, userInput string) bool {
    session, _ := store.Get(r, "captcha-session")
    code, ok := session.Values["captcha"].(string)
    if !ok || code == "" { return false }

    // 检查有效期（5分钟）
    created, _ := session.Values["created"].(int64)
    if time.Now().Unix()-created > 300 { return false }

    // 检查尝试次数（≤3次）
    attempts, _ := session.Values["attempts"].(int)
    if attempts >= 3 { return false }
    session.Values["attempts"] = attempts + 1
    session.Save(r, w)

    // 常量时间比较
    if subtle.ConstantTimeCompare([]byte(code), []byte(userInput)) != 1 {
        return false
    }

    // 验证成功：删除（一次性使用）
    delete(session.Values, "captcha")
    session.Save(r, w)
    return true
}
```

### 方案B：使用成熟库（推荐）

```bash
go get github.com/mojocn/base64Captcha
# 自动提供：crypto/rand + 图像干扰 + 5分钟过期 + 验证后删除
```

### 方案C：使用reCAPTCHA v3（最简单）

```
前端：<script src="https://www.google.com/recaptcha/api.js?render=YOUR_SITE_KEY"></script>
后端：验证token并检查score（>0.5为可信）
```

---

## 修复优先级

1. **立即修复（当天）**：`math/rand` → `crypto/rand`（最高威胁）
2. **快速修复（3天）**：验证成功后删除验证码，失败限制尝试
3. **短期改善（1周）**：有效期≤5分钟，存储creation_time
4. **长期优化（2周）**：字符集6+位，大小写+数字混合
5. **考虑迁移**：使用base64Captcha或reCAPTCHA v3

---

## 审计技巧与经验

### 快速破译法（5分钟内判断严重程度）

| 特征 | 等级 | 确认方法 |
|------|------|---------|
| 搜到 `"math/rand"` | 🔴P0 | 1秒确认，必报 |
| `rand.Seed(time.Now()` 在函数内 | 🔴P0 | 立即上报，不需测试 |
| `captchas[id] == input` 无删除 | 🔴P0 | 搜索verify函数是否删除操作 |
| `crypto/rand` 但字符集仅数字 | 🟠P1 | 4-5位=可行，6位=较安全 |
| Session无 `Options.MaxAge` | 🟠P1 | 搜索 `session.Save()` 前是否赋值 |

### 并发下验证问题快速判断

全局 `rand.Seed(time.Now())` = PRNG周期问题 | 全局map存储 = 跨用户共享问题

### 暴力破解成本评估

- 纯数字4位=10000种（1小时可破）| 6位=100万（困难）| 混合62^6=58亿（不可行）
- 有效期5分钟+10次/分钟 = 最多50次，成功率≈0.5%

### 审计搜索技巧

```bash
grep -r "math/rand\|rand.Seed" --include="*.go"
grep -r "var.*captcha.*map" --include="*.go"
grep -A3 "session.Save\|Options.MaxAge" --include="*.go"
```

### 常见绕过思路及黑盒测试

1. **时间预测**：服务器时间 ± 秒级 → 本地遍历UnixNano() → 破解
2. **并发重复**：快速请求两次 → 验证码相同？
3. **全局重用**：多次验证同一答案？
4. **空值绕过**：提交空字符串？
5. **慢速暴力**：无有效期+无尝试限制 → 每天几次持续数月

**快速黑盒测试清单**：[ ] 并发重复 [ ] 重用 [ ] 空值 [ ] 无限尝试 [ ] 5分钟后过期 [ ] 一次性

**报告撰写**：标注 `math/rand` 代码位置 + 时间预测攻击步骤 + 并发PoC


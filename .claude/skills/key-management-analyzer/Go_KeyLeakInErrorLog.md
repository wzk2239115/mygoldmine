# Go 密钥在错误日志中泄露

**漏洞类型**：密钥管理 - 信息泄露  
**适用场景**：链下组件（中继器、签名服务、CLI工具、节点服务）  
**高发位置**：密钥加载、签名操作、配置解析、错误处理路径

## Details

**典型代码模式：**

```go
// 漏洞示例1：直接在错误信息中包含密钥
func LoadPrivateKey(keyPath string) (*ecdsa.PrivateKey, error) {
    keyBytes, err := os.ReadFile(keyPath)
    if err != nil {
        return nil, fmt.Errorf("failed to read key %s: %w", string(keyBytes), err)
    }
    privateKey, err := crypto.ToECDSA(keyBytes)
    if err != nil {
        log.Errorf("invalid private key: %v, raw: %s", err, string(keyBytes))
        return nil, err
    }
    return privateKey, nil
}

// 漏洞示例2：结构体的Error()或String()方法暴露密钥
type Signer struct {
    PrivateKey string
    Address    string
}

func (s *Signer) Sign(hash []byte) ([]byte, error) {
    if s.PrivateKey == "" {
        return nil, fmt.Errorf("signer not initialized: %+v", s)
    }
    // ...
}

// 漏洞示例3：调试模式下全量输出配置
func InitConfig(cfg *Config) error {
    log.Debugf("loading config: %+v", cfg) // cfg包含PrivateKey字段
    // ...
}
```

**快速定位核心操作（L2-L3）：**
- **关键函数**：搜索 `fmt.Errorf`、`log.Error`、`log.Warn`、`log.Debug`、`log.Info`、`fmt.Sprintf`
- **高危变量名**：`privateKey`、`privKey`、`secret`、`mnemonic`、`seed`、`keyBytes`、`credential`
- **敏感结构体**：包含 `PrivateKey`、`SecretKey` 字段的结构体，检查其 `Error()`、`String()`、`GoString()` 方法
- **格式化动词**：`%+v`（输出所有字段）、`%#v`（详细格式）、`%s`（字符串化）
- **审计流程**：(L1) 关键词扫描错误处理函数 → (L2) 跳读日志调用上下文 → (L3) 逐行检查是否包含密钥变量

**快速定位保护机制（L1-L2）：**
- **自定义String方法**：检查敏感结构体是否实现 `String()` 并脱敏（如：`return "***"`）
- **日志脱敏库**：搜索 `redact`、`sanitize`、`mask` 函数调用
- **字段标签**：查找 `json:"-"`、`yaml:"-"`、`secret:"true"` 等标签（仅部分框架支持）
- **错误包装检查**：确认错误包装时未使用 `%w` 或 `%v` 直接暴露上层错误
- **审计流程**：(L1) 关键词扫描脱敏函数 → (L2) 跳读结构体定义确认保护方法存在

## Classify

**漏洞判定（High/Critical）：**
- 日志级别 ≤ Warn（Error/Fatal/Panic/Warn）且直接输出密钥内容
- 生产环境启用Debug日志且输出密钥（检查配置文件或环境变量）
- 错误返回值中包含密钥原文，可能传播至RPC响应、HTTP响应、跨进程通信

**误报（False Positive）：**
- 仅在测试代码中输出，且使用固定测试密钥（检查文件路径包含 `_test.go` 或 `testdata/`）
- 输出密钥的哈希值、公钥、地址（非原始私钥）
- 日志输出前已调用脱敏函数（如 `log.Info(redact(key))`）

**代码异味（Code Smell）：**
- Debug级别日志输出密钥，但生产环境默认关闭Debug（需配置review）
- 注释中包含密钥变量名，但实际未输出
- 错误信息提示密钥路径或格式，但未泄露内容

## Low risk

**降级为低风险的场景：**
- **本地开发工具**：CLI工具仅在本地运行，日志不上传远程（需确认无telemetry模块）
- **临时密钥**：密钥为会话临时生成，有效期 < 5分钟（需验证密钥生命周期管理）
- **沙箱环境**：测试网私钥泄露，且该私钥未用于主网或关联真实资产
- **受限日志访问**：日志仅写入本地文件，无网络传输，且服务器有严格访问控制（需审查日志采集配置）
- **已有二次防护**：日志系统配置了字段级过滤规则（如 ELK/Loki 的 pipeline 脱敏）

**注意**：即使符合低风险条件，仍需在审计报告中标注，建议修复，避免后续基础设施变化导致风险升级。

# Rust Serde Deserialize_Any 逻辑绕过

## Details

### 代码示例

**典型漏洞模式：**

```rust
// 场景1: deserialize_any 未限制类型
#[derive(Deserialize)]
struct Config {
    role: String,
    #[serde(default)]  // 允许缺失字段
    admin: bool,
}

fn load_config(data: &[u8]) -> Config {
    bincode::deserialize(data).unwrap()  // 可注入额外字段
}

// 场景2: 自定义 Visitor 无验证
impl<'de> Deserialize<'de> for Permission {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        deserializer.deserialize_any(PermissionVisitor)  // any类型
    }
}

// 场景3: 枚举标签可控
#[derive(Deserialize)]
#[serde(tag = "type")]  // 外部可控type字段决定枚举变体
enum Action {
    Read { path: String },
    Write { path: String, data: Vec<u8> },
    Execute { cmd: String },  // 特权操作
}

// 场景4: flatten 无边界
#[derive(Deserialize)]
struct Request {
    id: u64,
    #[serde(flatten)]  // 扁平化嵌入额外字段
    extra: HashMap<String, Value>,
}
```

### 快速定位核心操作技巧

**L1 - 关键词扫描：**
- `deserialize_any` / `deserialize_ignored_any` 
- `#[derive(Deserialize)]` 且无 `deny_unknown_fields`
- `bincode::deserialize` / `serde_json::from_*` / `ron::from_*` / `toml::from_*`
- `#[serde(tag =` / `#[serde(flatten)]` / `#[serde(untagged)]`

**L2 - 跳读验证：**
- 检查 `Deserialize` trait 实现中 `Visitor` 的 `visit_*` 方法是否覆盖所有类型
- 扫描配置加载/网络协议解析入口点（`load_config`, `parse_request`, `decode_message`）
- 查找 `#[serde(default)]` 字段是否影响权限判断

**L3 - 逐行分析：**
- 跟踪反序列化数据流向：是否用于 `if role == "admin"` / `match action` 等鉴权逻辑
- 验证枚举变体是否隐藏危险操作（`Execute`, `Delete`, `Elevate`）
- 检查 `flatten` 的 `HashMap`/`Value` 是否在后续被 `get()` 读取但未白名单校验

**L4 - 跨模块追踪：**
- 外部输入 → 反序列化 → 业务逻辑的完整路径（如 HTTP body → `serde_json::from_slice` → `handle_request`）
- 自定义 `Deserialize` 实现是否在多模块复用，且不同上下文有不同权限要求

### 快速定位保护机制技巧

**L1 - 关键词扫描：**
- `#[serde(deny_unknown_fields)]` - 拒绝未知字段
- `#[serde(bound =` - 自定义边界约束
- `deserialize_struct` / `deserialize_enum` - 显式类型方法（非 `any`）

**L2 - 跳读验证：**
- 查看结构体定义是否有 `deny_unknown_fields` 或 `#![forbid(unknown_fields)]`
- 检查是否用 `serde(try_from =` 配合自定义验证函数
- 扫描 `impl Deserialize` 中是否有 `expecting()` 错误信息和类型断言

**L3 - 逐行分析：**
- 验证 `Visitor` 的 `expecting` 描述是否与实际 `visit_*` 方法匹配
- 检查枚举是否有 `#[serde(rename_all = "snake_case")]` 且仅允许预定义标签
- 确认 `flatten` 后是否有 `validate_keys()` 白名单检查

**L4 - 跨模块追踪：**
- 查找配置加载后是否有全局验证层（如 `Config::validate(&self) -> Result`）
- 检查序列化格式库的版本和 feature（如 `bincode = { version = "1.3", features = ["no_std"] }`）
- 验证网络边界是否有 schema 预验证（如 JSON Schema / Protocol Buffers）

## Classify

### 归类为漏洞的判据：

1. **类型混淆导致逻辑绕过：** 反序列化数据直接用于权限判断，且攻击者可注入/篡改关键字段（如 `admin: true`, `role: "superuser"`）绕过鉴权
2. **枚举变体可控：** 通过可控的 `tag` 字段实例化危险枚举变体（如 `Action::Execute`），执行超出预期的操作
3. **数据覆盖：** `flatten` 或 `default` 允许覆盖受保护字段，导致业务逻辑异常（如覆盖价格、数量、用户ID）
4. **内存安全风险：** 自定义 `Deserialize` 实现未验证 `Vec` 长度、索引边界，可能 panic 或触发 unsafe 代码 UB

### 归类为误报的判据：

1. **数据源可信：** 反序列化输入来自本地文件系统且有权限控制，或通过签名/加密验证
2. **后置验证：** 反序列化后立即有 `validate()` 函数检查所有关键字段，拒绝非法值
3. **只读操作：** 仅用于日志、监控等只读场景，不影响控制流或状态修改

### 归类为代码异味的判据：

1. **过度灵活设计：** 使用 `deserialize_any` 但实际只需固定类型，增加攻击面
2. **防御深度不足：** 依赖单一 `deny_unknown_fields`，缺少多层验证（如类型+范围+业务规则）
3. **错误处理粗糙：** 反序列化失败直接 `unwrap()` panic，未优雅降级

## Low Risk

### 应给予低风险评级的场景：

1. **严格类型约束：** 使用 `deserialize_struct` 显式指定字段名和类型，且所有字段无 `default`，必须完全匹配
2. **隔离环境：** 反序列化在沙箱或独立进程中执行，崩溃不影响主服务
3. **仅元数据：** 反序列化内容为配置元数据（如主题颜色、日志级别），无安全敏感逻辑
4. **内容限制：** 输入经过大小/格式/字符集预过滤，且反序列化库启用安全 feature（如 `serde(bound = "T: SafeTrait")`）
5. **不可达路径：** 代码在测试/示例模块中，生产环境未编译（`#[cfg(test)]`）
6. **协议固定：** 使用 `protobuf`/`capnproto` 等严格 schema 协议，且 `.proto` 文件受版本控制且 code review
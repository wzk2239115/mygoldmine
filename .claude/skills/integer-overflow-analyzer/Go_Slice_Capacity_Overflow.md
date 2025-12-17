# Go_Slice_Capacity_Overflow

**漏洞类型**: 切片容量计算溢出，make() 函数创建切片时使用用户输入作为容量参数

**Go**

---

## Details

**代码示例**：`make([]int, length, capacity)`、`make([]byte, size)`、`s = append(s, data...)`、`s[:start+length]`

### 核心操作定位技巧 (L1: 关键词扫描)

1. **主要扫描关键字**：`make([]`、`make(map[`、`append()`、`cap()`、`len()`
2. **参数来源追踪**：
   - HTTP 请求参数（query、body、header）
   - 数据库查询结果
   - 文件读取的数据
   - 网络连接的输入
   - 配置文件解析
3. **边界操作识别**：`s[start:end]`、`s[:length]`、`s[start:]` 的边界计算
4. **循环中的动态分配**：for 循环内 make() 调用且容量受循环控制变量影响

### 保护机制定位技巧 (L2: 跳读)

1. **显式验证**：
   - `if length > MaxLength` 的上界检查
   - `if length < 0` 的下界检查
   - `if length > math.MaxInt64` 的溢出检查
   - `if cap > remaining` 的可用资源检查

2. **间接保护**：
   - 分页处理：逐页读取而非一次性分配
   - 流式处理：iterating over data 而非预分配
   - 固定大小 buffer：`make([]byte, 4096)` 重复使用
   - Rate limiting 或 quota 机制

3. **错误恢复**：
   - `defer func()` 捕获 panic
   - `recover()` 处理内存分配失败
   - 超时控制防止长时间占用资源

## Classify

### 确定为真实漏洞的特征

1. **完全无保护**：
   ```go
   // 直接用用户输入作为容量
   buf := make([]byte, request.Size)
   ```
   - 无任何长度校验
   - 无 panic 恢复
   - 无分页或流式处理

2. **不完整的验证**：
   ```go
   // 只检查下界，忽视上界
   if len < 0 {
       return error
   }
   buf := make([]byte, len)  // 仍可能超大
   ```

3. **验证绕过可能**：
   - 验证在错误处理分支中被跳过
   - 多个代码路径中只有部分做了检查
   - 使用了已过期的常量定义

### 区分真实漏洞与误报的经验

1. **明确误报**（低风险）：
   - 容量为代码中写死的常量：`make([]byte, 1024)`
   - 容量通过 config 来源但有 validation：`loadConfig()` 返回的已验证值
   - 分页处理清晰：`pageSize := min(userSize, maxPageSize); make([]byte, pageSize)`

2. **灰色地带需深入分析**：
   ```go
   // 需要检查 userInput 的真实来源和验证链
   size := parseUserInput(userInput)
   // 追踪 parseUserInput 是否有验证逻辑
   buf := make([]byte, size)
   ```

3. **常见误导情况**：
   - 参数名含有 "max"、"limit" 但没实际检查
   - 注释说明 "已验证" 但代码中无验证逻辑
   - 依赖上游系统的验证，但上游验证不可靠

### 审计盲点提示

- **跨函数验证遗漏**：验证在调用方，漏洞在被调用方
- **条件分支遗漏**：错误处理路径中没有检查
- **整数溢出计算**：`size1 + size2` 相加时可能溢出后变小
- **panic 假设**：认为内存分配失败会 panic，实际上有时会返回 nil

## Low risk

- slice 容量为常量或有明确上限
- 使用 `min(size, maxSize)` 限制容量
- 使用分页或流式处理代替大 slice
- 容量来自已验证的配置
- 有 panic 恢复和错误处理
- 基于连接级别或会话的资源限额
- 使用 context timeout 防止长期占用


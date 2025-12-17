# **Java LLM Prompt Injection Spring AI**

当使用 Spring AI 框架集成 LLM 时，用户输入未经清理直接用于构造提示词，攻击者可以通过注入恶意提示词改变模型行为。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索 Spring AI 使用：`RestClient`、`ChatModel`、`ChatClient`
- 查找提示词构造：`Prompt`、`SystemPromptTemplate`、`PromptTemplate`
- 搜索用户输入：`userInput`、`req.getParameter()`、`RequestBody`
- 查找字符串拼接：`"..." + userInput`、`String.format()`
- 定位消息构造：`UserMessage`、`SystemMessage`

**核心操作保护机制（L2: 跳读）**
- 检查是否使用了参数化的 PromptTemplate
- 验证是否对输入进行了验证
- 查看提示词系统设计是否明确
- 检查是否使用了分离的系统/用户消息
- 查看是否有提示词注入防护

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪从用户输入到 Prompt 对象的构造
- 检查 PromptTemplate 的参数化使用
- 审查 SystemPromptTemplate 中是否包含用户输入
- 查看消息列表的构造方式
- 检查是否有多个提示词拼接点

**数据流追踪（L4: 跨模块追踪）**
- 追踪用户输入的完整路径
- 检查是否有中间验证步骤
- 验证所有提示词构造点

## Classify

**确认为漏洞的特征：**
1. SystemPromptTemplate 中包含未清理的用户输入
2. Prompt 构造使用字符串拼接
3. 用户可以覆盖系统提示
4. 提示词参数未经验证
5. 多个消息来源混淆

**误报场景：**
1. 使用参数化的 PromptTemplate
2. 系统提示由应用定义，用户无法修改
3. 用户输入仅作为明确的参数
4. 输入经过验证
5. 明确的消息分离（SystemMessage vs UserMessage）

**代码异味（需要深入审查）**
1. 动态 PromptTemplate 构造
2. 多个提示词处理点
3. 条件性地包含用户输入
4. 缺少输入验证

## Low risk

**评级为低风险的场景：**
1. 使用 Spring AI 的参数化 PromptTemplate
2. 系统提示由应用代码定义，不接受用户修改
3. UserMessage 与 SystemMessage 明确分离
4. 输入长度和格式严格限制
5. 提示词版本控制和审核机制

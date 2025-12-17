# Java OGNL 表达式语言注入

**漏洞成因**：OGNL (Object-Graph Navigation Language) 是 Java 中用于获取和设置对象属性的表达式语言，广泛用于 Struts2、WebWork 等框架。当应用将用户输入作为 OGNL 表达式进行解析时，攻击者可构造恶意表达式访问静态方法、执行系统命令、访问私有字段等，导致远程代码执行。Struts2 历史上多个高危漏洞（如 S2-045、S2-057）均源于 OGNL 注入。

---

## Details

**代码示例**：
```java
// 危险：直接解析用户输入的 OGNL 表达式
import ognl.Ognl;
import ognl.OgnlContext;

String userInput = request.getParameter("expr");
Object root = new Object();
Object value = Ognl.getValue(userInput, root); // 危险：用户可注入任意表达式

// 危险示例：带上下文执行
OgnlContext context = new OgnlContext();
context.put("user", currentUser);
Object result = Ognl.getValue(userInput, context, root);

// 危险示例：Struts2 框架中的 OGNL 使用
// <s:property value="%{userInput}"/> // 用户输入直接作为 OGNL 表达式

// 攻击载荷示例
// @java.lang.Runtime@getRuntime().exec('calc')
// (#cmd='calc').(#iswin=(@java.lang.System@getProperty('os.name').toLowerCase().contains('win'))).(#cmds=(#iswin?{'cmd.exe','/c',#cmd}:{'/bin/bash','-c',#cmd})).(#p=new java.lang.ProcessBuilder(#cmds)).(#p.start())
// #context['xwork.MethodAccessor.denyMethodExecution']=false

// 较安全：使用受限的 OgnlContext
OgnlContext context = new OgnlContext();
context.setMemberAccess(new DefaultMemberAccess(false)); // 禁用私有成员访问

// 较安全：禁用静态方法调用
OgnlContext context = new OgnlContext();
context.put(OgnlContext.MEMBER_ACCESS, new MemberAccess() {
    @Override
    public boolean isAccessible(Map context, Object target, Member member, String propertyName) {
        return member.getModifiers() & Modifier.STATIC == 0; // 拒绝静态成员
    }
});

// 较安全：表达式白名单
Set<String> allowedExpressions = Set.of("user.name", "order.id");
if (!allowedExpressions.contains(userInput)) {
    throw new SecurityException("Invalid expression");
}
```

**快速定位核心操作**：
- 关键词：`Ognl.getValue`、`Ognl.setValue`、`Ognl.parseExpression`、`OgnlContext`、`@java.lang.Runtime@`
- 查找 OGNL 类的静态方法调用位置：`Ognl.getValue()`、`Ognl.setValue()`
- 追踪表达式字符串的来源，判断是否包含用户输入
- 检查 Struts2 框架中的 OGNL 使用：`<s:property>`、`<s:if>`、Action 类中的表达式求值
- 搜索依赖：`ognl:ognl`、`org.apache.struts:struts2-core`
- 关注 Struts2 版本，历史版本存在多个 OGNL 注入漏洞

**快速定位保护机制**：
- 是否使用了 `DefaultMemberAccess(false)` 禁用私有成员访问
- 是否自定义 `MemberAccess` 接口限制静态方法调用
- 是否禁用了 OGNL 的类型转换和构造函数调用
- Struts2 是否配置了 `struts.ognl.allowStaticMethodAccess=false`
- 是否使用了 Struts2 的安全配置：`struts.ognl.expressionMaxLength`
- 是否使用表达式白名单验证用户输入
- Struts2 版本是否为最新稳定版（2.5.30+），已修复已知漏洞

**审计等级**：**L2-L4**
- **L2**：跳读关键 API 调用，识别 OGNL 表达式的使用位置
- **L3**：逐行验证表达式参数来源，确认是否包含用户可控数据
- **L4**：跨模块追踪 OgnlContext 配置和 MemberAccess 实现，验证安全限制

---

## Classify

**确认为漏洞**：
- 直接使用 `Ognl.getValue()` 解析用户输入的表达式
- Struts2 应用中用户输入出现在 OGNL 表达式位置（如 `<s:property value="%{userInput}"/>`）
- 未配置 `MemberAccess` 或使用了默认的宽松访问控制
- 允许静态方法调用：`struts.ognl.allowStaticMethodAccess=true`
- 可通过 OGNL 表达式访问 Runtime、ProcessBuilder 等危险类

**误报**：
- 表达式内容为硬编码常量或配置文件中的预定义值
- 使用了严格的 `MemberAccess` 配置，禁用静态方法和私有成员访问
- 用户输入经过白名单验证，仅允许简单的属性访问表达式
- Struts2 应用使用了最新版本且已禁用 OGNL 的危险特性

**代码异味**：
- 大量使用 OGNL 进行动态属性访问和方法调用
- 表达式字符串通过字符串拼接构造，易引入注入风险
- Struts2 应用中过度依赖 OGNL 表达式处理业务逻辑
- 使用老版本的 Struts2 或 OGNL 库

---

## Low Risk

以下情况可评为低风险：
- **严格 MemberAccess**：禁用静态方法调用、私有成员访问、类型转换
- **Struts2 安全配置**：`struts.ognl.allowStaticMethodAccess=false`、设置表达式长度限制
- **表达式白名单**：用户输入必须匹配预定义的安全表达式模式
- **只读属性访问**：表达式仅用于访问对象的只读属性，不调用方法
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **版本更新**：使用最新版本的 Struts2 和 OGNL，已修复已知漏洞
- **日志监控**：所有 OGNL 表达式解析操作均记录日志并实时监控异常模式

**注意**：OGNL 注入是 Struts2 框架的头号安全威胁，历史上导致大量 RCE 漏洞，必须严格限制 OGNL 表达式的使用范围。

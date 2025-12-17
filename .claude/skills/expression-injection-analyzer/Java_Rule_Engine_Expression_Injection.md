# Java 规则引擎表达式注入

**漏洞成因**：规则引擎（如 Drools、Easy-Rules、RuleBook）允许使用表达式语言（如 MVEL、SpEL、自定义 DSL）定义业务规则。当应用允许用户输入或外部数据作为规则的一部分时，攻击者可构造恶意规则表达式访问敏感对象、执行系统命令、修改应用状态等。常见于动态规则配置、业务规则管理系统、工作流引擎、策略引擎等场景。

---

## Details

**代码示例**：
```java
// 危险：使用 Drools 规则引擎，规则内容来自用户输入
import org.drools.core.impl.InternalKnowledgeBase;
import org.kie.api.KieServices;
import org.kie.api.builder.KieBuilder;
import org.kie.api.builder.KieFileSystem;

String userRule = request.getParameter("rule");
KieServices ks = KieServices.Factory.get();
KieFileSystem kfs = ks.newKieFileSystem();
kfs.write("src/main/resources/rules/userRule.drl", userRule); // 危险：用户提供的规则
KieBuilder kieBuilder = ks.newKieBuilder(kfs);
kieBuilder.buildAll();

// 危险的 Drools 规则示例（DRL 文件）
rule "User Rule"
when
    eval(userInput) // 用户输入作为条件表达式
then
    Runtime.getRuntime().exec("calc"); // 规则动作中执行系统命令
end

// 危险：使用 Easy-Rules，条件和动作来自用户输入
import org.jeasy.rules.api.Rule;
import org.jeasy.rules.core.BasicRule;

String condition = request.getParameter("condition");
String action = request.getParameter("action");
Rule rule = new BasicRule("userRule", condition, action); // 危险：用户定义规则

// 危险：使用 MVEL 表达式作为规则条件
import org.mvel2.MVEL;

String ruleCondition = "user.age > 18 && " + userInput; // 表达式拼接
Boolean result = (Boolean) MVEL.eval(ruleCondition, context);

// 攻击载荷示例（Drools MVEL）
// Runtime.getRuntime().exec("calc")
// java.lang.ProcessBuilder.("calc").start()
// new java.io.File("/etc/passwd").delete()

// 较安全：使用预定义的规则模板
String ruleTemplate = """
rule "Predefined Rule"
when
    $user : User(age > $minAge)
then
    $user.setStatus($newStatus);
end
""";
// 仅允许用户提供参数值，不允许修改规则结构

// 较安全：规则白名单验证
Set<String> allowedRuleIds = Set.of("rule1", "rule2", "rule3");
String ruleId = request.getParameter("ruleId");
if (allowedRuleIds.contains(ruleId)) {
    executeRule(ruleId);
}

// 较安全：限制规则引擎的上下文对象
Map<String, Object> context = new HashMap<>();
context.put("order", order); // 仅提供必要的数据对象，不包含敏感对象
```

**快速定位核心操作**：
- 关键词：`KieFileSystem`、`kfs.write`、`MVEL.eval`、`BasicRule`、`RuleBook`、`when-then`、`.drl` 文件
- 查找规则引擎的初始化和规则加载位置
- 追踪规则内容的来源：数据库、配置文件、用户输入、外部 API
- 检查规则中是否使用了表达式语言（MVEL、SpEL、Groovy）
- 关注规则的条件（when）和动作（then）部分的表达式
- 搜索依赖：`org.drools:drools-core`、`org.jeasy:easy-rules-core`、`com.deliveredtechnologies:rulebook-core`

**快速定位保护机制**：
- 规则来源是否仅限于可信的配置文件或数据库
- 是否使用了规则模板，用户仅能提供参数值
- 是否对规则内容进行了语法和语义验证
- 规则引擎上下文中是否包含敏感对象（Runtime、File、ClassLoader）
- 是否限制了规则中可调用的方法和类
- 是否使用了规则白名单或黑名单机制
- 规则执行是否在沙箱环境中进行
- 是否启用了规则审计和异常监控

**审计等级**：**L3-L4**
- **L3**：逐行分析规则加载逻辑，确认规则来源和内容
- **L4**：跨模块追踪规则定义、上下文配置、执行环境，验证安全限制

---

## Classify

**确认为漏洞**：
- 规则引擎加载用户输入或外部不可信数据作为规则内容
- 规则中使用了表达式语言（MVEL、SpEL）且未限制表达式能力
- 规则执行上下文中包含危险对象（Runtime、ProcessBuilder）
- 规则可通过反射或类加载机制访问任意类
- 未对规则内容进行验证或使用了不安全的规则解析器

**误报**：
- 规则内容来自可信的配置文件或硬编码常量
- 使用了规则模板，用户仅能提供参数值而非规则结构
- 规则引擎配置了严格的安全限制，禁用反射和危险方法调用
- 规则执行在沙箱环境中，且已限制系统权限

**代码异味**：
- 大量使用动态规则，增加攻击面和维护难度
- 规则内容通过字符串拼接构造，易引入注入风险
- 规则引擎上下文中注册了过多的对象和方法
- 缺乏规则版本管理和审计机制

---

## Low Risk

以下情况可评为低风险：
- **规则模板**：使用预定义的规则模板，用户仅能提供参数值
- **规则白名单**：仅允许执行预定义的规则集合
- **受限上下文**：规则引擎上下文仅包含必要的数据对象，不包含方法调用能力
- **规则验证**：所有规则在加载前进行语法和语义验证
- **沙箱执行**：规则在受限的 SecurityManager 或容器沙箱中执行
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **审计日志**：所有规则的加载和执行均记录日志并实时监控
- **最小权限**：规则引擎进程以最小权限运行，限制文件和网络访问

**注意**：规则引擎的灵活性也带来了安全风险，必须严格控制规则的来源和内容，避免执行不可信的规则。

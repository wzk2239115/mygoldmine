# Java 反射调用危险方法注入

**漏洞成因**：使用反射机制（`Method.invoke()`、`Constructor.newInstance()` 等）根据用户输入动态调用类方法，攻击者可通过构造恶意的类名、方法名来执行任意方法。

---

## Details

**代码示例**：
```java
// 危险：根据用户输入动态调用方法
String className = request.getParameter("class");
String methodName = request.getParameter("method");
Object target = Class.forName(className).newInstance();
Method method = target.getClass().getMethod(methodName);
method.invoke(target);

// 危险：反射调用 Runtime.exec()
String userClass = request.getParameter("cls");
String userMethod = request.getParameter("meth");
Object result = Class.forName(userClass).getMethod(userMethod).invoke(null);

// 危险：通过反射构造恶意对象
Constructor constructor = Class.forName(userInput).getConstructor(String.class);
Object malicious = constructor.newInstance("payload");

// 虚假安全：白名单检查不完整
List<String> whitelist = Arrays.asList("toString", "hashCode");
if (whitelist.contains(methodName)) {
    // 仍可能调用其他危险方法
    method.invoke(target);
}
```

**快速定位核心操作**（L2-L3）：
- 关键词：`Method.invoke(`、`.getMethod(`、`Constructor.newInstance(`、`Class.forName(`
- 查看类名和方法名来源：用户参数、配置、数据库
- 检查是否涉及字符串拼接构造方法调用
- 追踪数据流：`request.getParameter()`、`getInputStream()`

**快速定位保护机制**（L2-L4）：
- 是否存在严格的类/方法白名单：仅允许特定的安全类和方法
- 是否进行了类型检查：验证类是否继承自受信任的基类
- 是否禁止了访问权限修改：`setAccessible(true)` 的使用
- 是否对参数进行了验证：参数类型、个数检查

**审计等级**：**L3-L4**
- **L3**：逐行读取反射调用及其参数来源、白名单验证
- **L4**：跨模块追踪用户输入到反射调用的完整流程

---

## Classify

**确认为漏洞**：
- 类名或方法名来自用户可控输入
- 无白名单或白名单不完整
- 可调用 Runtime、ProcessBuilder、File 等危险类的方法

**误报**：
- 仅用于调用受信任的安全方法（如 toString()）
- 存在严格的白名单，完全限制可访问的类和方法
- 类名和方法名为硬编码常量

**代码异味**：
- 反射存在但有部分防护
- 权限控制依赖前端验证
- 业务可用直接方法调用替代反射

---

## Low Risk

以下情况可评为低风险：
- **严格的双层白名单**：既限制类，也限制方法
- **权限隔离**：反射调用在最小权限用户下
- **内网保护**：仅限管理员、开发者
- **参数验证**：参数类型、个数严格检查
- **审计监控**：反射调用被完整记录、监控

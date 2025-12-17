# Java Class.forName() 动态加载类注入

**漏洞成因**：使用 `Class.forName()` 根据用户输入动态加载类，攻击者可加载恶意的类（如 JDBC 驱动、反序列化 gadget 链中的类等），在类初始化时执行恶意代码。

---

## Details

**代码示例**：
```java
// 危险：直接加载用户输入的类名
String className = request.getParameter("class");
Class<?> clazz = Class.forName(className);
Object instance = clazz.newInstance();

// 危险：字符串拼接构造类名
String userInput = request.getParameter("driver");
Class.forName("com.jdbc." + userInput);

// 危险：JDBC 驱动加载
String driverClass = request.getParameter("db_driver");
Class.forName(driverClass);  // 可加载恶意 JDBC 驱动

// 虚假安全：try-catch 未隔离恶意代码
try {
    Class<?> clazz = Class.forName(userInput);
} catch (Exception e) {
    // 代码已经执行（静态初始化块）
}
```

**快速定位核心操作**（L1-L3）：
- 关键词：`Class.forName(`、`ClassLoader.loadClass(`、`.newInstance(`
- 查看类名来源：用户参数、配置、数据库
- 检查是否涉及字符串拼接构造类名
- 追踪数据流：`request.getParameter()`、`getInputStream()`

**快速定位保护机制**（L2-L3）：
- 是否存在类名白名单：仅允许加载特定的安全类
- 是否验证了类的来源：类路径检查、Package 检查
- 是否禁止了包含危险类的包：`java.lang.Runtime`, `java.lang.ProcessBuilder`
- 是否进行了异常处理：捕获 ClassNotFoundException

**审计等级**：**L1-L3**
- **L1**：关键词扫描，快速定位 Class.forName 调用
- **L2**：跳读确认类名来源、是否为用户可控
- **L3**：逐行读取类加载及其防护机制

---

## Classify

**确认为漏洞**：
- 类名来自用户可控输入
- 无白名单限制或白名单不完整
- 可加载恶意类或 gadget 链中的类

**误报**：
- 类名为硬编码常量
- 类名来自受信任源（配置文件、内部常量）
- 存在严格的白名单

**代码异味**：
- Class.forName 存在但有部分防护
- 权限控制依赖前端验证
- 业务可用直接导入替代动态加载

---

## Low Risk

以下情况可评为低风险：
- **严格的类名白名单**：仅允许加载特定安全类
- **权限隔离**：类加载在最小权限用户下
- **内网保护**：仅限管理员、开发者
- **包白名单**：禁止加载危险包中的类
- **审计监控**：类加载被完整记录、监控

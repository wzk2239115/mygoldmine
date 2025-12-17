# Go CodeInjection: Reflect Dynamic Call

## Details

### 核心操作示例

```go
// 高危示例：直接使用用户输入进行动态方法调用
package main

import (
	"fmt"
	"reflect"
)

type Handler struct{}

func (h *Handler) ProcessData(data string) string {
	return "processed: " + data
}

func (h *Handler) ExecuteCommand(cmd string) string {
	return "executed: " + cmd
}

// 漏洞代码
func DynamicCall(methodName string, arg string) {
	handler := &Handler{}
	handlerVal := reflect.ValueOf(handler)
	method := handlerVal.MethodByName(methodName)

	if method.IsValid() {
		// 未校验 methodName，直接调用任意方法
		result := method.Call([]reflect.Value{reflect.ValueOf(arg)})
		fmt.Println(result)
	}
}

// 使用示例
// DynamicCall("ProcessData", "user_input")       // 调用预期方法
// DynamicCall("ExecuteCommand", "rm -rf /")      // 调用不同方法或传递危险参数
// DynamicCall("UnexportedPrivate", "payload")    // 尝试调用私有方法
```

### 快速定位核心操作的技巧 **[L1:关键词扫描]**

重点扫描以下patterns：
- `MethodByName()` - 按名称动态获取方法
- `reflect.ValueOf()` + `.Call()` - 反射调用函数
- `CallByName` 或类似的自定义动态调用封装
- 用户输入直接作为方法名参数
- `reflect.Type.Method()` 与动态索引结合

关键搜索词：`MethodByName`, `Call(`, `reflect.Func`, `interface{}` 配合反射操作的地方

### 快速定位保护机制的技巧 **[L3:逐行读]**

审计重点：
1. **方法名白名单验证** - 是否存在调用前的方法名校验
   - 查找是否有map或slice存储允许的方法集合
   - 确认白名单逻辑是否在反射操作之前执行

2. **参数类型校验** - 反射调用前的参数有效性验证
   - 检查 `method.Type()` 获取方法签名后是否做参数匹配
   - 确认参数是否经过消毒处理

3. **权限上下文检查** - 调用者权限是否被校验
   - 判断动态调用前是否进行了身份验证
   - 确认是否有操作权限的ACL检查

4. **日志审计** - 动态调用是否被记录
   - 确认高风险反射操作是否有审计日志
   - 查看是否记录了调用方法名、参数、调用者身份

## Classify

### 漏洞研判标准

**确认为漏洞的条件：**
1. **用户输入可直接影响方法名** - 无论是get参数、post参数、header还是文件内容，只要未经验证就用于反射调用
2. **调用的方法非预期集合** - 动态调用允许访问非业务逻辑所需的方法集合，扩大了攻击面
3. **敏感方法可被调用** - 能够调用执行os命令、数据库操作、文件系统操作、权限提升的方法
4. **参数注入无防护** - 方法参数同样来自用户输入且未做校验

**区分误报的关键点：**
- 方法名从硬编码常量或受信来源（配置文件/数据库预定义值）获取，非直接用户输入
- 虽有反射操作但只涉及内部自定义类型转换，无涉及可执行操作的方法
- 反射用于框架层的正常路由分发，且已有强制的中间件权限检查

**代码异味指标：**
- 存在 `reflect.ValueOf().MethodByName()` 但无对应的白名单实现
- 动态获取方法后直接调用，未检查返回的方法是否有效
- 用户输入与反射操作之间没有任何过滤/转换层
- 调用链中存在多层反射嵌套，增加了追踪复杂性

## Low risk

以下场景应评为低风险：

1. **预定义的方法集合** - 程序启动时初始化的方法映射表，后续反射操作只从该表中读取，且表内容经过严格审核

2. **框架级路由机制** - Web框架（gin、echo等）内部的反射调用机制，已验证过方法名合法性，且有整体的权限控制层

3. **序列化/反序列化场景** - 反射用于JSON/Protocol Buffer解析和结构体赋值，涉及的是数据映射而非方法执行

4. **纯粹的类型转换** - 反射仅用于类型检查和字段访问，未涉及方法动态调用

5. **受限的方法集** - 即使有动态调用，也仅限于获取器/设置器类的无害方法，且这些方法不执行任何业务逻辑

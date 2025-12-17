# C_SSTI_Template_Library_User_Input

**漏洞类型**: C/C++ 模板库中用户输入未正确处理导致注入

---

## Details

### 代码示例

**易受攻击的代码模式**:
```cpp
// C++ 模板引擎库使用不当可能导致 SSTI

// 场景1：inja 模板库不安全使用
#include <inja/inja.hpp>
using namespace inja;

// 危险：直接渲染用户提供的模板字符串
std::string user_template = request.get_param("template");
Environment env;
Template tmpl = env.parse(user_template);
std::string result = env.render(tmpl, json_data);

// 场景2：Jinja2Cpp 禁用转义
#include <jinja2cpp/template.h>
jinja2::Template tpl;
// 危险：加载用户可控的模板
tpl.Load(user_template_string);
// 如果未启用自动转义
jinja2::ValuesMap params = {{"user_data", user_input}};
std::string output = tpl.RenderAsString(params).value();

// 场景3：使用 {{ }} 表达式直接执行代码
// inja 模板中: {{ system("id") }} 或 {{ __import__("os").system("cmd") }}
// 取决于模板引擎的功能限制

// 场景4：模板路径用户可控
std::string template_name = request.query["tpl"];
env.render_file(template_name + ".html", json_data);

// 场景5：自定义回调函数暴露危险功能
Environment env;
// 危险：注册了可执行系统命令的函数
env.add_callback("exec", 1, [](Arguments& args) {
    std::string cmd = args.at(0)->get<std::string>();
    return system(cmd.c_str());
});
// 模板中: {{ exec("rm -rf /") }}

// 场景6：C 风格模板处理（自定义实现）
typedef struct {
    char* key;
    char* value;
} TemplateVar;

void replace_vars(char* template_str, TemplateVar* vars, int count) {
    for (int i = 0; i < count; i++) {
        char placeholder[256];
        sprintf(placeholder, "{{%s}}", vars[i].key);
        char* pos = strstr(template_str, placeholder);
        if (pos) {
            // 危险：未检查边界的字符串替换
            strcpy(pos, vars[i].value);
        }
    }
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板库: `inja`, `jinja2cpp`, `mustache`, `tera`, `handlebars`
- 渲染方法: `.render()`, `.parse()`, `.Load()`, `.RenderAsString()`
- 回调函数: `.add_callback()`, `.add_filter()`, `registerFunction()`
- 用户输入: `request.get()`, `argv`, `cin`, `getline()`
- 配置: `autoescape`, `strict_mode`, `sandbox`

**L2 跳读定位**:
- 从用户输入追踪到模板引擎的 parse/render 方法
- 检查模板字符串来源是否可控
- 搜索 add_callback/add_filter 注册的函数
- 定位模板文件路径的构造方式
- 关注 Environment/Template 的配置选项

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 自动转义: autoescape 配置启用
- 模板白名单: 模板名称白名单验证
- 回调限制: 仅注册安全的回调函数
- 沙箱模式: 限制可访问的功能
- 输入验证: 模板内容经过验证

**L3 逐行分析**:
- Environment 配置:
  - autoescape 是否启用
  - 模板目录是否限制
  - 是否启用 strict_mode
  - 错误处理配置是否安全
- 模板来源:
  - parse() 参数是否来自用户输入
  - render_file() 路径是否可控
  - Load() 是否加载用户提供的模板
- 回调函数:
  - add_callback 注册的函数是否安全
  - 回调是否能执行系统命令
  - 回调是否访问危险对象
  - 函数参数是否经过验证
- 数据传递:
  - ValuesMap/json 数据是否包含危险对象
  - 变量类型是否限制为基本类型
  - 是否传递了指针或函数指针
- C 风格处理:
  - strcpy/sprintf 是否检查边界
  - 字符串替换是否安全
  - 是否使用了安全的字符串函数

**L4 跨模块追踪**:
- 追踪从 HTTP 请求 → 参数解析 → 模板渲染的流程
- 检查模板引擎库的版本和已知漏洞
- 验证回调函数的实现和权限
- 检查模板文件的访问控制
- 追踪全局 Environment 对象的配置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为模板字符串 parse/render
- add_callback 注册了可执行系统命令的函数
- 模板文件路径完全由用户输入决定
- 禁用了 autoescape 且输出用户数据
- 回调函数未验证参数直接执行

**误报判定**:
- 模板完全预定义，用户仅控制数据值
- 启用 autoescape 且无危险回调
- 模板名称经过严格白名单验证
- 回调函数仅执行安全操作
- 使用了成熟库的安全配置

**代码异味**:
- add_callback 注册了复杂的函数
- 模板路径通过字符串拼接构造
- 自定义的 C 风格模板处理器
- 未启用模板引擎的安全选项
- 大量使用不安全的字符串函数
- 模板引擎库版本过低
- 回调函数未经安全审计

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染仅限内部使用
- 需要强身份验证
- 功能部署在隔离环境
- 严格访问控制和审计

**架构设计防护**:
- 使用成熟模板库的默认安全配置
- 强制启用 autoescape
- 模板全部预加载和验证
- 禁止注册危险的回调函数
- 实现 CSP 策略

**输入与输出保护**:
- 模板名称严格白名单验证
- 禁止用户输入作为模板内容
- 回调函数参数经过类型和值验证
- 所有输出经过转义处理
- 路径规范化后检查前缀

**监控与运行环保**:
- 应用在容器/沙箱中运行
- 模板目录只读挂载
- 启用系统级安全机制（SELinux等）
- 完整的审计日志
- 实时监控异常模板访问
- 依赖库定期更新和扫描

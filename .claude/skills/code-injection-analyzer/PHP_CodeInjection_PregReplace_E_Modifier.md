# PHP 代码注入：preg_replace() /e 修饰符执行用户输入

## Details

### 漏洞成因

PHP 的 `preg_replace()` 函数在使用 `/e` 修饰符时，将替换字符串作为 PHP 代码进行评估执行。当替换字符串（第二个参数）或匹配模式中包含用户可控数据时，攻击者可通过精心构造的输入注入任意 PHP 代码。虽然 `/e` 修饰符在 PHP 5.5.0 中已被废弃，在 PHP 7.0.0 中已被移除，但历史代码或老版本 PHP 系统仍可能存在此漏洞。关键风险在于：(1) `/e` 修饰符自动将替换字符串作为代码执行；(2) 正则表达式本身也可能包含代码注入；(3) 回溯引用（`$1`、`$2`）特性强化了攻击威力。

### 代码示例

```php
// 危险示例 1：替换字符串包含用户输入
$text = $_GET['text'];
$pattern = '/test/e';
$replacement = 'strtoupper("' . $_GET['replacement'] . '")';
$result = preg_replace($pattern, $replacement, $text);
// 攻击: replacement="); system('whoami'); die("

// 危险示例 2：直接传递用户输入到替换字符串
$user_search = $_POST['search'];
$user_replace = $_POST['replace'];
$result = preg_replace('/' . $user_search . '/e', $user_replace, $input_text);
// 攻击: search=.*; replace=system('rm -rf /')

// 危险示例 3：回溯引用与用户数据组合
$pattern = '/name=([^&]*)/e';
$replacement = 'echo "Hello " . $1 . ", your data: " . $_GET["data"]';
$result = preg_replace($pattern, $replacement, $query_string);
// 攻击: 在 URL 中注入 data=system('whoami')

// 危险示例 4：嵌套 preg_replace
$user_pattern = $_GET['pattern'];
$callback_code = 'return md5($1);';
$result = preg_replace('/' . $user_pattern . '/e', 'strtolower($1)', $text);
// 攻击: pattern=.*); system('id'); // 注释符会导致后续代码执行

// 危险示例 5：来自数据库的用户数据
$replacement = $db->query("SELECT replacement FROM templates WHERE id = ?");
$result = preg_replace('/oldtext/e', $replacement, $content);
// 攻击：数据库中被污染的替换字符串（二阶注入）
```

### 快速定位核心操作 `[L1:关键词扫描]`

**关键函数识别：**
- 搜索关键词：`preg_replace`、`/e` 修饰符、正则表达式中的 `e` 标志
- 示例搜索模式：
  ```
  preg_replace\s*\(\s*['/"].*\/e
  preg_replace\s*\(\s*\$.*\/e
  preg_replace.*\/e.*\$_
  ```

**危险标记识别：**
- `preg_replace()` 的第一个参数（模式）包含用户输入且带 `/e` 修饰符
- `preg_replace()` 的第二个参数（替换字符串）包含用户输入或用户数据
- 替换字符串中存在变量插值（如 `"$_GET['key']"`）或字符串拼接
- 使用了回溯引用（`$1`、`$2` 等），而原始匹配包含用户数据
- 模式或替换来自数据库查询结果或其他不可信源

**详细定位技巧 `[L2:跳读]`：**
- 定位每个 `preg_replace()` 调用，检查是否使用了 `/e` 修饰符
- 回溯第一个参数（模式）的来源，判断是否受用户输入影响
- 回溯第二个参数（替换字符串）的来源，标记所有用户可控的部分
- 检查替换字符串中是否使用了回溯引用及其对应的匹配组内容
- 对于数据库来源的替换字符串，需要追踪数据的注入点

### 快速定位保护机制 `[L3:逐行读]`

**输入验证与转义层：**
- 搜索在 `preg_replace()` 前的验证函数
  ```php
  // 有效的保护示例
  if (!preg_match('/^[a-zA-Z0-9_]+$/', $user_input)) {
      die('Invalid input');
  }
  $result = preg_replace('/test/e', $user_input, $text);
  ```
- 检查是否对模式进行了白名单验证
- 检查是否对替换字符串进行了 HTML 编码、HTML 实体转义或其他过滤
- 检查是否使用了 `quotemeta()` 或 `preg_quote()` 对正则特殊字符进行转义

**代码替代方案检查 `[L2:跳读]`：**
- 搜索是否改用了 `preg_replace_callback()` 替代 `/e` 修饰符
  ```php
  // 更安全的替代方案
  $result = preg_replace_callback(
      '/test/',
      function($matches) {
          return strtoupper($matches[0]);
      },
      $text
  );
  ```
- 检查是否使用了 `str_replace()`、`strtr()` 等非正则替换函数
- 确认是否使用了现代的模板引擎或字符串处理库

**环境和版本检查 `[L4:跨模块追踪]`：**
- 检查 PHP 版本是否低于 7.0.0（如果是，/e 修饰符仍可用）
- 查看是否有全局的 `disable_functions` 配置来限制代码执行
- 检查是否在特定的、受限的执行上下文中（如沙箱、特定权限用户）
- 查看是否有框架级的防护措施（如 ORM 或模板引擎的自动转义）

---

## Classify

### 确认为漏洞的必要条件

**漏洞判定流程：**

1. **识别 /e 修饰符的使用**：
   - PHP 版本 < 7.0.0 且代码中存在 `preg_replace()` 的 `/e` 修饰符
   - `/e` 修饰符在 PHP 5.5.0+ 已废弃，但仍可执行；在 PHP 7.0.0+ 中会导致编译错误

2. **验证用户输入可达性**：
   - 模式（第一个参数）或替换字符串（第二个参数）包含用户可控数据
   - 用户数据来自 `$_GET`、`$_POST`、`$_COOKIE`、`$_REQUEST`、`$_FILES`、`$_SERVER` 等
   - 用户数据也可能来自数据库查询结果、文件读取等间接源（二阶注入）

3. **验证充分性评估**：
   - **无验证**：用户输入直接传递 → 漏洞
   - **部分验证**：验证了部分属性但遗漏关键检查 → 可能是漏洞
   - **充分验证**：所有可能危险的输入都通过白名单验证 → 低风险或误报

### 误报判定标准

- **模式和替换均为常量或内部生成**：
  ```php
  $result = preg_replace('/test/e', 'return "success";', $text);
  // 两个参数都来自源代码，无用户输入
  ```

- **用户输入经过完整的白名单验证**：
  ```php
  $allowed_replacements = ['hello' => 'Hi', 'bye' => 'Goodbye'];
  if (!array_key_exists($_GET['repl'], $allowed_replacements)) {
      die('Invalid replacement');
  }
  $result = preg_replace('/test/e', $allowed_replacements[$_GET['repl']], $text);
  ```

- **PHP 版本 >= 7.0.0**：
  - `/e` 修饰符已被移除，代码将抛出编译错误，无法执行
  - 需要确认代码实际运行的 PHP 版本

- **用户输入被正确转义**：
  ```php
  $user_repl = preg_quote($_GET['replacement']);
  $result = preg_replace('/test/e', $user_repl, $text);
  // 虽然 preg_quote() 可转义正则符号，但仍无法完全防止代码注入
  ```

- **模式和替换来自可信的、经过审核的静态源**：
  - 配置文件中硬编码的值
  - 仅由系统管理员修改的设置

### 代码异味识别

- **使用了 `/e` 修饰符但没有明确的代码验证注释**：表明开发者可能未意识到风险
- **混合使用 preg_replace() 和用户输入**：即使当前没有直接漏洞，也表明风险意识不足
- **回溯引用与可控数据结合**：如 `$1` 或 `$2` 包含用户输入的匹配结果
- **多层函数调用链**：用户输入通过多个函数传递到 `preg_replace()` 的模式或替换参数
- **数据库驱动的模式或替换**：表明二阶注入的可能性，需要详细追踪
- **缺乏版本检查的历史代码**：老版本 PHP 代码被迁移到新版本但未更新

---

## Low risk

### 低风险评级场景

**场景一：完整的输入白名单验证**
- 模式和替换字符串都来自预定义的、有限的白名单集合
- 白名单在代码中硬编码或由管理员控制的配置文件提供
- 用户输入仅用于索引或选择白名单中的条目
- 示例：
  ```php
  $patterns = [
      'greet' => ['pattern' => '/hello/e', 'replacement' => '"Hi"'],
      'farewell' => ['pattern' => '/bye/e', 'replacement' => '"Goodbye"']
  ];
  if (!isset($patterns[$_GET['type']])) {
      die('Invalid type');
  }
  $result = preg_replace($patterns[$_GET['type']]['pattern'],
                         $patterns[$_GET['type']]['replacement'], $text);
  ```
- 评级依据：白名单限制了可能的模式和替换，攻击面消除

**场景二：PHP 版本 >= 7.0.0**
- 确认代码运行的实际 PHP 版本是 7.0.0 或更高
- `/e` 修饰符在 PHP 7.0.0+ 中被完全移除
- 使用 `/e` 修饰符的代码会导致编译错误而不是执行
- 评级依据：版本限制使得漏洞无法利用

**场景三：使用了安全的替代方案**
- 代码已改用 `preg_replace_callback()` 替代 `/e` 修饰符
- 回调函数对返回值进行了充分的清理和验证
- 示例：
  ```php
  $result = preg_replace_callback('/\$(\w+)/', function($matches) {
      $var_name = $matches[1];
      if (!ctype_alnum($var_name)) {
          return $matches[0]; // 返回原始匹配
      }
      return isset($GLOBALS[$var_name]) ? $GLOBALS[$var_name] : '';
  }, $text);
  ```
- 评级依据：回调函数提供了更好的控制和验证机制

**场景四：模式和替换完全由应用内部生成**
- 用户输入仅影响待处理的文本（`preg_replace()` 的第三个参数）
- 模式和替换字符串来自硬编码或不受用户影响的源
- 示例：
  ```php
  // 用户可控的仅是 $text，不影响模式和替换
  $text = $_GET['content'];
  $result = preg_replace('/old/e', '"new"', $text);
  ```
- 评级依据：用户输入无法影响执行的代码

**场景五：严格的输入格式验证**
- 用户输入经过严格的格式验证，限制了可能的特殊字符
- 验证确保输入仅包含安全的字符集（如仅字母数字）
- 示例：
  ```php
  if (!preg_match('/^[a-zA-Z0-9_]+$/', $_GET['tag'])) {
      die('Invalid tag');
  }
  $result = preg_replace('/old/e', 'return strtoupper("' . $_GET['tag'] . '");', $text);
  ```
- 评级依据：字符集限制防止了代码注入字符的使用

**场景六：隔离的执行环境**
- 代码运行在沙箱、容器或受严格权限限制的用户下
- 即使 `/e` 修饰符执行代码，也无法访问敏感资源或执行危险操作
- 示例：在容器内运行，且没有系统命令执行权限
- 评级依据：环境隔离限制了漏洞的影响范围

**场景七：非网络可达的代码路径**
- `preg_replace()` 的 `/e` 修饰符使用位于非网络可访问的代码路径
- 仅在命令行脚本、定时任务或管理员手动触发的场景中使用
- 示例：在 CLI 脚本中处理本地文件，无网络输入
- 评级依据：攻击者无法通过常规网络通道触发

### 评级决策补充

- **仅验证了模式但未验证替换字符串** → 中等风险或高风险
  - 例：检查了模式的合法性但替换字符串来自用户

- **使用了部分转义但不完整** → 中等风险或高风险
  - 例：只转义了引号但未处理其他特殊字符

- **回溯引用中包含用户匹配结果** → 中等风险或高风险
  - 例：虽然模式本身安全，但 `$1` 包含用户输入的匹配内容

- **二阶注入：数据库驱动的替换字符串** → 需详细分析
  - 例：从数据库读取替换字符串，需要追踪数据的初始来源

- **存在版本依赖但版本检查不清晰** → 需要验证实际运行版本
  - 例：代码要求 PHP < 7.0.0 但部署环境版本不确定

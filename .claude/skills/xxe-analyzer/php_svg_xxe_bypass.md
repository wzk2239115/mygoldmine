# PHP｜SVG文件XXE绕过漏洞

## Details

### 漏洞成因
SVG（可缩放矢量图形）文件本质上是一种XML格式，支持包含外部实体引用。在PHP应用中，当用户上传的SVG文件被服务器解析处理（如图片预览、尺寸调整、格式转换）时，如果XML解析器未正确禁用外部实体，攻击者可以通过构造恶意的SVG文件实现XXE攻击。这种攻击特别危险，因为它绕过了传统的文件类型检查，利用的是"图片处理"这一看似安全的功能点。

### 代码示例

**易受攻击的代码 - SVG文件上传处理：**
```php
// 危险的SVG文件处理
if ($_FILES['svg_file']['type'] === 'image/svg+xml') {
    $svg_content = file_get_contents($_FILES['svg_file']['tmp_name']);
    
    // 使用DOMDocument解析SVG - 默认启用外部实体
    $dom = new DOMDocument();
    $dom->loadXML($svg_content); // 危险：可能触发XXE
    
    // 提取SVG尺寸信息
    $svg = $dom->getElementsByTagName('svg')->item(0);
    $width = $svg->getAttribute('width');
    $height = $svg->getAttribute('height');
    
    echo "SVG dimensions: {$width}x{$height}";
}
```

**攻击示例 - 恶意SVG文件：**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE svg [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
  <!ENTITY xxe2 SYSTEM "http://internal-server.com/secret">
]>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <text x="10" y="20">&xxe;</text>
  <circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />
  <!-- 外部实体内容会被解析 -->
</svg>
```

**易受攻击的代码 - 图片处理库：**
```php
// 使用ImageMagick处理SVG
$image = new Imagick();
$image->readImageBlob($svg_content); // 可能触发XXE
$image->resizeImage(200, 200, Imagick::FILTER_LANCZOS, 1);
$image->setImageFormat('png');
```

**易受攻击的代码 - SVG压缩/优化：**
```php
// SVG优化处理
$svg = simplexml_load_string($svg_content); // 危险：默认启用外部实体

// 遍历所有元素进行优化
foreach ($svg->xpath('//*') as $element) {
    // 处理元素属性
    optimizeAttributes($element);
}

// 保存优化后的SVG
$optimized = $svg->asXML();
```

**安全示例 - 禁用外部实体的SVG处理：**
```php
class SecureSVGHandler {
    
    public function processSVG($svg_content) {
        // 方法1：使用libxml选项禁用外部实体
        $previous = libxml_disable_entity_loader(true);
        $dom = new DOMDocument();
        
        // 禁用加载外部实体
        $oldValue = libxml_use_internal_errors(true);
        
        if (@$dom->loadXML($svg_content, LIBXML_NONET | LIBXML_NOENT)) {
            // 安全处理SVG
            $this->extractSVGInfo($dom);
        } else {
            throw new Exception('Invalid SVG format');
        }
        
        libxml_disable_entity_loader($previous);
        libxml_use_internal_errors($oldValue);
        
        return true;
    }
    
    public function processSVGSecurely($svg_content) {
        // 方法2：使用XMLReader进行流式解析
        $reader = new XMLReader();
        $reader->XML($svg_content);
        
        // 禁用外部实体加载
        $reader->setParserProperty(XMLReader::SUBST_ENTITIES, false);
        
        while ($reader->read()) {
            if ($reader->nodeType === XMLReader::ELEMENT) {
                // 安全处理元素，不加载外部实体
                $this->processElement($reader);
            }
        }
        
        $reader->close();
    }
    
    // 方法3：使用安全的SVG专用库
    public function validateSVGStructure($svg_content) {
        // 首先进行结构验证，不包含解析
        if (!$this->isValidSVGStructure($svg_content)) {
            throw new Exception('SVG structure validation failed');
        }
        
        // 使用正则表达式提取基础信息（不解析XML）
        return $this->extractBasicInfo($svg_content);
    }
    
    private function isValidSVGStructure($content) {
        // 基础结构检查，不解析XML实体
        $pattern = '/^\s*<\?xml.*?\?>\s*<svg[^>]*>/i';
        return preg_match($pattern, $content) === 1;
    }
    
    private function extractBasicInfo($content) {
        // 使用正则安全提取属性，不解析XML
        $info = [];
        
        if (preg_match('/<svg[^>]*width=["\']([^"\']+)["\']/i', $content, $matches)) {
            $info['width'] = $matches[1];
        }
        
        if (preg_match('/<svg[^>]*height=["\']([^"\']+)["\']/i', $content, $matches)) {
            $info['height'] = $matches[1];
        }
        
        return $info;
    }
}
```

**安全示例 - SVG上传验证：**
```php
class SVGUploadValidator {
    
    public function validateUpload($file) {
        // 1. MIME类型检查
        $finfo = finfo_open(FILEINFO_MIME_TYPE);
        $mime_type = finfo_file($finfo, $file['tmp_name']);
        finfo_close($finfo);
        
        if ($mime_type !== 'image/svg+xml') {
            throw new Exception('Invalid MIME type');
        }
        
        // 2. 内容检查 - 查找危险模式
        $content = file_get_contents($file['tmp_name']);
        
        // 检查DOCTYPE和实体定义
        if (stripos($content, '<!DOCTYPE') !== false || 
            stripos($content, '<!ENTITY') !== false) {
            throw new Exception('SVG contains DOCTYPE or ENTITY definitions');
        }
        
        // 3. 安全解析验证
        return $this->safeParseValidation($content);
    }
    
    private function safeParseValidation($content) {
        // 使用XMLReader进行安全解析
        $reader = new XMLReader();
        
        // 设置安全选项
        $previous = libxml_disable_entity_loader(true);
        libxml_use_internal_errors(true);
        
        try {
            $reader->XML($content);
            
            while ($reader->read()) {
                // 检查节点类型
                if ($reader->nodeType === XMLReader::ELEMENT) {
                    // 验证元素名称
                    if (!$this->isSafeElement($reader->localName)) {
                        throw new Exception('Potentially dangerous element: ' . $reader->localName);
                    }
                }
            }
            
            return true;
            
        } finally {
            $reader->close();
            libxml_disable_entity_loader($previous);
            libxml_clear_errors();
        }
    }
    
    private function isSafeElement($elementName) {
        // 允许的SVG元素白名单
        $safe_elements = [
            'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon',
            'text', 'tspan', 'tref', 'textPath', 'defs', 'clipPath', 'mask', 'pattern',
            'image', 'switch', 'foreignObject', 'use', 'symbol', 'marker', 'linearGradient',
            'radialGradient', 'stop', 'animate', 'animateMotion', 'animateTransform', 'set'
        ];
        
        return in_array(strtolower($elementName), $safe_elements);
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- SVG处理：`image/svg+xml`, `svg`, `DOMDocument`, `SimpleXMLElement`
- XML解析：`loadXML`, `simplexml_load_string`, `XMLReader`
- 文件处理：`file_get_contents`, `readImageBlob`

**定位步骤：**
1. 搜索项目中所有SVG文件处理逻辑
2. 检查XML解析器的使用方式
3. 验证是否禁用外部实体加载
4. 检查文件上传的SVG处理流程

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **实体加载禁用：** `libxml_disable_entity_loader(true)`
- **安全解析选项：** `LIBXML_NONET`, `LIBXML_NOENT`
- **白名单验证：** 允许的SVG元素和属性限制
- **内容检查：** 危险模式（DOCTYPE/ENTITY）检测

**定位技巧：**
- 检查是否使用XMLReader而非DOMDocument/SimpleXML
- 确认是否禁用外部实体加载
- 验证是否进行内容级别的安全检查
- 检查文件上传流程中的SVG处理

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| XMLReader+实体禁用 | **L0（快速跳过）** | 安全配置 |
| 有实体禁用但解析器不安全 | **L2（跳读）** | 需验证解析方式 |
| 使用DOMDocument无防护 | **L3（逐行读）** | 高风险配置 |
| 完全无SVG安全检查 | **L4（跨模块追踪）** | 严重缺失 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 使用DOMDocument/SimpleXML解析SVG且未禁用外部实体
2. 未对SVG内容进行XXE安全检查
3. SVG文件处理流程中存在XML解析步骤
4. 允许用户上传或提供SVG文件内容

#### 误报
以下情景可判定为误报：
1. 使用XMLReader并禁用外部实体加载
2. 进行内容级别的XXE安全检查
3. 使用正则表达式提取信息而非XML解析
4. 完全禁止SVG文件处理

#### 代码异味
需记录的风险：
1. 仅在部分SVG处理流程中实施安全检查
2. 动态生成的XML内容存在注入风险
3. 不同的SVG处理函数安全级别不一致
4. 未验证SVG文件来源的可靠性

## Low risk

### 低风险评级场景

#### 1. 正则表达式提取
- **场景：** 仅使用正则表达式提取SVG基础信息，不解析XML
- **风险评估：** 避免了XML解析风险，相对安全

#### 2. 白名单文件处理
- **场景：** 严格限制SVG文件来源和处理方式
- **风险评估：** 降低了攻击面，风险可控

#### 3. 现代安全库
- **场景：** 使用专门的SVG安全处理库
- **风险评估：** 专业库通常考虑了安全因素

### SVG XXE攻击向量

| 攻击方法 | 适用条件 | 检测方法 | 防护建议 |
|----------|----------|----------|----------|
| 文件读取 | 实体未禁用 | 实体加载检查 | 禁用外部实体 |
| SSRF攻击 | 允许外部URL | 网络请求检测 | 限制网络访问 |
| 内网扫描 | 服务器端请求 | 目标地址检查 | 内网隔离 |
| DoS攻击 | 递归实体 | 实体嵌套检查 | 实体深度限制 |

### SVG特定风险点

| SVG特性 | 风险描述 | 检测要点 | 防护措施 |
|----------|----------|----------|----------|
| 外部图像 | xlink:href属性 | 外部链接检查 | 禁止外部资源 |
| 脚本元素 | <script>标签 | 脚本内容检测 | 禁止脚本执行 |
| 事件处理 | on*属性 | 事件处理器检测 | 过滤事件属性 |
|  foreignObject | HTML注入 | 内容安全检查 | 限制HTML内容 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 实体加载禁用 | 消除XXE基础 | 高 |
| 安全解析器 | 现代安全API | 高 |
| 内容白名单 | 严格输入控制 | 高 |
| 文件来源控制 | 降低攻击面 | 中 |
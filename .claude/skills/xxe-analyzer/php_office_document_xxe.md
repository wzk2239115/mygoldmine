# PHP｜Office文档XXE绕过漏洞

## Details

### 漏洞成因
现代Office文档（DOCX、XLSX、PPTX等）本质上是以XML为基础的ZIP压缩包格式（Open XML标准）。当PHP应用处理用户上传的Office文档时，如果文档解析器未正确禁用外部实体，攻击者可以通过构造恶意的Office文档实现XXE攻击。这类攻击特别隐蔽，因为Office文档通常被视为"安全"的文件类型，且传统的文件类型检查无法检测到其中嵌入的XML外部实体威胁。

### 代码示例

**易受攻击的代码 - Office文档解析：**
```php
// 危险的Office文档处理
if (in_array($file_extension, ['docx', 'xlsx', 'pptx'])) {
    $zip = new ZipArchive();
    if ($zip->open($uploaded_file) === TRUE) {
        
        // 提取并解析核心XML文档
        $core_xml = $zip->getFromName('docProps/core.xml'); // Word文档属性
        $content_xml = $zip->getFromName('word/document.xml'); // Word内容
        
        // 使用DOMDocument解析XML - 默认启用外部实体
        $dom = new DOMDocument();
        $dom->loadXML($core_xml); // 危险：可能触发XXE
        
        // 提取文档属性
        $title = $dom->getElementsByTagName('title')->item(0)->nodeValue;
        $author = $dom->getElementsByTagName('creator')->item(0)->nodeValue;
        
        echo "Document: $title by $author";
        $zip->close();
    }
}
```

**攻击示例 - 恶意DOCX文档结构：**
```
malicious.docx (ZIP格式):
├── [Content_Types].xml
├── _rels/
├── docProps/
│   └── core.xml (包含XXE Payload)
├── word/
│   ├── _rels/
│   ├── document.xml
│   └── settings.xml
└── xl/
    └── sharedStrings.xml (Excel中的XXE)
```

**恶意core.xml内容：**
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE coreProperties [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
  <!ENTITY internal SYSTEM "http://internal-server:8080/admin/config">
]>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties">
  <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">&xxe;</dc:title>
  <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">&internal;</dc:creator>
  <cp:lastModifiedBy>Admin</cp:lastModifiedBy>
</cp:coreProperties>
```

**易受攻击的代码 - Excel文档处理：**
```php
// Excel XLSX处理
if ($file_extension === 'xlsx') {
    $zip = new ZipArchive();
    $zip->open($uploaded_file);
    
    // 处理共享字符串（常见XXE攻击点）
    $shared_strings = $zip->getFromName('xl/sharedStrings.xml');
    
    // 危险的XML解析
    $xml = simplexml_load_string($shared_strings); // XXE风险
    
    foreach ($xml->si as $string_item) {
        $text = (string)$string_item->t;
        // 外部实体内容会被解析并显示
        processCellValue($text);
    }
    
    $zip->close();
}
```

**易受攻击的代码 - PowerPoint处理：**
```php
// PowerPoint PPTX处理
if ($file_extension === 'pptx') {
    $zip = new ZipArchive();
    $zip->open($uploaded_file);
    
    // 处理幻灯片内容
    $slide_content = $zip->getFromName('ppt/slides/slide1.xml');
    
    // 使用XMLReader处理（默认配置下仍可能风险）
    $reader = new XMLReader();
    $reader->XML($slide_content);
    
    while ($reader->read()) {
        if ($reader->nodeType === XMLReader::ELEMENT && $reader->localName === 't') {
            // 文本内容可能包含解析后的实体
            $text_content = $reader->readString();
            echo $text_content; // 可能包含敏感信息
        }
    }
    
    $reader->close();
    $zip->close();
}
```

**安全示例 - 安全的Office文档处理：**
```php
class SecureOfficeDocumentHandler {
    
    public function extractDocumentInfo($file_path) {
        $zip = new ZipArchive();
        if ($zip->open($file_path) !== TRUE) {
            throw new Exception('Failed to open Office document');
        }
        
        try {
            // 方法1：使用正则表达式安全提取基础信息
            $info = $this->extractBasicInfoRegex($zip);
            
            // 方法2：如果必须解析XML，使用安全配置
            if (empty($info)) {
                $info = $this->extractInfoSecureXML($zip);
            }
            
            return $info;
            
        } finally {
            $zip->close();
        }
    }
    
    private function extractBasicInfoRegex($zip) {
        // 安全的方法：使用正则表达式提取基础信息
        $info = [];
        
        // 尝试从core.xml中提取基础信息
        $core_xml = $zip->getFromName('docProps/core.xml');
        if ($core_xml !== false) {
            // 安全提取标题
            if (preg_match('/<dc:title[^>]*>([^<]+)<\/dc:title>/i', $core_xml, $matches)) {
                $info['title'] = htmlspecialchars($matches[1], ENT_QUOTES, 'UTF-8');
            }
            
            // 安全提取创建者
            if (preg_match('/<dc:creator[^>]*>([^<]+)<\/dc:creator>/i', $core_xml, $matches)) {
                $info['creator'] = htmlspecialchars($matches[1], ENT_QUOTES, 'UTF-8');
            }
            
            // 安全提取修改时间
            if (preg_match('/<dcterms:modified[^>]*>([^<]+)<\/dcterms:modified>/i', $core_xml, $matches)) {
                $info['modified'] = htmlspecialchars($matches[1], ENT_QUOTES, 'UTF-8');
            }
        }
        
        return $info;
    }
    
    private function extractInfoSecureXML($zip) {
        // 安全的XML解析方法
        $info = [];
        
        // 禁用外部实体加载
        $previous = libxml_disable_entity_loader(true);
        libxml_use_internal_errors(true);
        
        try {
            $core_xml = $zip->getFromName('docProps/core.xml');
            if ($core_xml !== false) {
                // 方法1：使用XMLReader（推荐）
                $info = $this->parseWithXMLReader($core_xml);
                
                if (empty($info)) {
                    // 方法2：使用DOMDocument（安全配置）
                    $info = $this->parseWithDOMDocument($core_xml);
                }
            }
            
            return $info;
            
        } finally {
            libxml_disable_entity_loader($previous);
            libxml_clear_errors();
        }
    }
    
    private function parseWithXMLReader($xml_content) {
        $info = [];
        $reader = new XMLReader();
        
        try {
            $reader->XML($xml_content);
            $reader->setParserProperty(XMLReader::SUBST_ENTITIES, false);
            
            while ($reader->read()) {
                if ($reader->nodeType === XMLReader::ELEMENT) {
                    switch ($reader->localName) {
                        case 'title':
                            if ($reader->namespaceURI === 'http://purl.org/dc/elements/1.1/') {
                                $info['title'] = htmlspecialchars($reader->readString(), ENT_QUOTES, 'UTF-8');
                            }
                            break;
                        case 'creator':
                            if ($reader->namespaceURI === 'http://purl.org/dc/elements/1.1/') {
                                $info['creator'] = htmlspecialchars($reader->readString(), ENT_QUOTES, 'UTF-8');
                            }
                            break;
                        case 'modified':
                            if ($reader->namespaceURI === 'http://purl.org/dc/terms/') {
                                $info['modified'] = htmlspecialchars($reader->readString(), ENT_QUOTES, 'UTF-8');
                            }
                            break;
                    }
                }
            }
            
        } finally {
            $reader->close();
        }
        
        return $info;
    }
    
    private function parseWithDOMDocument($xml_content) {
        $info = [];
        
        $dom = new DOMDocument();
        if (@$dom->loadXML($xml_content, LIBXML_NONET | LIBXML_NOENT)) {
            $xpath = new DOMXPath($dom);
            $xpath->registerNamespace('cp', 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties');
            $xpath->registerNamespace('dc', 'http://purl.org/dc/elements/1.1/');
            $xpath->registerNamespace('dcterms', 'http://purl.org/dc/terms/');
            
            // 安全提取信息
            $title_nodes = $xpath->query('//dc:title');
            if ($title_nodes->length > 0) {
                $info['title'] = htmlspecialchars($title_nodes->item(0)->nodeValue, ENT_QUOTES, 'UTF-8');
            }
            
            $creator_nodes = $xpath->query('//dc:creator');
            if ($creator_nodes->length > 0) {
                $info['creator'] = htmlspecialchars($creator_nodes->item(0)->nodeValue, ENT_QUOTES, 'UTF-8');
            }
            
            $modified_nodes = $xpath->query('//dcterms:modified');
            if ($modified_nodes->length > 0) {
                $info['modified'] = htmlspecialchars($modified_nodes->item(0)->nodeValue, ENT_QUOTES, 'UTF-8');
            }
        }
        
        return $info;
    }
}
```

**安全示例 - Office文档上传验证：**
```php
class OfficeDocumentUploadValidator {
    
    public function validateUpload($file) {
        // 1. MIME类型验证
        $allowed_types = [
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // docx
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',       // xlsx  
            'application/vnd.openxmlformats-officedocument.presentationml.presentation' // pptx
        ];
        
        $finfo = finfo_open(FILEINFO_MIME_TYPE);
        $mime_type = finfo_file($finfo, $file['tmp_name']);
        finfo_close($finfo);
        
        if (!in_array($mime_type, $allowed_types)) {
            throw new Exception('Invalid Office document MIME type');
        }
        
        // 2. ZIP结构验证
        $zip = new ZipArchive();
        if ($zip->open($file['tmp_name']) !== TRUE) {
            throw new Exception('Invalid ZIP format');
        }
        
        try {
            // 验证必需的ZIP条目
            $required_entries = ['[Content_Types].xml', '_rels/', 'docProps/'];
            foreach ($required_entries as $entry) {
                if ($zip->statName($entry) === false) {
                    throw new Exception("Missing required ZIP entry: $entry");
                }
            }
            
            // 3. 危险内容检测
            $this->checkForDangerousContent($zip);
            
            return true;
            
        } finally {
            $zip->close();
        }
    }
    
    private function checkForDangerousContent($zip) {
        // 检查常见的XXE攻击点
        $dangerous_patterns = [
            '<!DOCTYPE',  // DOCTYPE定义
            '<!ENTITY',   // 实体定义
            'SYSTEM',     // 系统实体
            'PUBLIC',     // 公共实体
            'file://',    // 文件协议
            'http://',    // HTTP协议（内部请求）
        ];
        
        // 检查核心XML文件
        $xml_files = [
            '[Content_Types].xml',
            '_rels/.rels',
            'docProps/core.xml',
            'docProps/app.xml'
        ];
        
        foreach ($xml_files as $xml_file) {
            $content = $zip->getFromName($xml_file);
            if ($content !== false) {
                foreach ($dangerous_patterns as $pattern) {
                    if (stripos($content, $pattern) !== false) {
                        throw new Exception("Potentially dangerous content detected: $pattern in $xml_file");
                    }
                }
            }
        }
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Office文档：`docx`, `xlsx`, `pptx`, `openxmlformats`
- ZIP处理：`ZipArchive`, `zip://`, `getFromName`
- XML解析：`loadXML`, `simplexml_load_string`, `DOMDocument`

**定位步骤：**
1. 搜索项目中所有Office文档处理逻辑
2. 检查ZIP文件处理后的XML解析步骤
3. 验证XML解析器的安全配置
4. 检查文件上传中的Office文档处理

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **实体加载禁用：** `libxml_disable_entity_loader(true)`
- **安全解析选项：** `LIBXML_NONET`, `XMLReader`使用
- **内容检查：** 危险模式（DOCTYPE/ENTITY）检测
- **替代方案：** 正则表达式提取而非XML解析

**定位技巧：**
- 检查是否优先使用正则表达式而非XML解析
- 确认是否禁用外部实体加载
- 验证是否进行内容级别的安全检查
- 检查是否使用XMLReader替代DOMDocument

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 正则提取+实体禁用 | **L0（快速跳过）** | 安全配置 |
| 有实体禁用但解析器不安全 | **L2（跳读）** | 需验证解析方式 |
| 使用DOMDocument无防护 | **L3（逐行读）** | 高风险配置 |
| 完全无Office安全检查 | **L4（跨模块追踪）** | 严重缺失 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 使用DOMDocument/SimpleXML解析Office文档XML且未禁用外部实体
2. 未对Office文档内容进行XXE安全检查
3. 允许用户上传或处理Office文档
4. XML解析步骤在处理流程中

#### 误报
以下情景可判定为误报：
1. 使用正则表达式提取基础信息而非XML解析
2. 使用XMLReader并禁用外部实体加载
3. 进行内容级别的XXE安全检查
4. 完全禁止Office文档处理

#### 代码异味
需记录的风险：
1. 仅在部分Office文档处理中实施安全检查
2. 动态生成的XML内容存在注入风险
3. 不同的Office格式处理安全级别不一致
4. 未验证Office文档来源的可靠性

## Low risk

### 低风险评级场景

#### 1. 正则表达式提取
- **场景：** 仅使用正则表达式提取基础元数据，不解析XML结构
- **风险评估：** 避免了XML解析风险，相对安全

#### 2. 专有库处理
- **场景：** 使用专门的Office文档处理库（如PhpSpreadsheet）
- **风险评估：** 专业库通常考虑了安全因素

#### 3. 只读元数据提取
- **场景：** 仅提取文档属性，不处理内容XML
- **风险评估：** 降低了攻击复杂性，风险可控

### Office文档XXE检查表

| 检查项 | 风险点 | 检测方法 | 防护建议 |
|--------|--------|----------|----------|
| XML解析器配置 | 外部实体启用 | 解析器设置检查 | 禁用外部实体 |
| 内容检查 | DOCTYPE/ENTITY | 危险模式检测 | 内容过滤 |
| 文件结构验证 | ZIP格式有效性 | 结构完整性检查 | 格式验证 |
| 网络访问限制 | 外部实体加载 | 网络权限检查 | 网络隔离 |

### Office文档类型风险分析

| 文档类型 | 主要风险点 | 攻击向量 | 防护重点 |
|----------|------------|----------|----------|
| DOCX | core.xml, document.xml | 文档属性XXE | 元数据处理 |
| XLSX | sharedStrings.xml | 共享字符串XXE | 字符串处理 |
| PPTX | slide*.xml | 幻灯片内容XXE | 内容解析 |

### 常见XXE注入点

| XML文件 | 作用 | XXE风险 | 检测要点 |
|----------|------|---------|----------|
| [Content_Types].xml | 内容类型定义 | 基础结构 | 格式验证 |
| .rels | 关系定义 | 重定向攻击 | 目标检查 |
| core.xml | 核心属性 | 元数据泄露 | 内容检查 |
| document.xml | 文档内容 | 内容注入 | 解析安全 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 正则表达式提取 | 避免XML解析 | 高 |
| 实体加载禁用 | 消除XXE基础 | 高 |
| 内容安全检查 | 多层防护 | 高 |
| 文件来源控制 | 降低攻击面 | 中 |
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""敏感信息扫描脚本。

使用 tree-sitter 提取敏感信息代码片段，识别硬编码敏感信息和泄露函数。
依据 `.claude/skills/sensitive-info-scanner/SKILL.md` 的分析维度：
1) 硬编码敏感信息（云服务凭据、数据库凭据、私钥、PII）
2) 泄露函数（环境变量导出、配置对象返回、敏感数据库查询）
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum

# Tree-sitter 支持（使用 tree-sitter-language-pack）
from tree_sitter import Parser, Language, Query, QueryCursor, Node  # type: ignore
from tree_sitter_language_pack import get_parser  # type: ignore


class SensitiveType(Enum):
    """敏感信息类型枚举"""
    AWS_KEY = "aws_key"
    GITHUB_TOKEN = "github_token"
    GOOGLE_API_KEY = "google_api_key"
    DATABASE_CREDENTIAL = "database_credential"
    PRIVATE_KEY = "private_key"
    JWT_SECRET = "jwt_secret"
    API_KEY = "api_key"
    PII_PHONE = "pii_phone"
    PII_EMAIL = "pii_email"
    PII_ID_CARD = "pii_id_card"
    ENV_EXPORT = "env_export"
    CONFIG_EXPORT = "config_export"
    SENSITIVE_QUERY = "sensitive_query"


class Priority(Enum):
    """优先级枚举"""
    P0_CRITICAL = "P0"
    P1_HIGH = "P1"
    P2_MEDIUM = "P2"
    P3_LOW = "P3"


@dataclass
class SensitiveInfo:
    """敏感信息"""
    type: SensitiveType  # 敏感信息类型
    file_path: str  # 文件路径
    line_number: int  # 行号
    column_number: int  # 列号
    code_snippet: str  # 代码片段
    context: Optional[str] = None  # 上下文信息
    priority: Priority = Priority.P2_MEDIUM  # 优先级
    is_hardcoded: bool = True  # 是否硬编码
    pattern_match: Optional[str] = None  # 匹配的模式


class TreeSitterParserManager:
    """Tree-sitter 解析器管理器，使用 tree-sitter-language-pack。"""
    
    def __init__(self):
        self.parsers: Dict[str, Parser] = {}
    
    def get_parser(self, language: str) -> Optional[Parser]:
        """获取指定语言的解析器。"""
        if language in self.parsers:
            return self.parsers[language]
        
        parser = get_parser(language)
        if parser:
            self.parsers[language] = parser
            return parser
        return None
    
    def get_language(self, language: str) -> Optional[Language]:
        """获取指定语言的 Language 对象。"""
        parser = self.get_parser(language)
        if parser:
            return parser.language
        return None
    
    def is_supported(self, language: str) -> bool:
        """检查语言是否支持。"""
        parser = self.get_parser(language)
        return parser is not None


# 语言映射常量
LANGUAGE_MAP = {
    "JavaScript/TypeScript": "javascript",
    "Python": "python",
    "Go": "go",
    "Java": "java",
    "PHP": "php",
    "Ruby": "ruby",
    "Rust": "rust",
    "C": "c",
    "C++": "cpp",
    ".NET": "csharp",
    "Swift": "swift",
    "Kotlin": "kotlin",
    "Scala": "scala",
    "Lua": "lua",
    "Bash": "bash",
    "YAML": "yaml",
    "JSON": "json",
    "HTML": "html",
    "CSS": "css",
}

# 测试文件后缀列表
TEST_FILE_SUFFIXES = [
    "_test.go", "_test.py", "_test.php", "_test.rs",
    ".test.js", ".test.ts", ".test.jsx", ".test.tsx",
    ".spec.js", ".spec.ts", ".spec.jsx", ".spec.tsx",
    "Test.java", "Tests.java",
    "_test.rb", "_spec.rb",
    ".test.cs", ".tests.cs",
]

# 敏感信息模式（正则表达式）
SENSITIVE_PATTERNS = {
    SensitiveType.AWS_KEY: re.compile(r'AKIA[0-9A-Z]{16}', re.IGNORECASE),
    SensitiveType.GITHUB_TOKEN: re.compile(r'gh[ps]_[0-9a-zA-Z]{36}', re.IGNORECASE),
    SensitiveType.GOOGLE_API_KEY: re.compile(r'AIza[0-9A-Za-z_-]{35}', re.IGNORECASE),
    SensitiveType.DATABASE_CREDENTIAL: re.compile(
        r'(mysql|postgresql|mongodb|redis)://[^:]+:[^@]+@',
        re.IGNORECASE
    ),
    SensitiveType.PRIVATE_KEY: re.compile(
        r'-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----',
        re.IGNORECASE
    ),
    SensitiveType.JWT_SECRET: re.compile(
        r'(jwt|jws|jwe)[_-]?secret["\']?\s*[:=]\s*["\']?[a-zA-Z0-9+/=]{20,}',
        re.IGNORECASE
    ),
    SensitiveType.API_KEY: re.compile(
        r'(api[_-]?key|apikey)["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{20,}["\']',
        re.IGNORECASE
    ),
    SensitiveType.PII_PHONE: re.compile(
        r'1[3-9]\d{9}',  # 中国手机号
    ),
    SensitiveType.PII_EMAIL: re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    ),
    SensitiveType.PII_ID_CARD: re.compile(
        r'[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]',  # 中国身份证号
    ),
}

# 误报过滤规则
FALSE_POSITIVE_PATTERNS = [
    re.compile(r'YOUR_.*_HERE', re.IGNORECASE),
    re.compile(r'<INSERT_.*>', re.IGNORECASE),
    re.compile(r'REPLACE_ME', re.IGNORECASE),
    re.compile(r'\bexample\b', re.IGNORECASE),
    re.compile(r'\btest\b', re.IGNORECASE),
    re.compile(r'\bdemo\b', re.IGNORECASE),
    re.compile(r'AKIAIOSFODNN7EXAMPLE', re.IGNORECASE),  # AWS 官方示例
]


def is_test_file(file_path: Path) -> bool:
    """检查是否为测试文件。"""
    name = file_path.name
    for suffix in TEST_FILE_SUFFIXES:
        if suffix in name:
            return True
    
    # 检查路径
    path_str = str(file_path)
    test_dirs = ['tests/', '__tests__/', 'spec/', 'fixtures/', 'examples/', 'docs/']
    for test_dir in test_dirs:
        if test_dir in path_str:
            return True
    
    return False


def is_false_positive(text: str) -> bool:
    """检查是否为误报。"""
    for pattern in FALSE_POSITIVE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def detect_language(root: Path) -> Optional[str]:
    """检测项目主要语言。"""
    # 检查常见配置文件
    config_files = {
        'package.json': 'JavaScript/TypeScript',
        'requirements.txt': 'Python',
        'go.mod': 'Go',
        'pom.xml': 'Java',
        'build.gradle': 'Java',
        'composer.json': 'PHP',
        'Gemfile': 'Ruby',
        'Cargo.toml': 'Rust',
        '*.csproj': '.NET',
    }
    
    for config_file, language in config_files.items():
        if config_file.startswith('*'):
            # 使用 glob 匹配
            pattern = config_file[1:]
            if list(root.glob(f'**/{pattern}')):
                return language
        else:
            if (root / config_file).exists():
                return language
    
    # 统计代码文件数量
    code_files = {
        'JavaScript/TypeScript': list(root.glob('**/*.{js,ts,jsx,tsx}')),
        'Python': list(root.glob('**/*.py')),
        'Go': list(root.glob('**/*.go')),
        'Java': list(root.glob('**/*.java')),
        'PHP': list(root.glob('**/*.php')),
    }
    
    # 返回文件数量最多的语言
    if code_files:
        max_lang = max(code_files.items(), key=lambda x: len(x[1]))
        if len(max_lang[1]) > 0:
            return max_lang[0]
    
    return None


def extract_string_literal(node: Node, source_code: bytes) -> Optional[str]:
    """从 AST 节点提取字符串字面量。"""
    try:
        text = source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
        # 去除引号
        if text.startswith('"') and text.endswith('"'):
            return text[1:-1]
        elif text.startswith("'") and text.endswith("'"):
            return text[1:-1]
        elif text.startswith('`') and text.endswith('`'):
            return text[1:-1]
        return text
    except Exception:
        return None


def scan_hardcoded_secrets(
    root: Path,
    parser_manager: TreeSitterParserManager,
    code_extensions: Tuple[str, ...]
) -> List[SensitiveInfo]:
    """扫描硬编码敏感信息。"""
    findings: List[SensitiveInfo] = []
    
    for ext in code_extensions:
        for file_path in root.rglob(f"*{ext}"):
            if not file_path.is_file() or is_test_file(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 使用正则表达式扫描
                for sensitive_type, pattern in SENSITIVE_PATTERNS.items():
                    for match in pattern.finditer(content):
                        matched_text = match.group(0)
                        
                        # 对于 API_KEY，检查是否是环境变量名称（误报过滤）
                        if sensitive_type == SensitiveType.API_KEY:
                            # 从匹配文本中提取引号内的值
                            import re as re_module
                            value_match = re_module.search(r'["\']([^"\']+)["\']', matched_text)
                            if value_match:
                                api_key_value = value_match.group(1)
                                # 检查是否是环境变量名称（全大写+下划线，且包含常见前缀）
                                if api_key_value.isupper() and '_' in api_key_value:
                                    # 检查是否包含常见环境变量前缀
                                    env_prefixes = ['ENV_', '_ENV', 'MINIO_', 'KMS_', 'KES_', 'AWS_', 'GCP_', 'AZURE_', 'SUBNET_']
                                    if any(api_key_value.startswith(prefix) or prefix in api_key_value for prefix in env_prefixes):
                                        continue
                        
                        # 检查是否为误报
                        if is_false_positive(matched_text):
                            continue
                        
                        # 检查是否在注释中（简单检查：行首有 // 或 #）
                        match_start = match.start()
                        line_start = content[:match_start].rfind('\n') + 1
                        line_prefix = content[line_start:match_start].strip()
                        if line_prefix.startswith('//') or line_prefix.startswith('#'):
                            continue
                        
                        # 对于 PII 类型，检查是否在哈希值中（避免误报）
                        if sensitive_type in (SensitiveType.PII_PHONE, SensitiveType.PII_ID_CARD):
                            # 检查匹配内容前后是否有更多数字/字母（可能是哈希值的一部分）
                            context_before = content[max(0, match_start - 10):match_start]
                            context_after = content[match.end():min(len(content), match.end() + 10)]
                            # 如果前后都是十六进制字符，可能是哈希值
                            hex_chars = set('0123456789abcdefABCDEF')
                            if (all(c in hex_chars or c.isspace() for c in context_before) and
                                all(c in hex_chars or c.isspace() for c in context_after)):
                                # 检查整个匹配内容是否看起来像哈希值的一部分
                                if len(matched_text) > 10 and all(c in hex_chars for c in matched_text):
                                    continue
                        
                        # 计算行号和列号
                        line_start = content[:match.start()].count('\n')
                        line_content = content.split('\n')[line_start] if line_start < len(content.split('\n')) else ''
                        column = match.start() - content[:match.start()].rfind('\n') - 1
                        
                        # 提取上下文（前后各 2 行）
                        lines = content.split('\n')
                        context_lines = []
                        for i in range(max(0, line_start - 2), min(len(lines), line_start + 3)):
                            if i == line_start:
                                context_lines.append(f"> {lines[i]}")
                            else:
                                context_lines.append(f"  {lines[i]}")
                        context = '\n'.join(context_lines)
                        
                        # 确定优先级
                        priority = Priority.P2_MEDIUM
                        if sensitive_type in (SensitiveType.PRIVATE_KEY, SensitiveType.DATABASE_CREDENTIAL,
                                            SensitiveType.AWS_KEY, SensitiveType.GITHUB_TOKEN):
                            priority = Priority.P0_CRITICAL
                        elif sensitive_type in (SensitiveType.JWT_SECRET, SensitiveType.API_KEY, SensitiveType.GOOGLE_API_KEY):
                            priority = Priority.P1_HIGH
                        
                        finding = SensitiveInfo(
                            type=sensitive_type,
                            file_path=str(file_path),
                            line_number=line_start + 1,
                            column_number=column + 1,
                            code_snippet=line_content.strip(),
                            context=context,
                            priority=priority,
                            is_hardcoded=True,
                            pattern_match=matched_text
                        )
                        findings.append(finding)
            
            except Exception:
                continue
    
    return findings


def get_leak_queries(language: str, lang_obj: Language) -> List[Query]:
    """获取泄露函数的 tree-sitter 查询。"""
    queries = []
    
    if language == "python":
        # os.environ 整体导出
        env_query = Query(lang_obj, """
            (call_expression
                function: (attribute
                    object: (identifier) @obj
                    attr: (identifier) @attr)
                (#match? @obj "^os$")
                (#match? @attr "^(environ|getenv)$")
            ) @env_call
        """)
        queries.append(env_query)
        
        # 配置对象返回
        config_query = Query(lang_obj, """
            (return_statement
                (attribute
                    object: (identifier) @obj
                    attr: (identifier) @attr)
                (#match? @attr "^(config|settings|CONFIG|SETTINGS)$")
            ) @config_return
        """)
        queries.append(config_query)
    
    elif language == "javascript":
        # process.env 整体导出
        env_query = Query(lang_obj, """
            (member_expression
                object: (identifier) @obj
                property: (property_identifier) @prop
                (#match? @obj "^process$")
                (#match? @prop "^env$")
            ) @process_env
        """)
        queries.append(env_query)
        
        # 配置对象返回
        config_query = Query(lang_obj, """
            (return_statement
                (member_expression
                    object: (identifier) @obj
                    property: (property_identifier) @prop)
                (#match? @prop "^(config|settings|CONFIG|SETTINGS)$")
            ) @config_return
        """)
        queries.append(config_query)
    
    elif language == "go":
        # os.Getenv / os.Environ / os.LookupEnv
        os_env_query = Query(lang_obj, """
            (call_expression
                function: (selector_expression
                    operand: (identifier) @obj
                    field: (field_identifier) @field)
                (#match? @obj "^os$")
                (#match? @field "^(Getenv|Environ|LookupEnv)$")
            ) @env_call
        """)
        queries.append(os_env_query)
        
        # env 库：env.List() / env.Get() / env.Parse()
        env_lib_query = Query(lang_obj, """
            (call_expression
                function: (selector_expression
                    operand: (identifier) @obj
                    field: (field_identifier) @field)
                (#match? @obj "^env$")
                (#match? @field "^(List|Get|Parse)$")
            ) @env_lib_call
        """)
        queries.append(env_lib_query)
    
    elif language == "java":
        # System.getenv()
        env_query = Query(lang_obj, """
            (method_invocation
                object: (identifier) @obj
                name: (identifier) @method
                (#match? @obj "^System$")
                (#match? @method "^(getenv|getProperty)$")
            ) @system_env
        """)
        queries.append(env_query)
    
    return queries


def scan_leak_functions(
    root: Path,
    language: str,
    parser_manager: TreeSitterParserManager,
    code_extensions: Tuple[str, ...]
) -> List[SensitiveInfo]:
    """扫描泄露函数。"""
    findings: List[SensitiveInfo] = []
    ts_lang = LANGUAGE_MAP.get(language)
    
    if not ts_lang or not parser_manager.is_supported(ts_lang):
        return findings
    
    parser = parser_manager.get_parser(ts_lang)
    if not parser:
        return findings
    
    lang_obj = parser_manager.get_language(ts_lang)
    if not lang_obj:
        return findings
    
    queries = get_leak_queries(ts_lang, lang_obj)
    
    for ext in code_extensions:
        for file_path in root.rglob(f"*{ext}"):
            if not file_path.is_file() or is_test_file(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                tree = parser.parse(content.encode('utf-8'))
                source_code = content.encode('utf-8')
                
                for query in queries:
                    try:
                        cursor = QueryCursor(query)
                        matches = cursor.matches(tree.root_node)
                        
                        for pattern_index, captures_dict in matches:
                            # 获取匹配的节点（captures_dict 的值是节点列表）
                            for capture_name, nodes in captures_dict.items():
                                if capture_name not in ("env_call", "env_lib_call", "process_env", "system_env", "config_return"):
                                    continue
                                
                                # 遍历该捕获名称对应的所有节点
                                if not isinstance(nodes, list):
                                    nodes = [nodes]
                                
                                for node in nodes:
                                    if not hasattr(node, 'start_point'):
                                        continue
                                    
                                    line_number = node.start_point[0] + 1
                                    column_number = node.start_point[1] + 1
                                    
                                    # 提取代码片段
                                    code_snippet = source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                                    
                                    # 对于 env 库，检查是否是 List() 方法（会返回所有环境变量）
                                    is_env_list = False
                                    if capture_name == "env_lib_call":
                                        # 检查是否是 env.List() 调用
                                        if "env.List" in code_snippet or "List" in code_snippet:
                                            # 进一步确认：检查 field 捕获
                                            if "field" in captures_dict:
                                                field_nodes = captures_dict["field"]
                                                if isinstance(field_nodes, list) and len(field_nodes) > 0:
                                                    field_text = source_code[field_nodes[0].start_byte:field_nodes[0].end_byte].decode('utf-8', errors='ignore')
                                                    if field_text == "List":
                                                        is_env_list = True
                                    
                                    # 提取上下文
                                    lines = content.split('\n')
                                    context_lines = []
                                    for i in range(max(0, line_number - 3), min(len(lines), line_number + 2)):
                                        if i == line_number - 1:
                                            context_lines.append(f"> {lines[i]}")
                                        else:
                                            context_lines.append(f"  {lines[i]}")
                                    context = '\n'.join(context_lines)
                                    
                                    # 确定类型和优先级
                                    if capture_name in ("env_call", "process_env", "system_env"):
                                        # os.Environ() 会返回所有环境变量
                                        if "Environ" in code_snippet:
                                            sensitive_type = SensitiveType.ENV_EXPORT
                                            priority = Priority.P0_CRITICAL
                                        else:
                                            # 单个环境变量获取，风险较低
                                            sensitive_type = SensitiveType.ENV_EXPORT
                                            priority = Priority.P2_MEDIUM
                                    elif capture_name == "env_lib_call":
                                        if is_env_list:
                                            sensitive_type = SensitiveType.ENV_EXPORT
                                            priority = Priority.P0_CRITICAL
                                        else:
                                            # env.Get() 或 env.Parse() 单个变量，风险较低
                                            sensitive_type = SensitiveType.ENV_EXPORT
                                            priority = Priority.P2_MEDIUM
                                    else:
                                        sensitive_type = SensitiveType.CONFIG_EXPORT
                                        priority = Priority.P1_HIGH
                                    
                                    finding = SensitiveInfo(
                                        type=sensitive_type,
                                        file_path=str(file_path),
                                        line_number=line_number,
                                        column_number=column_number,
                                        code_snippet=code_snippet.strip(),
                                        context=context,
                                        priority=priority,
                                        is_hardcoded=False
                                    )
                                    findings.append(finding)
                    
                    except Exception:
                        continue
            
            except Exception:
                continue
    
    return findings


def format_findings_output(findings: List[SensitiveInfo]) -> str:
    """格式化敏感信息输出为 Markdown。"""
    output = []
    output.append("# 敏感信息扫描结果\n")
    output.append(f"## 概述\n")
    output.append(f"- **总发现数**: {len(findings)}\n")
    
    # 按类型统计
    type_counts = {}
    priority_counts = {}
    for finding in findings:
        type_counts[finding.type.value] = type_counts.get(finding.type.value, 0) + 1
        priority_counts[finding.priority.value] = priority_counts.get(finding.priority.value, 0) + 1
    
    output.append(f"- **P0 Critical**: {priority_counts.get('P0', 0)}\n")
    output.append(f"- **P1 High**: {priority_counts.get('P1', 0)}\n")
    output.append(f"- **P2 Medium**: {priority_counts.get('P2', 0)}\n")
    output.append(f"- **P3 Low**: {priority_counts.get('P3', 0)}\n")
    output.append("\n## 发现列表\n\n")
    
    # 按优先级分组
    findings_by_priority = {}
    for finding in findings:
        priority = finding.priority.value
        if priority not in findings_by_priority:
            findings_by_priority[priority] = []
        findings_by_priority[priority].append(finding)
    
    for priority in ['P0', 'P1', 'P2', 'P3']:
        if priority not in findings_by_priority:
            continue
        
        output.append(f"### {priority} 级别发现\n\n")
        
        for finding in findings_by_priority[priority]:
            output.append(f"#### {finding.type.value}\n")
            output.append(f"- **文件**: {finding.file_path}:{finding.line_number}:{finding.column_number}\n")
            output.append(f"- **类型**: {'硬编码' if finding.is_hardcoded else '泄露函数'}\n")
            if finding.pattern_match:
                output.append(f"- **匹配内容**: `{finding.pattern_match[:50]}...`\n")
            output.append(f"- **代码片段**:\n")
            output.append(f"```\n{finding.code_snippet}\n```\n")
            if finding.context:
                output.append(f"- **上下文**:\n")
                output.append(f"```\n{finding.context}\n```\n")
            output.append("\n")
    
    return "".join(output)


def main():
    parser = argparse.ArgumentParser(description="敏感信息扫描脚本（使用 tree-sitter）")
    parser.add_argument("source_dir", type=str, help="项目源码目录路径")
    parser.add_argument(
        "--output",
        type=str,
        help="输出文件路径（Markdown 格式）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试输出",
    )
    args = parser.parse_args()
    
    root = Path(args.source_dir).resolve()
    if not root.exists():
        print(f"错误：目录不存在: {root}")
        return
    
    language = detect_language(root)
    if not language:
        print("警告: 无法检测项目语言")
        return
    
    # 根据语言确定代码文件扩展名
    code_extensions_map = {
        "JavaScript/TypeScript": (".js", ".ts", ".jsx", ".tsx"),
        "Python": (".py",),
        "Go": (".go",),
        "Java": (".java",),
        "PHP": (".php",),
        "Ruby": (".rb",),
        "Rust": (".rs",),
        "C": (".c", ".h"),
        "C++": (".cpp", ".cc", ".cxx", ".hpp"),
        ".NET": (".cs",),
    }
    
    code_extensions = code_extensions_map.get(language, (".js", ".py", ".go", ".java"))
    
    parser_manager = TreeSitterParserManager()
    
    print(f"项目路径: {root}")
    print(f"检测到语言: {language}")
    print(f"搜索代码文件: {', '.join(code_extensions)}")
    print("=" * 80)
    
    # 扫描硬编码敏感信息
    print("扫描硬编码敏感信息...")
    hardcoded_findings = scan_hardcoded_secrets(root, parser_manager, code_extensions)
    print(f"找到 {len(hardcoded_findings)} 个硬编码敏感信息")
    
    # 扫描泄露函数
    print("扫描泄露函数...")
    leak_findings = scan_leak_functions(root, language, parser_manager, code_extensions)
    print(f"找到 {len(leak_findings)} 个泄露函数")
    
    # 合并结果
    all_findings = hardcoded_findings + leak_findings
    
    print(f"\n总共找到 {len(all_findings)} 个敏感信息发现")
    
    # 输出结果
    if args.json:
        findings_dict = [asdict(f) for f in all_findings]
        # 转换枚举为字符串
        for f in findings_dict:
            f['type'] = f['type'].value if isinstance(f['type'], SensitiveType) else f['type']
            f['priority'] = f['priority'].value if isinstance(f['priority'], Priority) else f['priority']
        output = json.dumps(findings_dict, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
        else:
            print(output)
    else:
        output = format_findings_output(all_findings)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
        else:
            print(output)
    
    print("=" * 80)
    print("扫描完成")


if __name__ == "__main__":
    main()


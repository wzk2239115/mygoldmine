#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路由扫描脚本。

使用 tree-sitter 提取路由注册信息，识别项目中的 API 端点。
依据 `.claude/skills/unauth-route-scanner/SKILL.md` 的分析维度：
1) 路由识别（支持主流框架：Express、Flask、Spring、Gin 等）
2) 条件注册路由识别
3) 路由风险分级
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum

# Tree-sitter 支持（使用 tree-sitter-language-pack）
from tree_sitter import Parser, Language, Query, QueryCursor, Node  # type: ignore
from tree_sitter_language_pack import get_parser  # type: ignore


@dataclass
class RouteInfo:
    """路由信息"""
    method: str  # HTTP 方法
    path: str  # 路由路径
    file_path: str  # 文件路径
    line_number: int  # 行号
    handler_name: Optional[str] = None  # Handler 函数名
    handler_file: Optional[str] = None  # Handler 定义文件
    handler_line: Optional[int] = None  # Handler 定义行号
    is_conditional: bool = False  # 是否条件注册
    condition: Optional[str] = None  # 条件表达式
    middleware: List[str] = None  # 中间件列表
    risk_level: Optional[str] = None  # 风险等级
    
    def __post_init__(self):
        if self.middleware is None:
            self.middleware = []


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
    "Test.java", "Tests.java",
    "_spec.rb", "_test.rb",
    ".spec.js", ".spec.ts",
    "_test.scala",
]


def detect_language(root: Path) -> Optional[str]:
    """检测项目主要语言。"""
    dep_files = {
        "package.json": "JavaScript/TypeScript",
        "tsconfig.json": "JavaScript/TypeScript",
        "go.mod": "Go",
        "pom.xml": "Java",
        "build.gradle": "Java",
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "composer.json": "PHP",
        "Cargo.toml": "Rust",
        "Gemfile": "Ruby",
        "build.sbt": "Scala",
    }
    
    for dep_file, lang in dep_files.items():
        if (root / dep_file).exists():
            return lang
    
    if list(root.glob("*.csproj")) or list(root.glob("*.sln")):
        return ".NET"
    
    if list(root.glob("CMakeLists.txt")) or list(root.glob("Makefile")):
        if list(root.glob("*.cpp")) or list(root.glob("*.hpp")):
            return "C++"
        return "C"
    
    return None


def get_code_extensions(language: Optional[str]) -> Tuple[str, ...]:
    """根据语言返回代码文件扩展名。"""
    ext_map = {
        "JavaScript/TypeScript": (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"),
        "Python": (".py", ".pyw", ".pyi"),
        "Java": (".java",),
        "Go": (".go",),
        "PHP": (".php", ".phtml", ".php3", ".php4", ".php5"),
        ".NET": (".cs", ".vb", ".fs"),
        "Rust": (".rs",),
        "Ruby": (".rb", ".rake", ".ru"),
        "Scala": (".scala", ".sc"),
        "C": (".c", ".h"),
        "C++": (".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh", ".h"),
        "Swift": (".swift",),
        "Kotlin": (".kt", ".kts"),
        "Lua": (".lua",),
        "Bash": (".sh", ".bash", ".zsh"),
    }
    return ext_map.get(language, (".js", ".ts", ".py", ".java", ".go", ".php", ".cs"))


def is_test_file(file_path: Path) -> bool:
    """检查是否为测试文件。"""
    return any(test_suffix in str(file_path) for test_suffix in TEST_FILE_SUFFIXES)


def extract_string_literal(node: Node, source_code: bytes) -> Optional[str]:
    """从 AST 节点提取字符串字面量。"""
    if node.type in ("string", "string_literal", "raw_string_literal"):
        text = source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
        # 移除引号
        text = text.strip('"\'`')
        return text
    return None


def extract_route_from_node(
    node: Node,
    source_code: bytes,
    file_path: Path,
    language: str,
    parser_manager: TreeSitterParserManager
) -> Optional[RouteInfo]:
    """从 AST 节点提取路由信息（框架特定实现）。"""
    ts_lang = LANGUAGE_MAP.get(language)
    if not ts_lang:
        return None
    
    # 根据语言类型调用不同的提取函数
    if ts_lang == "javascript":
        return extract_route_javascript(node, source_code, file_path)
    elif ts_lang == "python":
        return extract_route_python(node, source_code, file_path)
    elif ts_lang == "go":
        return extract_route_go(node, source_code, file_path)
    elif ts_lang == "java":
        return extract_route_java(node, source_code, file_path)
    
    return None


def extract_route_javascript(
    node: Node,
    source_code: bytes,
    file_path: Path
) -> Optional[RouteInfo]:
    """提取 JavaScript/TypeScript 路由（Express/Koa/NestJS）。"""
    # Express: app.get('/path', handler) 或 router.get('/path', handler)
    # NestJS: @Get('/path') 装饰器
    # 这里需要实现具体的 AST 节点解析逻辑
    # 暂时返回 None，后续实现
    return None


def extract_route_python(
    node: Node,
    source_code: bytes,
    file_path: Path
) -> Optional[RouteInfo]:
    """提取 Python 路由（Flask/FastAPI/Django）。"""
    # Flask: @app.route('/path', methods=['GET'])
    # FastAPI: @router.get('/path')
    # Django: path('path', view)
    # 这里需要实现具体的 AST 节点解析逻辑
    # 暂时返回 None，后续实现
    return None


def extract_route_go(
    node: Node,
    source_code: bytes,
    file_path: Path
) -> Optional[RouteInfo]:
    """提取 Go 路由（Gin/Echo/Chi/gorilla-mux/net/http）。"""
    try:
        # 获取节点文本用于调试
        node_text = source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
        # 处理链式调用：router.Methods(...).Path(...).HandlerFunc(...)
        # 或：router.Methods(...).HandlerFunc(...)
        
        method = None
        path = None
        handler_name = None
        
        # 遍历节点查找 Methods、Path、HandlerFunc 调用
        def find_chain_calls(n: Node):
            nonlocal method, path, handler_name
            
            if n.type == "call_expression":
                func_node = n.child_by_field_name("function")
                if func_node:
                    # 检查是否是链式调用
                    if func_node.type == "selector_expression":
                        field = func_node.child_by_field_name("field")
                        if field:
                            field_name = source_code[field.start_byte:field.end_byte].decode('utf-8', errors='ignore')
                            
                            # 提取 Methods
                            if field_name == "Methods":
                                args = n.child_by_field_name("arguments")
                                if args and args.child_count > 0:
                                    # 提取第一个参数（通常是 http.MethodGet 等）
                                    first_arg = args.child(0)
                                    if first_arg:
                                        method_text = source_code[first_arg.start_byte:first_arg.end_byte].decode('utf-8', errors='ignore')
                                        # 提取方法名（如 http.MethodGet -> GET）
                                        if "MethodGet" in method_text:
                                            method = "GET"
                                        elif "MethodPost" in method_text:
                                            method = "POST"
                                        elif "MethodPut" in method_text:
                                            method = "PUT"
                                        elif "MethodDelete" in method_text:
                                            method = "DELETE"
                                        elif "MethodHead" in method_text:
                                            method = "HEAD"
                                        elif "MethodOptions" in method_text:
                                            method = "OPTIONS"
                                        elif "MethodPatch" in method_text:
                                            method = "PATCH"
                            
                            # 提取 Path
                            elif field_name == "Path":
                                args = n.child_by_field_name("arguments")
                                if args and args.child_count > 0:
                                    path_node = args.child(0)
                                    if path_node:
                                        path = extract_string_literal(path_node, source_code)
                            
                            # 提取 HandlerFunc
                            elif field_name == "HandlerFunc":
                                args = n.child_by_field_name("arguments")
                                if args and args.child_count > 0:
                                    handler_node = args.child(0)
                                    if handler_node:
                                        # 提取函数名（可能是函数调用或标识符）
                                        handler_text = source_code[handler_node.start_byte:handler_node.end_byte].decode('utf-8', errors='ignore')
                                        # 尝试提取函数名（去除可能的包装函数调用）
                                        if handler_node.type == "identifier":
                                            handler_name = handler_text
                                        elif handler_node.type == "call_expression":
                                            # 处理包装函数调用，如 gz(httpTraceAll(api.PutBucketHandler))
                                            # 尝试提取最内层的函数名
                                            func_call = handler_node
                                            while func_call and func_call.type == "call_expression":
                                                args = func_call.child_by_field_name("arguments")
                                                if args and args.child_count > 0:
                                                    inner = args.child(0)
                                                    if inner.type == "identifier":
                                                        handler_name = source_code[inner.start_byte:inner.end_byte].decode('utf-8', errors='ignore')
                                                        break
                                                    elif inner.type == "selector_expression":
                                                        # 处理 api.PutBucketHandler 这种形式
                                                        field = inner.child_by_field_name("field")
                                                        if field:
                                                            handler_name = source_code[field.start_byte:field.end_byte].decode('utf-8', errors='ignore')
                                                        break
                                                    elif inner.type == "call_expression":
                                                        func_call = inner
                                                    else:
                                                        break
                                                else:
                                                    break
            
            # 递归遍历子节点
            for child in n.children:
                find_chain_calls(child)
        
        find_chain_calls(node)
        
        # 如果找到了方法和处理器，创建路由信息
        if method and handler_name:
            # 如果 path 为空，尝试从节点文本中提取
            if not path:
                # 查找 Path 调用
                node_text = source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                # 尝试从文本中提取路径（简单模式匹配）
                import re
                path_match = re.search(r'\.Path\(["\']([^"\']+)["\']', node_text)
                if path_match:
                    path = path_match.group(1)
            
            line_number = node.start_point[0] + 1
            
            route = RouteInfo(
                method=method,
                path=path or "/",  # 如果没有 Path，使用默认路径
                file_path=str(file_path),
                line_number=line_number,
                handler_name=handler_name
            )
            
            return route
        
        # 备用方法：直接从节点文本中提取（正则表达式）
        import re
        node_text = source_code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
        
        # 匹配 gorilla/mux 模式：router.Methods(http.MethodGet).Path("/path").HandlerFunc(...)
        # 改进：支持更灵活的路径匹配（包括变量和表达式）
        mux_pattern = r'\.Methods\([^)]*http\.Method(\w+)[^)]*\)(?:\.Path\(([^)]+)\))?.*?\.HandlerFunc\([^)]*?([a-zA-Z_][a-zA-Z0-9_]*Handler)'
        mux_match = re.search(mux_pattern, node_text, re.DOTALL)
        if mux_match:
            method_name = mux_match.group(1)
            path_value = mux_match.group(2) if mux_match.group(2) else None
            handler_name_value = mux_match.group(3)
            
            # 清理路径值（去除引号，处理变量）
            if path_value:
                path_value = path_value.strip().strip('"\'')
                # 如果路径包含变量或表达式，标记为动态路径
                if '+' in path_value or '{' in path_value or ':' in path_value:
                    path_value = path_value  # 保留原始值
                elif not path_value:
                    path_value = "/"
            else:
                path_value = "/"
            
            if method_name and handler_name_value:
                return RouteInfo(
                    method=method_name,
                    path=path_value,
                    file_path=str(file_path),
                    line_number=node.start_point[0] + 1,
                    handler_name=handler_name_value
                )
        
        # 处理 Gin/Echo 风格：r.GET("/path", handler)
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node and func_node.type == "selector_expression":
                field = func_node.child_by_field_name("field")
                if field:
                    method_name = source_code[field.start_byte:field.end_byte].decode('utf-8', errors='ignore')
                    if method_name in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "Any"):
                        args = node.child_by_field_name("arguments")
                        if args and args.child_count >= 2:
                            path_node = args.child(0)
                            handler_node = args.child(1)
                            
                            path = extract_string_literal(path_node, source_code)
                            if handler_node and handler_node.type == "identifier":
                                handler_name = source_code[handler_node.start_byte:handler_node.end_byte].decode('utf-8', errors='ignore')
                            
                            if path and handler_name:
                                return RouteInfo(
                                    method=method_name,
                                    path=path,
                                    file_path=str(file_path),
                                    line_number=node.start_point[0] + 1,
                                    handler_name=handler_name
                                )
    
    except Exception:
        pass
    
    return None


def extract_route_java(
    node: Node,
    source_code: bytes,
    file_path: Path
) -> Optional[RouteInfo]:
    """提取 Java 路由（Spring Boot）。"""
    # Spring: @GetMapping("/path") 或 @RequestMapping(value = "/path", method = RequestMethod.GET)
    # 这里需要实现具体的 AST 节点解析逻辑
    # 暂时返回 None，后续实现
    return None




def scan_routes_with_treesitter(
    root: Path,
    language: str,
    parser_manager: TreeSitterParserManager,
    code_extensions: Tuple[str, ...],
    debug: bool = False
) -> List[RouteInfo]:
    """使用 tree-sitter 扫描路由注册信息。"""
    routes: List[RouteInfo] = []
    ts_lang = LANGUAGE_MAP.get(language)
    
    if not ts_lang or not parser_manager.is_supported(ts_lang):
        return routes
    
    parser = parser_manager.get_parser(ts_lang)
    if not parser:
        return routes
    
    lang_obj = parser_manager.get_language(ts_lang)
    if not lang_obj:
        return routes
    
    # 定义框架特定的 tree-sitter 查询
    queries = get_route_queries(ts_lang, lang_obj)
    
    for ext in code_extensions:
        for file_path in root.rglob(f"*{ext}"):
            if not file_path.is_file() or is_test_file(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                tree = parser.parse(content.encode('utf-8'))
                source_code = content.encode('utf-8')
                
                # 使用查询提取路由
                for query in queries:
                    try:
                        cursor = QueryCursor(query)
                        matches = cursor.matches(tree.root_node)
                        
                        # 收集所有匹配的节点（避免重复处理）
                        processed_nodes = set()
                        processed_routes = set()  # 用于去重路由
                        
                        for pattern_index, captures_dict in matches:
                            # 获取 chain_call 节点（链式调用的完整节点）
                            if "chain_call" in captures_dict:
                                for node in captures_dict["chain_call"]:
                                    node_id = (node.start_byte, node.end_byte)
                                    if node_id in processed_nodes:
                                        continue
                                    processed_nodes.add(node_id)
                                    
                                    # 对于链式调用，需要找到完整的调用链
                                    # 从当前节点向上查找父节点，找到包含 Methods、Path、HandlerFunc 的完整链
                                    parent_node = node
                                    max_depth = 10
                                    depth = 0
                                    
                                    # 向上查找包含完整链式调用的父节点
                                    # 查找包含 Methods 和 HandlerFunc 的 call_expression 节点
                                    while parent_node.parent and depth < max_depth:
                                        parent_node = parent_node.parent
                                        depth += 1
                                        
                                        # 只检查 call_expression 类型的节点
                                        if parent_node.type == "call_expression":
                                            parent_text = source_code[parent_node.start_byte:parent_node.end_byte].decode('utf-8', errors='ignore')
                                            # 检查是否包含 Methods 和 HandlerFunc（链式调用的特征）
                                            if "Methods" in parent_text and "HandlerFunc" in parent_text:
                                                # 进一步验证：检查是否是链式调用结构
                                                # 链式调用应该有多个 call_expression 嵌套
                                                if parent_text.count("Methods") > 0 and parent_text.count("HandlerFunc") > 0:
                                                    route = extract_route_from_node(parent_node, source_code, file_path, language, parser_manager)
                                                    if route:
                                                        # 去重：使用 (file_path, line_number, method, handler_name) 作为唯一标识
                                                        route_key = (str(file_path), route.line_number, route.method, route.handler_name)
                                                        if route_key not in processed_routes:
                                                            processed_routes.add(route_key)
                                                            routes.append(route)
                                                        break
                                    
                                    # 如果向上查找失败，直接尝试从当前节点提取
                                    route_key = (str(file_path), node.start_point[0] + 1, None, None)
                                    if not any(r.file_path == str(file_path) and r.line_number == node.start_point[0] + 1 for r in routes):
                                        route = extract_route_from_node(node, source_code, file_path, language, parser_manager)
                                        if route:
                                            # 去重
                                            route_key = (str(file_path), route.line_number, route.method, route.handler_name)
                                            if route_key not in processed_routes:
                                                processed_routes.add(route_key)
                                                routes.append(route)
                            
                            # 处理其他类型的路由（route_call, http_route）
                            for capture_name in ("route_call", "http_route"):
                                if capture_name in captures_dict:
                                    for node in captures_dict[capture_name]:
                                        node_id = (node.start_byte, node.end_byte)
                                        if node_id in processed_nodes:
                                            continue
                                        processed_nodes.add(node_id)
                                        
                                        route = extract_route_from_node(node, source_code, file_path, language, parser_manager)
                                        if route:
                                            # 去重
                                            route_key = (str(file_path), route.line_number, route.method, route.handler_name)
                                            if route_key not in processed_routes:
                                                processed_routes.add(route_key)
                                                routes.append(route)
                    except Exception as e:
                        # 查询失败，继续下一个查询
                        continue
                
            except Exception:
                continue
    
    return routes


def get_route_queries(language: str, lang_obj: Language) -> List[Query]:
    """获取框架特定的 tree-sitter 查询。"""
    queries = []
    
    if language == "javascript":
        # Express: app.get('/path', handler)
        express_query = Query(lang_obj, """
            (call_expression
                function: (member_expression
                    object: (identifier) @router
                    property: (property_identifier) @method)
                arguments: (arguments
                    (string) @path
                    (_) @handler)
                (#match? @method "^(get|post|put|patch|delete|options|head|all|use)$")
            ) @route_call
        """)
        queries.append(express_query)
        
        # NestJS: @Get('/path')
        nestjs_query = Query(lang_obj, """
            (decorator
                call_expression: (call_expression
                    function: (identifier) @decorator
                    arguments: (arguments
                        (string) @path))
                (#match? @decorator "^(Get|Post|Put|Patch|Delete|Options|Head|All)$")
            ) @route_decorator
        """)
        queries.append(nestjs_query)
    
    elif language == "python":
        # Flask: @app.route('/path', methods=['GET'])
        flask_query = Query(lang_obj, """
            (decorator
                call: (call
                    function: (attribute
                        object: (identifier) @app
                        attr: (identifier) @route_method)
                    arguments: (argument_list
                        (string) @path
                        (_)*)
                )
                (#match? @route_method "^(route|get|post|put|patch|delete)$")
            ) @route_decorator
        """)
        queries.append(flask_query)
        
        # FastAPI: @router.get('/path')
        fastapi_query = Query(lang_obj, """
            (decorator
                call: (call
                    function: (attribute
                        object: (identifier) @router
                        attr: (identifier) @method)
                    arguments: (argument_list
                        (string) @path)
                )
                (#match? @method "^(get|post|put|patch|delete|options|head)$")
            ) @route_decorator
        """)
        queries.append(fastapi_query)
    
    elif language == "go":
        # gorilla/mux: router.Methods(...).Path(...).HandlerFunc(...)
        # 或: router.Methods(...).HandlerFunc(...)
        mux_query = Query(lang_obj, """
            (call_expression
                function: (selector_expression
                    field: (field_identifier) @chain_method)
                (#match? @chain_method "^(Methods|Path|HandlerFunc)$")
            ) @chain_call
        """)
        queries.append(mux_query)
        
        # Gin/Echo: r.GET("/path", handler)
        gin_query = Query(lang_obj, """
            (call_expression
                function: (selector_expression
                    operand: (identifier) @router
                    field: (field_identifier) @method)
                arguments: (argument_list
                    (interpreted_string_literal) @path
                    (_) @handler)
                (#match? @method "^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Any|Handle|Group)$")
            ) @route_call
        """)
        queries.append(gin_query)
        
        # net/http: http.HandleFunc("/path", handler) 或 mux.HandleFunc("/path", handler)
        http_query = Query(lang_obj, """
            (call_expression
                function: (selector_expression
                    operand: (identifier) @http_or_mux
                    field: (field_identifier) @handle_method)
                arguments: (argument_list
                    (interpreted_string_literal) @path
                    (_) @handler)
                (#match? @handle_method "^(HandleFunc|Handle)$")
            ) @http_route
        """)
        queries.append(http_query)
    
    elif language == "java":
        # Spring: @GetMapping("/path")
        spring_query = Query(lang_obj, """
            (annotation
                name: (identifier) @annotation
                arguments: (annotation_argument_list
                    (element_value_pair
                        key: (identifier) @key
                        value: (string_literal) @path)
                    | (string_literal) @path)
                (#match? @annotation "^(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)$")
            ) @route_annotation
        """)
        queries.append(spring_query)
    
    return queries


def format_routes_output(routes: List[RouteInfo]) -> str:
    """格式化路由输出为 Markdown。"""
    output = []
    output.append("# 路由清单\n")
    output.append(f"## 概述\n")
    output.append(f"- **总路由数**: {len(routes)}\n")
    output.append("\n## 路由列表\n\n")
    
    for route in routes:
        output.append(f"### {route.method} {route.path}\n")
        output.append(f"- **文件**: {route.file_path}:{route.line_number}\n")
        if route.handler_name:
            output.append(f"- **Handler**: {route.handler_name}")
            if route.handler_file:
                output.append(f" ({route.handler_file}:{route.handler_line})")
            output.append("\n")
        if route.is_conditional:
            output.append(f"- **条件注册**: {route.condition}\n")
        if route.middleware:
            output.append(f"- **中间件**: {', '.join(route.middleware)}\n")
        if route.risk_level:
            output.append(f"- **风险等级**: {route.risk_level}\n")
        output.append("\n")
    
    return "".join(output)


def main():
    parser = argparse.ArgumentParser(description="路由扫描脚本（使用 tree-sitter）")
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
    
    code_extensions = get_code_extensions(language)
    parser_manager = TreeSitterParserManager()
    
    print(f"项目路径: {root}")
    print(f"检测到语言: {language}")
    print(f"搜索代码文件: {', '.join(code_extensions)}")
    print("=" * 80)
    
    # 扫描路由
    routes = scan_routes_with_treesitter(root, language, parser_manager, code_extensions, debug=args.debug)
    
    print(f"\n找到 {len(routes)} 个路由")
    
    # 输出结果
    if args.json:
        routes_dict = [asdict(r) for r in routes]
        output = json.dumps(routes_dict, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
        else:
            print(output)
    else:
        output = format_routes_output(routes)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
        else:
            print(output)
    
    print("\n" + "=" * 80)
    print("扫描完成")


if __name__ == "__main__":
    main()


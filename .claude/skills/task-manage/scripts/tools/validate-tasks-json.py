#!/usr/bin/env python3
# validate-tasks-json.py
# 验证 tasks.json 文件是否符合 Schema
#
# 用法：
#   validate-tasks-json.py <json_file> <schema_file>
#
# 参数：
#   json_file: 要验证的 JSON 文件路径（必需）
#   schema_file: Schema 文件路径（必需）

import json
import sys
import os

def validate_tasks_json(json_file, schema_file):
    """验证 tasks.json 文件是否符合 Schema"""
    
    # 检查文件是否存在
    if not os.path.exists(json_file):
        print(f"错误: JSON 文件不存在: {json_file}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(schema_file):
        print(f"警告: Schema 文件不存在: {schema_file}，跳过校验", file=sys.stderr)
        sys.exit(0)
    
    try:
        import jsonschema
        from jsonschema import validate
    except ImportError:
        print("警告: jsonschema 库未安装，跳过 Schema 校验", file=sys.stderr)
        print("安装方法: pip install jsonschema", file=sys.stderr)
        sys.exit(0)
    
    # 读取 schema
    try:
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ Schema 文件格式错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ 读取 Schema 文件失败: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 读取 tasks.json
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ JSON 文件格式错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ 读取 JSON 文件失败: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 验证
    try:
        validate(instance=data, schema=schema)
        sys.exit(0)
    except jsonschema.ValidationError as e:
        print("✗ Schema 验证失败:", file=sys.stderr)
        path = " -> ".join(str(x) for x in e.path) if e.path else "root"
        print(f"  错误路径: {path}", file=sys.stderr)
        print(f"  错误信息: {e.message}", file=sys.stderr)
        sys.exit(1)
    except jsonschema.SchemaError as e:
        print(f"✗ Schema 文件错误: {e.message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: validate-tasks-json.py <json_file> <schema_file>", file=sys.stderr)
        sys.exit(1)
    
    json_file = sys.argv[1]
    schema_file = sys.argv[2]
    
    validate_tasks_json(json_file, schema_file)


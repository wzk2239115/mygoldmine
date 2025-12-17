"""
CLI - 命令行入口
"""
import argparse
import sys
from pathlib import Path
from .core.scanner import Scanner
from .reports.json_reporter import JSONReporter
from .reports.sarif_reporter import SARIFReporter


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='XSS Sink Detector - 基于Tree-sitter的XSS漏洞检测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 扫描单个文件并输出JSON报告
  python -m xss_sink_detector.cli --lang php --output json /path/to/code.php

  # 扫描整个目录
  python -m xss_sink_detector.cli --lang python --output json /path/to/project

  # 生成SARIF报告
  python -m xss_sink_detector.cli --output sarif --output-file report.sarif /path/to/code

  # 扫描所有支持语言的文件
  python -m xss_sink_detector.cli --output json --output-file report.json /path/to/project
        """
    )

    parser.add_argument(
        'path',
        type=str,
        help='要扫描的文件或目录路径'
    )

    parser.add_argument(
        '--lang',
        '-l',
        type=str,
        choices=['php', 'python', 'javascript', 'java', 'auto'],
        default='auto',
        help='编程语言 (默认: auto自动检测)'
    )

    parser.add_argument(
        '--output',
        '-o',
        type=str,
        choices=['json', 'sarif', 'text'],
        default='text',
        help='输出格式 (默认: text)'
    )

    parser.add_argument(
        '--output-file',
        '-f',
        type=str,
        default=None,
        help='输出文件路径（可选，不指定则输出到stdout）'
    )

    parser.add_argument(
        '--compact',
        action='store_true',
        help='生成紧凑的JSON输出（无缩进）'
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='详细输出模式'
    )

    args = parser.parse_args()

    # 验证路径
    path = Path(args.path)
    if not path.exists():
        print(f"错误: 路径不存在: {args.path}", file=sys.stderr)
        sys.exit(1)

    # 创建扫描器
    scanner = Scanner()

    # 执行扫描
    try:
        if args.verbose:
            print(f"开始扫描: {args.path}", file=sys.stderr)

        if path.is_file():
            results = scanner.scan_file(str(path))
            scan_root = str(path.parent)
        else:
            results = scanner.scan_directory(str(path))
            scan_root = str(path)

        if args.verbose:
            print(f"发现 {len(results)} 个XSS Sink", file=sys.stderr)

        # 生成报告
        output = _generate_output(results, args.output, args.compact, scan_root)

        # 输出结果
        if args.output_file:
            output_path = Path(args.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"报告已生成: {args.output_file}", file=sys.stderr)
        else:
            print(output)

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def _generate_output(results, output_format, compact=False, scan_root=None):
    """生成输出"""
    if output_format == 'json':
        if compact:
            return JSONReporter.generate_compact(results)
        else:
            return JSONReporter.generate(results)

    elif output_format == 'sarif':
        return SARIFReporter.generate(results)

    else:  # text
        return _format_text_output(results, scan_root)


def _format_text_output(results, scan_root=None):
    """格式化文本输出"""
    lines = []

    if not results:
        lines.append("✓ 未发现XSS Sink")
        return '\n'.join(lines)

    lines.append(f"发现 {len(results)} 个XSS Sink\n")

    # 按文件分组
    by_file = {}
    for result in results:
        filepath = result['file']
        if filepath not in by_file:
            by_file[filepath] = []
        by_file[filepath].append(result)

    # 获取工作目录以计算相对路径
    import os

    # 如果提供了扫描根目录，相对于它计算相对路径
    if scan_root:
        base_dir = os.path.abspath(scan_root)
    else:
        base_dir = os.getcwd()

    # 输出结果
    for filepath in sorted(by_file.keys()):
        # 转换为相对路径（相对于扫描根目录）
        try:
            rel_path = os.path.relpath(filepath, base_dir)
        except ValueError:
            # 如果无法计算相对路径，使用原路径
            rel_path = filepath

        lines.append(f"{rel_path}")
        for result in by_file[filepath]:
            # 只显示主要的 sink_type，跳过 obj、field、method 等附加的 capture
            sink_type = result['sink_type']
            if sink_type not in ('obj', 'field', 'method', 'prop', 'func'):
                lines.append(
                    f"  Line {result['line']:4d}: {sink_type:25s} {result['code'][:60]}"
                )
        lines.append("")

    # 统计
    by_language = {}
    by_type = {}

    for result in results:
        lang = result['language']
        sink_type = result['sink_type']

        # 只统计主要的 sink_type，跳过附加的 capture
        if sink_type not in ('obj', 'field', 'method', 'prop', 'func'):
            by_language[lang] = by_language.get(lang, 0) + 1
            by_type[sink_type] = by_type.get(sink_type, 0) + 1

    lines.append("统计信息:")
    lines.append("  按语言:")
    for lang, count in sorted(by_language.items()):
        lines.append(f"    {lang:15s}: {count:3d}")

    lines.append("  按类型:")
    for sink_type, count in sorted(by_type.items()):
        lines.append(f"    {sink_type:25s}: {count:3d}")

    return '\n'.join(lines)


if __name__ == '__main__':
    main()

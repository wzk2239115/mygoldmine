"""
JSON Reporter - 生成JSON格式的报告
"""
import json
from typing import List, Dict
from pathlib import Path


class JSONReporter:
    """JSON格式报告生成器"""

    @staticmethod
    def generate(results: List[Dict], output_file: str = None) -> str:
        """
        生成JSON格式报告

        Args:
            results: 检测结果列表
            output_file: 输出文件路径（可选）

        Returns:
            JSON字符串
        """
        report = {
            "status": "success",
            "total_sinks_found": len(results),
            "results": results,
            "summary_by_language": JSONReporter._summarize_by_language(results),
            "summary_by_sink_type": JSONReporter._summarize_by_sink_type(results)
        }

        json_str = json.dumps(report, indent=2, ensure_ascii=False)

        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(json_str)

        return json_str

    @staticmethod
    def _summarize_by_language(results: List[Dict]) -> Dict[str, int]:
        """按语言汇总结果"""
        summary = {}
        for result in results:
            language = result.get('language', 'unknown')
            summary[language] = summary.get(language, 0) + 1
        return summary

    @staticmethod
    def _summarize_by_sink_type(results: List[Dict]) -> Dict[str, int]:
        """按Sink类型汇总结果"""
        summary = {}
        for result in results:
            sink_type = result.get('sink_type', 'unknown')
            summary[sink_type] = summary.get(sink_type, 0) + 1
        return summary

    @staticmethod
    def generate_compact(results: List[Dict], output_file: str = None) -> str:
        """
        生成紧凑的JSON报告（无缩进）

        Args:
            results: 检测结果列表
            output_file: 输出文件路径（可选）

        Returns:
            JSON字符串
        """
        report = {
            "status": "success",
            "total": len(results),
            "results": results
        }

        json_str = json.dumps(report, ensure_ascii=False, separators=(',', ':'))

        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(json_str)

        return json_str

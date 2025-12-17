"""
SARIF Reporter - 生成SARIF格式报告
SARIF: Static Analysis Results Interchange Format
"""
import json
from typing import List, Dict
from pathlib import Path
from datetime import datetime


class SARIFReporter:
    """SARIF格式报告生成器"""

    TOOL_NAME = "XSS Sink Detector"
    TOOL_VERSION = "1.0.0"

    @staticmethod
    def generate(results: List[Dict], output_file: str = None) -> str:
        """
        生成SARIF格式报告

        Args:
            results: 检测结果列表
            output_file: 输出文件路径（可选）

        Returns:
            SARIF JSON字符串
        """
        sarif_report = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": SARIFReporter.TOOL_NAME,
                            "version": SARIFReporter.TOOL_VERSION,
                            "informationUri": "https://github.com/yourusername/xss-sink-detector",
                            "rules": SARIFReporter._generate_rules()
                        }
                    },
                    "results": [SARIFReporter._convert_result(r) for r in results],
                    "invocation": {
                        "executionSuccessful": True,
                        "endTimeUtc": datetime.utcnow().isoformat() + "Z",
                        "toolExecutionNotifications": []
                    }
                }
            ]
        }

        json_str = json.dumps(sarif_report, indent=2, ensure_ascii=False)

        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(json_str)

        return json_str

    @staticmethod
    def _generate_rules() -> List[Dict]:
        """生成规则定义"""
        return [
            {
                "id": "xss_sink",
                "name": "XSS Sink Detection",
                "shortDescription": {
                    "text": "Detects potential XSS sinks in code"
                },
                "fullDescription": {
                    "text": "This rule identifies functions and expressions that are potential XSS sinks, "
                            "such as output functions, DOM manipulation methods, and dynamic code execution."
                },
                "defaultConfiguration": {
                    "level": "warning"
                },
                "help": {
                    "text": "XSS sinks are locations where untrusted data can be executed as code in the browser. "
                            "Ensure that all data passed to these functions is properly sanitized or escaped."
                }
            }
        ]

    @staticmethod
    def _convert_result(result: Dict) -> Dict:
        """将检测结果转换为SARIF格式"""
        return {
            "ruleId": "xss_sink",
            "level": "warning",
            "message": {
                "text": f"Potential XSS sink: {result.get('sink_type', 'unknown')} at {result.get('file')}"
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": result.get('file', ''),
                            "uriBaseId": "%SRCROOT%"
                        },
                        "region": {
                            "startLine": result.get('line', 0),
                            "startColumn": result.get('column', 0),
                            "endLine": result.get('end_line', result.get('line', 0)),
                            "endColumn": result.get('end_column', 0),
                            "snippet": {
                                "text": result.get('code', result.get('node_text', ''))
                            }
                        }
                    }
                }
            ],
            "partialFingerprints": {
                "primaryLocationLineHash": str(hash(result.get('node_text', '')))
            }
        }

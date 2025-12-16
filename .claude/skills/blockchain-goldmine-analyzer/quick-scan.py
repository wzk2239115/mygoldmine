#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""智能合约快速扫描脚本。

识别合约编程语言、推断应用场景，生成审计建议报告。
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# 合约类型特征关键词
APPLICATION_KEYWORDS = {
    "DeFi": ["swap", "liquidity", "borrow", "lend", "oracle", "amm", "dex", "lending", "yield", "pool"],
    "NFT": ["erc721", "erc1155", "nft", "mint", "burn", "token uri", "metadata"],
    "Cross-Chain": ["bridge", "relay", "interop", "cross-chain", "attestation", "signature"],
    "Governance": ["vote", "proposal", "timelock", "governance", "dao"],
    "Stablecoin": ["stablecoin", "collateral", "peg", "liquidation", "mint"],
    "Derivative": ["derivative", "perpetual", "leverage", "liquidation", "future"],
    "Token": ["erc20", "transfer", "approve", "burn"],
}

# 编程语言特有漏洞
LANGUAGE_SPECIFIC_RISKS = {
    "Solidity": [
        "Reentrancy",
        "Delegatecall",
        "Selfdestruct",
        "DoS Attacks",
        "Front-Running & MEV",
    ],
    "Rust": [
        "CPI Reentrancy",
        "Account Validation",
        "Signer Verification",
        "Integer Overflow",
    ],
    "Move": [
        "Resource Safety",
        "Capability Patterns",
        "Integer Overflow",
    ],
    "Vyper": [
        "Reentrancy",
        "Raw Call",
        "Gas Optimization",
    ],
    "Go": [
        "Keeper Vulnerabilities",
        "IBC Security",
        "Integer Overflow",
    ],
}

# 应用场景特有漏洞
APPLICATION_SPECIFIC_RISKS = {
    "DeFi": {
        "critical": ["Flash Loan", "Oracle Manipulation", "Reentrancy"],
        "high": ["Front-Running & MEV", "Business Logic"],
    },
    "NFT": {
        "critical": ["Access Control", "Business Logic"],
        "high": ["Insecure Randomness", "Integer Overflow"],
    },
    "Cross-Chain": {
        "critical": ["Cross-Chain Bridge", "Signature Verification"],
        "high": ["DoS Attacks", "Integer Overflow"],
    },
    "Governance": {
        "critical": ["Governance", "Access Control"],
        "high": ["Timestamp Dependence", "Business Logic"],
    },
    "Stablecoin": {
        "critical": ["Oracle Manipulation", "Business Logic"],
        "high": ["Integer Overflow", "Access Control"],
    },
    "Derivative": {
        "critical": ["Business Logic", "Front-Running & MEV", "Oracle Manipulation"],
        "high": ["Integer Overflow", "Reentrancy"],
    },
}


def detect_language(root: Path) -> Optional[str]:
    """检测合约编程语言。"""
    # 检查源文件
    extensions = {
        ".sol": "Solidity",
        ".rs": "Rust",
        ".move": "Move",
        ".vy": "Vyper",
        ".go": "Go",
    }

    for ext, language in extensions.items():
        # 在根目录及主要子目录中查找
        for search_dir in [root, root / "contracts", root / "src"]:
            if search_dir.exists():
                try:
                    for file in search_dir.glob(f"*{ext}"):
                        if file.is_file():
                            return language
                except Exception:
                    pass

    # 检查代码关键词
    code_keywords = {
        "pragma solidity": "Solidity",
        "#[program]": "Rust",
        "module {": "Move",
        "public fun": "Move",
    }

    try:
        for file in root.rglob("*"):
            if file.is_file() and file.suffix in [".sol", ".rs", ".move", ".vy", ".go"]:
                try:
                    content = file.read_text(encoding="utf-8").lower()
                    for keyword, language in code_keywords.items():
                        if keyword.lower() in content:
                            return language
                except Exception:
                    pass
    except Exception:
        pass

    return None


def detect_framework(root: Path, language: Optional[str]) -> Optional[str]:
    """检测合约框架/工具链。"""
    frameworks = {
        "hardhat.config.js": "Hardhat",
        "hardhat.config.ts": "Hardhat",
        "truffle-config.js": "Truffle",
        "truffle.js": "Truffle",
        "foundry.toml": "Foundry",
        "Anchor.toml": "Anchor",
        "go.mod": "Cosmos SDK / Go Modules",
    }

    for config_file, framework in frameworks.items():
        if (root / config_file).exists():
            return framework

    # 检查 package.json 中的开发依赖
    if (root / "package.json").exists():
        try:
            with (root / "package.json").open() as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "hardhat" in deps:
                    return "Hardhat"
                elif "truffle" in deps:
                    return "Truffle"
                elif "foundry" in deps or "@foundry/cli" in deps:
                    return "Foundry"
        except Exception:
            pass

    # 检查 Cargo.toml 中的依赖
    if (root / "Cargo.toml").exists():
        try:
            content = (root / "Cargo.toml").read_text().lower()
            if "anchor" in content:
                return "Anchor"
            elif "solana-program" in content:
                return "Solana SDK"
        except Exception:
            pass

    return None


def infer_application(root: Path) -> Optional[str]:
    """推断应用场景。"""
    # 收集所有代码内容
    code_content = ""
    try:
        for file in root.rglob("*"):
            if file.is_file() and file.suffix in [".sol", ".rs", ".move", ".vy", ".go", ".ts", ".js"]:
                try:
                    code_content += file.read_text(encoding="utf-8").lower()
                except Exception:
                    pass
    except Exception:
        pass

    # 检查 README
    try:
        for readme_file in ["README.md", "README.txt", "README"]:
            readme_path = root / readme_file
            if readme_path.exists():
                code_content += readme_path.read_text(encoding="utf-8").lower()
    except Exception:
        pass

    # 匹配应用场景
    scores = {}
    for app, keywords in APPLICATION_KEYWORDS.items():
        scores[app] = sum(1 for keyword in keywords if keyword in code_content)

    # 返回得分最高的应用场景
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)

    return None


def get_audit_checklist(language: Optional[str], application: Optional[str]) -> Dict:
    """生成审计检查清单。"""
    checklist = {
        "priority_1": [
            "Access Control",
            "Integer Overflow/Underflow",
            "Business Logic Flaws",
            "Signature Verification",
        ],
        "priority_2": [],
        "application_specific": [],
    }

    # 添加语言特定的审计项
    if language and language in LANGUAGE_SPECIFIC_RISKS:
        checklist["priority_2"] = LANGUAGE_SPECIFIC_RISKS[language]

    # 如果是 EVM（Solidity/Vyper），必须包含 Reentrancy
    if language in ["Solidity", "Vyper"] and "Reentrancy" not in checklist["priority_1"]:
        checklist["priority_1"].append("Reentrancy")

    # 添加应用场景特定的审计项
    if application and application in APPLICATION_SPECIFIC_RISKS:
        app_risks = APPLICATION_SPECIFIC_RISKS[application]
        checklist["application_specific"] = app_risks.get("critical", []) + app_risks.get("high", [])

    return checklist


def format_markdown_report(
    root: Path,
    language: Optional[str],
    framework: Optional[str],
    application: Optional[str],
    evidence: Dict,
    checklist: Dict,
) -> str:
    """格式化输出为 Markdown 报告。"""
    lines = []

    lines.append("# 智能合约审计建议")
    lines.append("")

    # 基本信息
    lines.append("## 基本信息")
    lines.append(f"- **项目名称**：{root.name}")
    lines.append(f"- **项目路径**：{root}")
    lines.append(f"- **扫描时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **项目分类**：智能合约项目")
    lines.append("")

    # 合约编程语言
    lines.append("## 合约编程语言")
    lines.append(f"- **主要语言**：{language or '未识别'}")
    lines.append(f"- **框架/工具链**：{framework or '未识别'}")
    if language and evidence:
        lines.append(f"- **检测依据**：{evidence.get('language_evidence', '文件扩展名和代码特征')}")
    lines.append("")

    # 应用场景推断
    lines.append("## 应用场景推断")
    lines.append(f"- **推断场景**：{application or '通用合约'}")
    if application:
        app_keywords = APPLICATION_KEYWORDS.get(application, [])
        lines.append(f"- **场景特征**：包含关键词 {', '.join(app_keywords[:5])}")
    else:
        lines.append("- **场景特征**：未检测到明确的应用场景特征")
    lines.append("")

    # 审计建议
    lines.append("## 审计建议")
    lines.append("")

    # 优先级 1
    lines.append("### 优先级 1 - 必须检查（关键）")
    for item in checklist.get("priority_1", []):
        lines.append(f"- [ ] **{item}** - 详见 Blockchain Security Goldmine")
    lines.append("")

    # 优先级 2（语言特定）
    if checklist.get("priority_2"):
        lines.append("### 优先级 2 - 重点检查（高）")
        for item in checklist.get("priority_2", []):
            lines.append(f"- [ ] **{item}** - 语言特定风险")
        lines.append("")

    # 应用场景特定
    if checklist.get("application_specific"):
        lines.append("### 优先级 3 - 应用场景特定检查")
        for item in checklist.get("application_specific", []):
            lines.append(f"- [ ] **{item}** - {application} 特有风险")
        lines.append("")

    # 推荐资源
    lines.append("## 推荐资源")
    lines.append("- 📚 Blockchain Security Goldmine：`.claude/skills/blockchain_goldmine/`")
    lines.append("- 🛠️ 静态分析工具：")
    if language == "Solidity":
        lines.append("  - Slither：https://github.com/crytic/slither")
        lines.append("  - Mythril：https://github.com/ConsenSys/mythril")
    elif language == "Rust":
        lines.append("  - cargo-audit：https://rustsec.org/")
        lines.append("  - Clippy：https://github.com/rust-lang/rust-clippy")
    elif language == "Move":
        lines.append("  - Move Prover：https://github.com/move-language/move")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="智能合约快速扫描和审计建议生成")
    parser.add_argument("path", nargs="?", default=".", help="项目路径")
    parser.add_argument("--output", help="输出文件路径（默认打印到标准输出）")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"路径不存在: {root}")
        return

    # 检测语言和框架
    language = detect_language(root)
    framework = detect_framework(root, language)
    application = infer_application(root)

    # 生成审计检查清单
    checklist = get_audit_checklist(language, application)

    # 生成报告
    evidence = {
        "language_evidence": f"检测到 {language} 源文件" if language else "未检测到源文件",
    }

    report = format_markdown_report(root, language, framework, application, evidence, checklist)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"报告已保存到: {output_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()

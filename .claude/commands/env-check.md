---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Check development environment, dependencies, and services
argument-hint: [--python | --node | --deps | --services]
---


# 环境检查

> 检查开发环境配置、依赖版本和兼容性

## 任务

全面检查当前开发环境，确保所有依赖和配置正确。

## 检查项目

### 1. 运行时环境

```bash
# Python
python --version
pip --version
which python

# Node.js
node --version
npm --version
which node

# 其他
java --version
go version
```

### 2. 包管理器

```bash
# Python
pip list --outdated
pip check  # 检查依赖冲突

# Node.js
npm outdated
npm audit

# 系统包
brew outdated  # macOS
apt list --upgradable  # Ubuntu
```

### 3. 项目依赖

**Python 项目**:
```bash
# 检查 requirements.txt
pip install -r requirements.txt --dry-run

# 检查 pyproject.toml
pip install . --dry-run

# 虚拟环境
echo $VIRTUAL_ENV
```

**Node.js 项目**:
```bash
# 检查 package.json
npm install --dry-run
npm ls  # 依赖树
```

### 4. 配置文件

检查以下文件是否存在且有效：
- `.env` / `.env.local`
- `config.yaml` / `config.json`
- `docker-compose.yml`
- `Makefile`

### 5. 外部服务

```bash
# 数据库连接
pg_isready -h localhost
mysql -e "SELECT 1"
redis-cli ping

# API 服务
curl -s http://localhost:8080/health
```

## 输出格式

```markdown
## 环境检查报告

### ✅ 通过项
- [x] Python 3.11.0
- [x] Node.js 20.10.0
- [x] 所有依赖已安装

### ⚠️ 警告项
- [ ] npm 有 3 个过时的包
- [ ] Python 依赖有安全更新

### ❌ 失败项
- [ ] Redis 连接失败
- [ ] 缺少 .env 文件

### 建议操作
1. 运行 `npm update` 更新过时的包
2. 创建 `.env` 文件（参考 `.env.example`）
3. 启动 Redis 服务
```

## 常见问题修复

### Python 版本不匹配
```bash
# 使用 pyenv
pyenv install 3.11
pyenv local 3.11
```

### Node.js 版本不匹配
```bash
# 使用 nvm
nvm install 20
nvm use 20
```

### 依赖冲突
```bash
# Python
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall

# Node.js
rm -rf node_modules package-lock.json
npm install
```

## 示例

```
/env-check              # 完整环境检查
/env-check --python     # 仅检查 Python 环境
/env-check --deps       # 仅检查依赖
/env-check --services   # 仅检查外部服务
```

------

**最后更新**: 2025-11-30 16:10:35
**维护者**: Documentation Team
**版本**: 1.0.0

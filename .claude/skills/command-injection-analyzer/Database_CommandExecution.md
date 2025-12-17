# 数据库命令执行

## Details

**代码特征示例：**
```sql
-- SQL Server xp_cmdshell（需要管理员权限）
EXEC xp_cmdshell 'dir C:\';
EXEC xp_cmdshell 'whoami';
EXEC master..xp_cmdshell 'powershell.exe -Command "Get-Process"';

-- SQL Server OLE Automation（需要管理员权限）
DECLARE @shell INT;
EXEC sp_OACreate 'WScript.Shell', @shell OUTPUT;
EXEC sp_OAMethod @shell, 'Run', NULL, 'cmd.exe /c tasklist';

-- MySQL LOAD_FILE 和 INTO OUTFILE（需要 FILE 权限）
SELECT LOAD_FILE('/etc/passwd');
SELECT '<?php system($_GET["cmd"]); ?>' INTO OUTFILE '/var/www/html/shell.php';

-- PostgreSQL copy 和 program（需要超级用户权限）
COPY (SELECT 1) TO PROGRAM 'id > /tmp/output.txt';

-- MongoDB $where 操作符（客户端代码执行）
db.collection.find({$where: "function(){...} return true"});

-- Oracle DBMS_JAVA 和外部过程调用
BEGIN
  DBMS_JAVA.runjava('java.lang.Runtime.getRuntime().exec("touch /tmp/pwned")');
END;

-- Redis 远程代码执行（旧版本或配置不当）
CONFIG SET dir /var/www/html
CONFIG SET dbfilename shell.php
SAVE

-- Elasticsearch 远程代码执行（某些版本）
POST /_scripts/painless
GET /_cat/nodes?h=version

-- GraphQL 中的命令注入
query {
  executeCommand(cmd: "ls && cat /etc/passwd")
}
```

**快速定位核心操作：**
- SQL Server：全局搜索 `xp_cmdshell`、`sp_OACreate`、`sp_OAMethod`、`WScript.Shell`
- MySQL：搜索 `LOAD_FILE`、`INTO OUTFILE`、`INTO DUMPFILE`
- PostgreSQL：搜索 `COPY.*PROGRAM`、`pg_execute`
- MongoDB：搜索 `$where`、`mapReduce`、`function()`
- Oracle：搜索 `DBMS_JAVA`、`DBMS_SQL`、外部过程调用
- Redis：搜索 `CONFIG SET`、`EVAL`、`SCRIPT LOAD`
- 关注上下文：用户输入是否直接参与 SQL 拼接

**快速定位保护机制：**
- 权限检查：当前用户是否具有执行这些危险操作的权限
- 输入过滤：是否对用户输入进行了白名单验证
- 参数化查询：是否使用了预准备语句
- 功能禁用：是否在数据库层面禁用了这些危险功能
- 审计日志：是否记录所有命令执行操作

**审计等级：L3（逐行读）**
- 数据库命令执行危险性极高
- 需逐行分析用户输入如何进入数据库查询
- 检查权限模型是否真的能阻止这些操作

## Classify

**确认为漏洞：**
- 用户输入直接拼接到 xp_cmdshell、COPY PROGRAM 等危险 SQL 函数
- 数据库用户权限过高（如 MSSQL 使用 sa 账户）
- 使用 ORM 时直接拼接原生 SQL 而不是使用参数化查询
- MySQL with `LOAD_FILE` 或 `INTO OUTFILE` 且无访问控制
- PostgreSQL `COPY TO/FROM PROGRAM` 且 SQL 包含用户输入
- MongoDB `$where` 操作符执行用户提供的 JavaScript 代码

**误报：**
- 命令完全硬编码，无用户输入
- 使用了参数化查询且用户输入不在危险函数参数中
- 数据库用户权限受限（如 MySQL 的 `FILE` 权限被收回）
- 这些危险功能在数据库层面已被禁用
- 用户输入仅用于选择预定义的操作（通过白名单）

**代码异味：**
- 使用字符串拼接构造 SQL 查询（即使暂未发现用户输入）
- 数据库用户权限过高
- 存在多个数据库服务但权限配置不一致
- 依赖前端验证或应用层防护

## Low risk

**低风险场景：**
- 数据库仅在内网使用，访问受 VPN/防火墙限制
- 数据库用户权限严格受限（无 FILE、无 ADMIN 权限）
- 这些危险功能在数据库配置中已被禁用
- 执行命令的操作需要管理员手动审批
- 存在完善的审计日志记录和告警机制
- 执行的命令受限于特定的安全列表

**降级因素：**
- 数据库以非 root/Administrator 用户运行
- 容器化部署且文件系统只读或受限挂载
- 数据库和应用部署在同一容器内，无法访问主机文件系统
- 命令执行失败不会造成信息泄露（如输出被重定向到应用无法访问的位置）

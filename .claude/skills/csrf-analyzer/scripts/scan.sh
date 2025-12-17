#!/bin/bash

# CSRF (Cross-Site Request Forgery) 相关代码检索脚本
# 支持语言: C/C++, Python, Java, Go, PHP, Rust, TypeScript, Ruby, C#
# 用途: 快速定位跨站请求相关的代码文件
# 优化: 减少误报，聚焦真实风险点

echo "======================================"
echo "跨站请求相关代码检索"
echo "======================================"


TARGET_DIR="${1:-.}"
echo "扫描目录: $TARGET_DIR"


# 切换到目标目录，使输出使用相对路径
cd "$TARGET_DIR" || exit 1

# 关闭用户侧配置，防止 CI 乱码
export RIPGREP_CONFIG_PATH=""

# 统计变量
declare -A STATS
STATS["csrf_disabled"]=0
STATS["csrf_protected"]=0
STATS["suspicious_endpoints"]=0
STATS["forms_with_token"]=0
STATS["forms_without_token"]=0

# 辅助函数：快速检测语言
detect_languages() {
    echo "正在检测代码库语言分布..."
    local files=$(rg --files 2>/dev/null | head -5000)
    
    [[ "$files" =~ \.py$ ]] && echo "  ✓ Python"
    [[ "$files" =~ \.java$ ]] && echo "  ✓ Java"
    [[ "$files" =~ \.(ts|tsx|js|jsx)$ ]] && echo "  ✓ TypeScript/JavaScript"
    [[ "$files" =~ \.php$ ]] && echo "  ✓ PHP"
    [[ "$files" =~ \.go$ ]] && echo "  ✓ Go"
    [[ "$files" =~ \.rs$ ]] && echo "  ✓ Rust"
    [[ "$files" =~ \.rb$ ]] && echo "  ✓ Ruby"
    [[ "$files" =~ \.cs$ ]] && echo "  ✓ C#"
    
}

detect_languages

# Java - Spring Security 显式关闭 CSRF
echo "【高危】Java Spring - 显式关闭 CSRF (csrf().disable):"
result=$(rg -t java -n "csrf\(\)\.disable|\.csrf\(\)\.ignoringAntMatchers|csrf.*disable.*true" . -C 2 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_disabled"]=$((STATS["csrf_disabled"] + $(echo "$result" | grep -c "^[0-9]")))
else
    echo "✓ 未发现"
fi


# Laravel - 关闭 CSRF 中间件
echo "【高危】PHP Laravel - 排除 CSRF 保护 (VerifyCsrfToken except):"
result=$(rg -t php -n "VerifyCsrfToken.*except|csrf.*disable|csrf.*false" . -C 2 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_disabled"]=$((STATS["csrf_disabled"] + $(echo "$result" | grep -c "^[0-9]")))
else
    echo "✓ 未发现"
fi


# Rails - 跳过 CSRF 保护
echo "【高危】Ruby Rails - 跳过 CSRF 保护 (skip_forgery_protection):"
result=$(rg -t ruby -n "skip_forgery_protection|skip_before_action.*verify_authenticity_token" . -C 2 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_disabled"]=$((STATS["csrf_disabled"] + $(echo "$result" | grep -c "^[0-9]")))
else
    echo "✓ 未发现"
fi


# ASP.NET - 忽略反伪造
echo "【高危】C# ASP.NET - 忽略防伪 (IgnoreAntiforgeryToken):"
result=$(rg -t cs -n "IgnoreAntiforgeryToken|ValidateAntiForgeryToken.*false" . -C 2 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_disabled"]=$((STATS["csrf_disabled"] + $(echo "$result" | grep -c "^[0-9]")))
else
    echo "✓ 未发现"
fi


# Python - Django 可疑端点（有 POST 但无 csrf 防护）
echo "【可疑】Python Django - POST/PUT/DELETE 路由（请人工确认是否有 CSRF 保护）:"
result=$(rg -t py -i -n "@.*route.*methods.*[\"']POST|@.*route.*methods.*[\"']PUT|@.*route.*methods.*[\"']DELETE" . -C 3 --color=never --max-columns 200 2>/dev/null | \
    rg -v "csrf_protect|csrf_exempt|CsrfViewMiddleware|@csrf" 2>/dev/null | head -25)
if [ -n "$result" ]; then
    echo "$result"
    STATS["suspicious_endpoints"]=$((STATS["suspicious_endpoints"] + 1))
else
    echo "✓ 未发现"
fi


# Python - Flask 可疑端点
echo "【可疑】Python Flask - POST 方法（请确认是否使用 CSRFProtect）:"
result=$(rg -t py -i -n "@app\.route.*POST|@blueprint\.route.*POST" . -C 3 --color=never --max-columns 200 2>/dev/null | \
    rg -v "CSRFProtect|flask_wtf|csrf\.exempt" 2>/dev/null | head -25)
if [ -n "$result" ]; then
    echo "$result"
    STATS["suspicious_endpoints"]=$((STATS["suspicious_endpoints"] + 1))
else
    echo "✓ 未发现"
fi


# Python - FastAPI 补充
echo "【信息】Python FastAPI - CSRF 保护检查 (fastapi_csrf/CSRFProtect):"
result=$(rg -t py -i -n "fastapi_csrf|CSRFProtect.*FastAPI|from.*csrf.*import" . -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_protected"]=$((STATS["csrf_protected"] + 1))
else
    echo "0 匹配"
fi


# Java - Spring Security 正常配置
echo "【信息】Java Spring - CSRF Token 配置检查 (CsrfToken/CookieCsrfTokenRepository):"
result=$(rg -t java -i -n "CsrfToken|CsrfTokenRepository|CookieCsrfTokenRepository|XorCsrfTokenRepository|@EnableWebSecurity" . -C 1 --color=never --max-columns 150 2>/dev/null | \
    rg -v "disable" 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_protected"]=$((STATS["csrf_protected"] + 1))
else
    echo "0 匹配"
fi


# Java - 可疑端点（POST/PUT/DELETE 映射，上下文无 CSRF 保护关键字）
echo "【可疑】Java Spring - 状态改变端点（@PostMapping/@PutMapping/@DeleteMapping）:"
result=$(rg -t java -i -n "@PostMapping|@PutMapping|@DeleteMapping|@RequestMapping.*POST" . -C 3 --color=never --max-columns 200 2>/dev/null | \
    rg -v "CsrfToken|csrf\(\)|ignoringAntMatchers" 2>/dev/null | head -25)
if [ -n "$result" ]; then
    echo "$result"
    STATS["suspicious_endpoints"]=$((STATS["suspicious_endpoints"] + 1))
else
    echo "✓ 未发现"
fi


# JavaScript/TypeScript - Node.js CSRF 保护
echo "【信息】Node.js/Express - CSRF 中间件 (csurf/csrf-csrf/next-csrf/csrfSync):"
result=$(rg -t ts -t js -i -n "csurf\(|csrf-csrf|next-csrf|csrfSync|doubleCsrf|express.*csrf|app\.use.*csrf" . -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_protected"]=$((STATS["csrf_protected"] + 1))
else
    echo "0 匹配"
fi


# TypeScript - 可疑 POST 请求
echo "【可疑】TypeScript/JS - HTTP POST/PUT/DELETE 请求（请确认是否传递 CSRF Token）:"
result=$(rg -t ts -t js -i -n "\.post\(|\.put\(|\.delete\(|\.patch\(|method:.*['\"]POST|method:.*['\"]PUT" . -C 3 --color=never --max-columns 200 2>/dev/null | \
    rg -v "csrf|X-CSRF-TOKEN|_token|xsrf" 2>/dev/null | head -25)
if [ -n "$result" ]; then
    echo "$result"
    STATS["suspicious_endpoints"]=$((STATS["suspicious_endpoints"] + 1))
else
    echo "✓ 未发现"
fi


# PHP - Laravel CSRF 保护
echo "【信息】PHP Laravel - CSRF 保护检查 (@csrf/csrf_token/csrf_field/VerifyCsrfToken):"
result=$(rg -t php -i -n "@csrf|csrf_token\(\)|csrf_field\(\)|VerifyCsrfToken|CSRF-TOKEN" . -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_protected"]=$((STATS["csrf_protected"] + 1))
else
    echo "0 匹配"
fi


# PHP - WordPress Nonce
echo "【信息】PHP WordPress - Nonce 检查 (wp_nonce/check_admin_referer):"
result=$(rg -t php -i -n "wp_nonce|check_admin_referer|wp_verify_nonce|wp_create_nonce" . -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_protected"]=$((STATS["csrf_protected"] + 1))
else
    echo "0 匹配"
fi


# Go - CSRF 中间件
echo "【信息】Go - CSRF 中间件 (gorilla/csrf/nosurf):"
result=$(rg -t go -i -n "csrf\.|gorilla.*csrf|nosurf|CSRF.*Token|csrf.*Middleware|csrf\.Protect" . -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_protected"]=$((STATS["csrf_protected"] + 1))
else
    echo "0 匹配"
fi


# Rust - CSRF 保护
echo "【信息】Rust - CSRF 中间件 (actix-csrf/csrf/CsrfToken):"
result=$(rg -t rust -i -n "csrf|actix.*csrf|rocket.*csrf|CsrfToken|csrf_protection" . -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_protected"]=$((STATS["csrf_protected"] + 1))
else
    echo "0 匹配"
fi


# Ruby - Rails CSRF 保护
echo "【信息】Ruby Rails - CSRF 保护 (protect_from_forgery/authenticity_token):"
result=$(rg -t ruby -i -n "protect_from_forgery|form_authenticity_token|verify_authenticity_token|csrf_meta_tags" . -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_protected"]=$((STATS["csrf_protected"] + 1))
else
    echo "0 匹配"
fi


# C# - ASP.NET Core 反伪造
echo "【信息】C# ASP.NET - 反伪造 Token (ValidateAntiForgeryToken/AntiforgeryToken):"
result=$(rg -t cs -i -n "ValidateAntiForgeryToken|AutoValidateAntiforgeryToken|AntiForgeryToken|@Html.AntiForgeryToken" . -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
    STATS["csrf_protected"]=$((STATS["csrf_protected"] + 1))
else
    echo "0 匹配"
fi
# 通用 - CORS 配置
echo "【信息】CORS 配置 (Access-Control-Allow-Origin/cors()/allowCredentials):"
result=$(rg -i -n "Access-Control-Allow-Origin|cors\(\)|AllowedOrigins|withOrigins|allowCredentials|credentials.*true" . -g '!*.{css,min.css,min.js,map,html,md}' -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
else
    echo "0 匹配"
fi


# 通用 - SameSite Cookie
echo "【信息】Cookie 安全配置 (SameSite/secure/httponly):"
result=$(rg -i -n "SameSite.*Strict|SameSite.*Lax|SameSite.*None|secure.*true.*httponly|Set-Cookie" . -g '!*.{css,min.css,min.js,map,html,md}' -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
else
    echo "0 匹配"
fi


# HTML 表单 - 二次筛选（只要没有 token 的）
echo "【可疑】HTML 表单 - POST/PUT/DELETE 且缺少 CSRF Token:"
# 第一步：找出所有 POST/PUT/DELETE 表单文件
form_files=$(rg -i -l "<form.*method.*[\"']?(post|put|delete)" . --type-add 'html:*.{html,htm,jsp,php,ejs,erb,blade.php}' -t html 2>/dev/null)

if [ -n "$form_files" ]; then
    # 第二步：在这些文件中筛掉已包含 token 的
    suspicious_forms=$(echo "$form_files" | xargs rg -i -L "hidden.*token|hidden.*csrf|@csrf|csrf_field|csrf_token|authenticity_token" 2>/dev/null | head -10)
    
    if [ -n "$suspicious_forms" ]; then
        echo "以下文件的表单可能缺少 CSRF Token:"
        echo "$suspicious_forms" | while read -r file; do
            echo "  - $file"
            STATS["forms_without_token"]=$((STATS["forms_without_token"] + 1))
            # 显示表单片段
            rg -i -n "<form.*method.*[\"']?(post|put|delete)" "$file" -C 2 --color=never --max-columns 200 2>/dev/null | head -8
        done
    else
        echo "✓ 所有表单都包含 Token 字段"
        STATS["forms_with_token"]=$((STATS["forms_with_token"] + 1))
    fi
else
    echo "0 匹配"
fi


# 配置文件 - 安全设置
echo "【信息】配置文件 - CSRF 相关配置 (enable/disable/protect):"
result=$(rg -i -n "csrf.*enable|csrf.*protect|csrf.*disable|security.*csrf|csrf.*true|csrf.*false" . --type-add 'config:*.{yml,yaml,json,conf,config,properties,xml}' -t config -C 2 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
else
    echo "0 匹配"
fi


# 敏感业务操作
echo "【信息】敏感业务操作 (delete/update/transfer/reset - 需特别关注 CSRF 防护):"
result=$(rg -i -n "delete.*user|update.*password|transfer.*money|change.*email|reset.*password|update.*role|delete.*account|modify.*permission" . -g '!*.{css,min.css,min.js,map,html,md}' -C 1 --color=never --max-columns 150 2>/dev/null | head -20)
if [ -n "$result" ]; then
    echo "$result"
else
    echo "0 匹配"
fi


echo "扫描完成!"



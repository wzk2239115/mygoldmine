# Java_Auth_Bypass_Missing_Check

**漏洞类型**: Java Spring Security 认证中缺少某些路由或操作的权限检查，导致未认证用户可访问受保护资源

---

## Details

### 代码示例

```java
@Configuration
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) {
        http.authorizeHttpRequests(authorize ->
            authorize
                .requestMatchers("/admin").hasRole("ADMIN")
                .requestMatchers("/public/**").permitAll()
                // 缺少 /api/** 的权限检查
        );
    }
}

// 应该明确定义所有路由
authorize
    .requestMatchers("/admin/**").hasRole("ADMIN")
    .requestMatchers("/api/**").authenticated()
    .requestMatchers("/public/**").permitAll()
    .anyRequest().denyAll();  // 默认拒绝
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `authorizeHttpRequests()`, `antMatchers()`
- `hasRole()`, `authenticated()`
- 权限配置缺失的路由

**L2 跳读定位**:
- Spring Security 配置
- SecurityFilterChain 定义

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 所有路由有明确规则
- `anyRequest().denyAll()`

**L3 逐行分析**:
- 每个路由有权限定义
- 没有遗漏的路由

---

## Classify

确认为漏洞: 某些路由无权限检查
误报判定: 所有路由有明确规则
代码异味: 权限规则不完整或顺序错误

---

## Low risk

- 虽无权限检查但资源无敏感数据
- 有其他防护层

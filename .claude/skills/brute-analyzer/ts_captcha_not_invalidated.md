# TypeScript/Node.js 验证码验证后未标记为已用

## 漏洞描述

在 NestJS 认证守卫中进行验证码验证时，即使验证通过，系统未能及时将该验证码标记为已使用或过期，导致相同的验证码可被重复利用，攻击者可通过暴力破解或重放同一验证码绕过认证或账户保护机制。

## Details

### 核心操作定位
查找验证码验证逻辑所在的认证守卫、中间件或控制器方法。目标定位包括：
- NestJS 中 `@UseGuards()`、`canActivate()` 等守卫机制的实现
- 调用验证码校验的数据库查询或缓存操作（如 Redis、in-memory store）
- 验证通过后的业务流程

**审计技巧（L1：关键词扫描）**
- 扫描关键词：`verifyCode()`、`checkCaptcha()`、`validateOTP()`、`guard`、`canActivate`
- 查找验证码验证的入口点，通常在认证控制器或 Guard 中

### 保护机制定位
在验证码验证成功后，系统应立即执行以下操作之一：
- 将验证码从数据库/缓存中删除（DELETE 或 hash 标记）
- 更新验证码状态字段为已使用（`used=true`、`status='used'`）
- 设置验证码过期时间为当前时刻

**审计技巧（L2：跳读）**
- 验证通过后，查看是否存在 `delete()`、`remove()`、`update()` 等操作
- 检查是否调用了 Redis 的 `DEL` 命令或设置了 `EX` 过期时间
- 确认状态修改操作与验证逻辑在**同一事务**内完成（防止并发竞态）

### 代码示例

**易受攻击的代码：**
```typescript
// auth.guard.ts (NestJS Guard)
@Injectable()
export class CaptchaGuard implements CanActivate {
  constructor(private readonly captchaService: CaptchaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const { email, captcha } = request.body;

    // 验证验证码
    const isValid = await this.captchaService.verify(email, captcha);
    if (!isValid) {
      throw new UnauthorizedException('Invalid captcha');
    }

    // ❌ 问题：验证通过后，未标记验证码为已用
    return true;
  }
}

// captcha.service.ts
export class CaptchaService {
  async verify(email: string, code: string): Promise<boolean> {
    const storedCode = await this.cacheManager.get(`captcha:${email}`);
    // 仅验证，未删除或更新状态
    return storedCode === code;
  }
}
```

**问题分析：**
- 验证码验证后未被删除或失效，允许重复使用同一验证码
- 多个请求可同时或顺序使用同一验证码，绕过速率限制和暴力破解防护

## Classify

### 漏洞判断标准

**确认为漏洞的条件：**
1. 验证码验证成功后，未执行任何形式的失效操作（删除、更新状态、设置过期）
2. 系统允许在**同一验证周期内**重复使用相同验证码进行多次认证
3. 验证码失效机制仅依赖服务端时间戳，但未在验证成功时立即清除或标记

**区分误报的要点：**
- 如果验证码带有时间戳验证且时间窗口合理（如 5 分钟内一次性），但未提供重复验证防护，这是漏洞而非误报
- 如果系统依赖**令牌刷新机制**（如验证后下发 JWT），但未明确失效验证码本身，仍需视为漏洞
- 某些场景允许有限重试，但必须有**重试次数限制和时间间隔**，否则判定为漏洞

**代码异味标志：**
- 验证码返回数据库查询结果后，无后续数据修改操作
- 缺少 `DELETE`、`UPDATE`、`remove()` 等操作的日志和注释
- 验证码过期仅由客户端或外部定时任务处理，而非同步失效

## Low risk

### 低风险判定场景

**以下情况评为低风险：**

1. **单一验证、短周期失效**
   - 验证码用于单次验证操作（如登录），且系统在验证后 100ms 内后续业务操作完成
   - 验证码失效时间不超过 30 秒，且有其他防护层（如 IP 限流）

2. **强速率限制 + 有状态跟踪**
   - 系统对同一用户同一验证码的验证请求实施 IP/设备级别的速率限制（如 1 请求/秒）
   - 维护请求计数器，即使验证码未删除，也限制了单验证码的利用次数

3. **验证码绑定多重因素**
   - 验证码需结合**设备指纹、Session ID、Nonce** 等因素，单独重放验证码无效
   - 验证码仅在特定业务流程和上下文中有效

4. **完全隔离的验证域**
   - 验证码仅用于非关键操作（如页面刷新校验、内容加载），不涉及账户、资金、隐私变更
   - 该操作已有其他防护机制（如 CSRF Token、身份验证）

### 升级为高风险的情形

- 验证码用于账户登录、密码重置、支付确认等**关键操作**
- 系统无任何速率限制或并发控制
- 验证码有效期超过 1 小时或不设置过期

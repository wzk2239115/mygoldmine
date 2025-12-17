**Go - 回调逻辑欺骗 (Callback Logic Spoofing)**

第三方回调接口（支付通知、消息推送、webhook）缺乏严格验证，攻击者可伪造回调触发敏感业务逻辑（充值、发货、权限变更）。

---

## Details

**审计等级：L3（逐行读）- 回调处理器需逐行验证签名、幂等、来源**

**快速定位核心操作：**
- 关键词：`/callback`、`/notify`、`/webhook`、`HandleCallback`、`PaymentNotify`
- HTTP 路由注册中带 `callback`、`notify`、`hook` 的端点
- 回调后立即执行的敏感操作：`UpdateBalance`、`UpdateOrder`、`GrantPermission`、`DeductInventory`

**快速定位保护机制：**
- 签名验证：`VerifySign`、`CheckSignature`、`crypto/hmac`、`md5.Sum`、`sha256`
- 幂等控制：`redis.SetNX`、`SELECT...FOR UPDATE`、事务号去重表
- 来源校验：IP 白名单、证书验证、AppID/Secret 配对
- 时间戳防重放：`time.Since(callbackTime) > 5*time.Minute`

**代码示例（漏洞）：**
```go
// 支付回调直接信任 HTTP 参数
func PaymentCallback(c *gin.Context) {
    orderID := c.PostForm("order_id")
    amount := c.PostForm("amount")
    // 缺失签名验证
    db.Exec("UPDATE orders SET paid=1 WHERE id=?", orderID)
    // 缺失幂等控制，可重放充值
    user.Balance += amount
}
```

**审计检查点：**
1. 签名算法是否可预测（硬编码密钥、弱哈希）
2. 验签前是否已执行业务逻辑
3. 是否存在事务号/订单号去重机制
4. 回调参数是否与订单原始数据二次比对（金额、商品）

---

## Classify

**明确漏洞：**
- 无任何签名/密钥验证，直接信任回调参数执行敏感操作
- 签名验证存在但可被绕过（空值豁免、逻辑与或错误）
- 缺乏幂等控制，同一回调可重放触发多次充值/发货

**代码异味：**
- 存在签名验证但使用弱算法（MD5）且密钥复杂度低
- 有幂等表但未在事务中原子检查（先查后插，存在竞态窗口）
- IP 白名单作为唯一防护（CDN/代理场景可伪造）

**误报：**
- 内网专用回调接口（通过 API Gateway 内部调用，不直接暴露）
- 仅处理非敏感通知（日志记录、监控埋点）且无资产操作
- 回调后仅更新中间状态，最终结算需人工审核

---

## Low Risk

- 回调触发的是异步队列任务，消费端有独立验证流程
- 敏感操作需二次确认（如回调仅标记待审核，后台定时任务查询第三方 API 确认）
- 单次回调影响金额受限（如单笔充值上限 $10 且有日频次限制）
- 测试/沙箱环境回调接口（需确认生产环境已修复）
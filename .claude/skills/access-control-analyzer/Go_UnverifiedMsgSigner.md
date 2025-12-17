# 未验证消息签名者（Go - Cosmos SDK）

**漏洞描述：** 消息处理函数未检查 Msg.Signer 是否具有执行权限，导致任意用户可提交特权操作消息，绕过访问控制

## Details

**对应代码示例：**
```go
// msg_server.go - 风险示例
func (ms msgServer) UpdateModuleConfig(goCtx context.Context, msg *types.MsgUpdateModuleConfig) (*types.MsgUpdateModuleConfigResponse, error) {
    ctx := sdk.UnwrapSDKContext(goCtx)
    
    // 直接执行更新，未校验 msg.Authority/Signer 权限
    params := types.Params{
        MaxSupply: msg.MaxSupply,
        MintRate:  msg.MintRate,
    }
    ms.keeper.SetParams(ctx, params)
    
    return &types.MsgUpdateModuleConfigResponse{}, nil
}

// msg_server.go - 正常示例（应包含的校验）
func (ms msgServer) AdminMint(goCtx context.Context, msg *types.MsgAdminMint) (*types.MsgAdminMintResponse, error) {
    ctx := sdk.UnwrapSDKContext(goCtx)
    
    // ✅ 校验 Signer 是否为授权管理员
    if !ms.keeper.IsAdmin(ctx, msg.Signer) {
        return nil, sdkerrors.Wrap(sdkerrors.ErrUnauthorized, "signer is not admin")
    }
    
    // ✅ 或校验 Authority 是否为治理模块地址
    if msg.Authority != ms.keeper.GetAuthority() {
        return nil, govtypes.ErrInvalidSigner.Wrapf("expected %s got %s", ms.keeper.GetAuthority(), msg.Authority)
    }
    
    return ms.keeper.Mint(ctx, msg.Recipient, msg.Amount)
}
```

**快速定位核心操作的技巧（L2:跳读）：**  
- 扫描 `msg_server.go` 中所有 `msgServer` 的方法，重点关注涉及状态修改的操作
- 快速跳到方法体首部，检查是否在调用 Keeper 之前存在权限校验逻辑
- 优先审计包含敏感操作的消息：`Update*`、`Set*`、`Admin*`、`Mint*`、`Burn*`、`Transfer*`、`Grant*`
- 检查 `proto/*/tx.proto` 中消息定义，识别包含 `authority` 或 `signer` 字段的特权消息类型

**快速定位保护机制的技巧（L3:逐行读）：**  
- 在消息处理函数的前 5-10 行内查找权限校验模式：
  - `if msg.Authority != k.GetAuthority()` - 校验治理模块权限
  - `if !k.IsAdmin(ctx, msg.Signer)` - 校验管理员身份
  - `if msg.Signer != expectedAddr` - 校验特定地址
  - `k.authzKeeper.CheckAuthorization()` - 使用 authz 模块授权
- 检查消息定义中 `Signer` 字段的注解：`[(cosmos_proto.scalar) = "cosmos.AddressString"]`
- 确认 `ValidateBasic()` 方法是否包含签名者地址格式校验（非权限校验）
- 搜索 `GetSigners()` 方法的返回值是否被实际使用于权限判断

## Classify

**漏洞判定：**  
- 消息处理函数涉及特权操作（参数修改、资产铸造/销毁、权限授予、合约部署）且完全未校验 `msg.Signer` 或 `msg.Authority` 的身份
- 存在伪校验：仅在 `ValidateBasic()` 中校验地址格式，但未在 `msg_server` 中校验调用者权限
- 权限校验逻辑可被绕过：如仅检查 `msg.Signer != ""` 而不验证是否为授权地址

**误报判定：**  
- 消息处理函数仅执行公开操作（如用户质押、转账自有资产），无需特殊权限即可调用
- 权限校验在 Keeper 方法内部实现：`msg_server` 仅作为路由层，实际校验下沉到 Keeper（需确认 Keeper 校验完整性）
- 消息类型为查询请求（`Query*`），不修改状态

**代码异味判定：**  
- 权限校验逻辑不一致：同一模块中部分消息有校验，部分消息缺失，且无明确业务理由
- 过度依赖外部模块：权限判断完全委托给其他模块（如 authz），但未处理委托调用失败的兜底逻辑
- 注释标注"仅限管理员调用"但代码中无对应权限检查

## Low risk

- **公开功能设计：** 消息本身设计为所有用户可调用，操作仅影响调用者自身状态（如质押自有代币、撤回委托），无越权风险
- **Keeper 层防护：** msg_server 确实未校验，但调用的 Keeper 方法内部包含完整权限验证，且 Keeper 方法未在其他路径暴露
- **治理保护补偿：** 特权消息虽缺少即时校验，但操作需经过链上治理投票或多签确认，且存在紧急暂停机制
- **有限操作范围：** 消息仅修改非敏感配置（如 UI 显示参数、非核心元数据），即使被滥用不影响资产安全或共识稳定性
- **SDK 版本差异：** 旧版本 Cosmos SDK（< v0.46）部分默认消息类型（如 `MsgUpdateParams`）依赖隐式治理校验，升级后风险解除

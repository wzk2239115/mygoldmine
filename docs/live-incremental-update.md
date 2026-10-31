# 实时观察台局部更新（2026-10-30）

运行卡的“运行中”文字改为 Loader2 旋转图标，复用现有 spin 动画，保留 title、aria-label 和 role=status。

删除轮询时重建 iframe 的做法。每 4 秒同步落盘会话后，同源父页面通过 postMessage 通知内层聊天界面调用现有增量 history store。仅接受同源父窗口且 sessionId 匹配的消息。旧消息及组件保持挂载；阅读历史时扩展尾部窗口，避免新消息导致窗口起点移动。内层 ready 握手避免等待第三方字体等资源的 window.load 才注入嵌入样式。

验证：新增同源、来源、会话匹配和清理测试 3 项通过；内嵌前端全套 878 项通过；lint 0 errors（139 warnings）；看板 8 项测试通过。两个前端构建通过，内嵌使用 VITE_IS_PLATFORM=true 和 scripts/ccui/vite.config.ccui.mjs。浏览器系统测试跨 16 秒检查 iframe 元素和 performance.timeOrigin 均保持不变，通过。实际浏览器确认图标 animationName=spin，文字为空，状态标签保留。

完整 typecheck 仍被未修改的 src/modules/sidebar/tests/recentConversationTitleSync.test.ts 中缺少 backgroundSessionIds 的 fixture 阻挡；本轮未修改该测试。详见 mygoldmine-live-typecheck.log。

修改前备份位于 Spark 23 的 /home/wzk/mygoldmine/backups/live-update-20261030T091957Z/source-before.tar.gz。

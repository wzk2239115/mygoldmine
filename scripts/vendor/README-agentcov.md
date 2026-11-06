# 读取记录依赖

来源：https://github.com/trailofbits/agentcov

固定版本：d9b1f7abcfbe9262dc9abab988d6b3bc92dd944a

许可证：Apache-2.0，见 LICENSE-agentcov。

agentcov 目录为该版本 src/agentcov 的原样副本，使用其 Claude 会话适配器和读取范围解析器，不修改上游逻辑。随现有 scripts 只读挂载进入持久沙箱，无须在审计时联网安装。仅阶段二启动器启用采集，其他阶段不新增采集。

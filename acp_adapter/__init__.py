# =============================================================================
# acp_adapter/ - ACP (Agent Communication Protocol) 适配器
# =============================================================================
#
# 本模块实现 ACP（Agent Client Protocol）适配器，允许 Hermes Agent 通过 ACP 协议
# 与外部客户端（如编辑器插件、IDE 集成）通信。
#
# ACP 协议是一种标准化的事件传输协议，支持：
#   - 会话管理（创建、恢复、fork）
#   - 工具调用（远程执行 Hermes 工具）
#   - 消息传递（用户消息、助手消息）
#   - 资源访问（文件系统、工作区等）
#
# 传输方式：
#   - stdio（默认，本地进程通信）
#   - HTTP/WebSocket（远程连接）
#
# 使用方式：
#     python -m acp_adapter
#     hermes acp
#     hermes-acp
# =============================================================================

"""ACP (Agent Communication Protocol) adapter for hermes-agent."""
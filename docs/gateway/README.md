# gateway/ 目录解释

`gateway/` 是 Hermes Agent 的消息网关层，负责连接各种消息平台（Telegram、Discord、Slack、WhatsApp 等）与 Agent 核心。

---

## 目录结构

```
gateway/
├─── __init__.py
├─── run.py                     # 【网关入口】主运行时，平台适配、会话管理
├─── session.py                 # 会话管理
├─── session_context.py         # 会话上下文
├─── config.py                  # 网关配置
├─── authz_mixin.py             # 授权混合类
├─── channel_directory.py       # 频道目录
├─── delivery.py                # 消息投送
├─── status.py                  # 状态管理
├─── stream_consumer.py         # 流消费器
├─── stream_dispatch.py         # 流调度器
├─── stream_events.py           # 流事件
├─── platform_registry.py        # 平台注册表
├─── pairing.py                 # 平台配对
├─── slash_commands.py          # 斜杠命令
├─── display_config.py          # 显示配置
├─── drain_control.py           # 排水控制
├─── hooks.py                   # 钩子系统
├─── builtin_hooks/             # 内置钩子
├─── restart.py                 # 重启控制
├─── restart_loop_guard.py      # 重启循环保护
├─── shutdown_forensics.py      # 关闭取证
├─── scale_to_zero.py           # 零缩放
├─── memory_monitor.py          # 内存监控
├─── kanban_watchers.py         # 看板监控
├─── message_timestamps.py      # 消息时间戳
├─── mirror.py                  # 镜像功能
├─── response_filters.py        # 响应过滤器
├─── runtime_footer.py          # 运行时页脚
├─── sticker_cache.py           # 贴纸缓存
├─── rich_sent_store.py         # 富文本发送存储
├─── whatsapp_identity.py       # WhatsApp 身份
├─── dead_targets.py            # 死亡目标
├─── code_skew.py               # 代码偏移
├─── cgroup_cleanup.py          # cgroup 清理
├─── cwd_placeholder.py         # 工作目录占位符
├─── assets/                    # 静态资源
├─── platforms/                 # 平台适配器
│   ├─── telegram.py
│   ├─── discord.py
│   ├─── slack.py
│   ├─── whatsapp.py
│   ├─── signal.py
│   ├─── matrix.py
│   ├─── webhook.py
│   ├─── api_server.py
│   └─── ... (other platforms)
└─── relay/                     # 中继系统
    ├─── __init__.py
    └─── ...
```

---

## 核心模块说明

### 网关主入口

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `run.py` | 980KB | **网关主入口**，平台适配器管理、会话调度、消息路由 | `run.md` |

### 会话管理

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `session.py` | 94KB | 会话创建、持久化、恢复 | `session.md` |
| `session_context.py` | 15KB | 会话上下文传递 | `session_context.md` |

### 消息投送

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `delivery.py` | 23KB | 消息投送队列，异步发送到平台 | `delivery.md` |
| `stream_consumer.py` | 91KB | 流式消息消费 | `stream_consumer.md` |
| `stream_dispatch.py` | 5KB | 流消息调度 | `stream_dispatch.md` |
| `stream_events.py` | 7KB | 流事件定义 | `stream_events.md` |

### 平台适配器

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `platform_registry.py` | 14KB | 平台适配器注册表 | `platform_registry.md` |
| `platforms/telegram.py` | ~200KB | Telegram Bot 适配 | `platforms/telegram.md` |
| `platforms/discord.py` | ~100KB | Discord Bot 适配 | `platforms/discord.md` |
| `platforms/slack.py` | ~80KB | Slack 适配 | `platforms/slack.md` |
| `platforms/whatsapp.py` | ~100KB | WhatsApp 适配 | `platforms/whatsapp.md` |
| `platforms/signal.py` | ~50KB | Signal 适配 | `platforms/signal.md` |
| `platforms/webhook.py` | ~30KB | Webhook 接口 | `platforms/webhook.md` |
| `platforms/api_server.py` | ~40KB | API 服务器 | `platforms/api_server.md` |

### 命令与配置

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `slash_commands.py` | 220KB | 斜杠命令处理（/help, /model, /tools 等） | `slash_commands.md` |
| `config.py` | 102KB | 网关配置管理 | `config.md` |
| `display_config.py` | 10KB | 显示配置 | `display_config.md` |

### 运维与监控

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `status.py` | 56KB | 状态监控和报告 | `status.md` |
| `memory_monitor.py` | 8KB | 内存监控 | `memory_monitor.md` |
| `kanban_watchers.py` | 65KB | 看板监控 | `kanban_watchers.md` |
| `restart.py` | 1KB | 重启控制 | `restart.md` |
| `restart_loop_guard.py` | 6KB | 重启循环保护 | `restart_loop_guard.md` |
| `shutdown_forensics.py` | 17KB | 关闭取证 | `shutdown_forensics.md` |
| `scale_to_zero.py` | 5KB | 零缩放支持 | `scale_to_zero.md` |

---

## 流程图

### 网关启动

```
gateway/run.py
    │
    ▼
GatewayRunner.start()
    ├─── 加载配置 (config.py)
    ├─── 初始化平台适配器 (platform_registry.py)
    ├─── 启动各平台服务
    │       ├─── Telegram Bot 轮询
    │       ├─── Discord Bot 连接
    │       ├─── Slack 事件监听
    │       └─── ...
    └─── 启动会话过期监控器
```

### 消息处理

```
平台消息收到
    │
    ▼
platforms/<platform>.py
    │
    ▼
构建 Message 对象
    │
    ▼
gateway/run.py
    ├─── 查找或创建 Session (session.py)
    ├─── 获取 AIAgent (缓存或新建)
    ├─── 构建对话历史
    │
    ▼
AIAgent.run_conversation()
    │
    ▼
生成响应
    │
    ▼
消息投送 (delivery.py)
    │
    ▼
平台发送给用户
```

### 缓存机制

网关使用 LRU 缓存管理 AIAgent 实例：

```python
_AGENT_CACHE_MAX_SIZE = 128          # 最多缓存128个Agent
_AGENT_CACHE_IDLE_TTL_SECS = 3600.0  # 1小时未使用过期
```

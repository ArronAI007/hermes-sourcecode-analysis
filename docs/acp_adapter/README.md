# acp_adapter/ 目录解释

`acp_adapter/` 是 Hermes Agent 的 ACP（Agent Client Protocol）协议适配器，允许 Hermes 通过标准化协议与外部客户端通信。

---

## 目录结构

```
acp_adapter/
├─── __init__.py              # 包初始化
├─── __main__.py               # 入口点
├─── entry.py                   # CLI 入口点
├─── server.py                  # ACP Agent 服务器
├─── session.py                 # 会话管理器
├─── tools.py                   # 工具调用辅助
├─── auth.py                    # 认证辅助
├─── events.py                  # 事件回调工厂
├─── permissions.py             # 权限桥接
├─── edit_approval.py           # 编辑审批辅助
└─── provenance.py              # 会话溯源
```

---

## 核心模块说明

### 协议层

| 文件 | 职责 |
|------|------|
| `server.py` | ACP Agent 服务器，实现 JSON-RPC 2.0 协议处理 |
| `entry.py` | CLI 入口点，配置日志和环境变量 |

### 会话管理

| 文件 | 职责 |
|------|------|
| `session.py` | ACP 会话映射到 Hermes AIAgent，持久化到 SessionDB |
| `provenance.py` | 会话溯源元数据推导 |

### 工具桥接

| 文件 | 职责 |
|------|------|
| `tools.py` | Hermes 工具到 ACP ToolKind 的映射表（TOOL_KIND_MAP） |
| `events.py` | AIAgent 事件到 ACP 通知的桥接 |
| `permissions.py` | 权限选项转换（allow_once/session/always） |
| `edit_approval.py` | 编辑审批请求的上下文隔离 |

### 认证

| 文件 | 职责 |
|------|------|
| `auth.py` | 检测和广告 Hermes 认证方法 |

---

## ACP 协议工具映射

```python
TOOL_KIND_MAP = {
    "read_file": "read",
    "write_file": "edit",
    "terminal": "execute",
    "browser_navigate": "fetch",
    "delegate_task": "execute",
    ...
}
```

---

## 调用关系

```
hermes acp
    │
    ▼
entry.py:main()
    │
    ▼
server.py:ACPServer
    │
    ├───→ session.py      # 会话管理
    ├───→ tools.py       # 工具映射
    ├───→ events.py      # 事件桥接
    ├───→ auth.py        # 认证
    └───→ permissions.py   # 权限
```

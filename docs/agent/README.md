# agent/ 目录解释

`agent/` 是 Hermes Agent 的核心逻辑层，包含对话循环、记忆管理、学习系统、错误处理、多模型适配等关键模块。

---

## 目录结构

```
agent/
├─── __init__.py                    # 包装导出，jiter 预加载
├─── jiter_preload.py               # jiter 库预加载优化
├─── agent_init.py                  # Agent 初始化流程
├─── agent_runtime_helpers.py       # 运行时辅助函数
├─── conversation_loop.py           # 【核心对话循环】
├─── chat_completion_helpers.py     # LLM API 调用封装
├─── context_compressor.py          # 上下文压缩
├─── context_engine.py              # 上下文引擎
├─── context_references.py          # 上下文引用管理
├─── conversation_compression.py    # 对话压缩
├─── memory_manager.py              # 记忆管理器
├─── curator.py                     # 【学习系统】
├─── learn_prompt.py                # 学习提示
├─── learning_graph.py              # 学习图谱
├─── learning_graph_render.py       # 学习图渲染
├─── learning_mutations.py          # 学习变异操作
├─── error_classifier.py            # 错误分类器
├─── redact.py                      # 敏感信息脱敏
├─── display.py                     # 终端显示格式化
├─── insights.py                    # 洞察分析
├─── iteration_budget.py            # 迭代次数预算
├─── usage_pricing.py               # Token 用量和定价
├─── i18n.py                        # 国际化
├─── file_safety.py                 # 文件安全检查
├─── coding_context.py              # 编码上下文
├─── codex_runtime.py               # Codex 运行时
├─── codex_responses_adapter.py     # Codex 响应适配
├─── system_prompt.py               # 系统提示
├─── process_bootstrap.py           # 进程引导
├─── credential_pool.py             # 凭证池
├─── credential_sources.py          # 凭证来源
├─── credential_persistence.py      # 凭证持久化
├─── credits_tracker.py             # 配额跟踪
├─── billing_view.py                # 计费视图
├─── account_usage.py               # 账户用量
├─── auxiliary_client.py            # 辅助 LLM 客户端
├─── background_review.py           # 后台审查
├─── browser_provider.py            # 浏览器提供者
├─── browser_registry.py            # 浏览器注册表
├─── image_gen_provider.py          # 图像生成提供者
├─── image_gen_registry.py          # 图像生成注册表
├─── image_routing.py               # 图像路由
├─── copilot_acp_client.py          # Copilot ACP 客户端
├─── curator_backup.py              # 学习备份
├─── display.py                     # 显示格式化
└─── ... (其他文件)
```

---

## 核心模块说明

### 对话系统

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `conversation_loop.py` | 298KB | **对话主循环**，处理流式响应、工具调用、错误恢复 | `conversation_loop.md` |
| `chat_completion_helpers.py` | 149KB | LLM API 调用封装，支持多提供商 | `chat_completion_helpers.md` |
| `context_compressor.py` | 149KB | 上下文压缩，超长对话自动摘要 | `context_compressor.md` |
| `context_engine.py` | 9KB | 上下文引擎，管理会话上下文 | `context_engine.md` |
| `context_references.py` | 21KB | 上下文引用跟踪 | `context_references.md` |
| `conversation_compression.py` | 63KB | 对话压缩算法 | `conversation_compression.md` |
| `system_prompt.py` | ~50KB | 系统提示模板管理 | `system_prompt.md` |

### 记忆与学习

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `memory_manager.py` | ~100KB | 记忆管理，跨会话搜索（FTS5全文搜索） | `memory_manager.md` |
| `curator.py` | 85KB | **自我学习系统**，技能创建、改进 | `curator.md` |
| `learn_prompt.py` | 8KB | 学习提示生成 | `learn_prompt.md` |
| `learning_graph.py` | 11KB | 学习图谱数据结构 | `learning_graph.md` |
| `learning_graph_render.py` | 25KB | 学习图渲染器 | `learning_graph_render.md` |
| `learning_mutations.py` | 8KB | 学习变异操作 | `learning_mutations.md` |

### 错误处理

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `error_classifier.py` | 65KB | 错误分类，决定故障转移策略 | `error_classifier.md` |
| `redact.py` | ~20KB | 敏感信息脱敏处理 | `redact.md` |
| `file_safety.py` | 27KB | 文件操作安全检查 | `file_safety.md` |

### 模型适配器

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `anthropic_adapter.py` | 120KB | Anthropic Claude API 适配 | `anthropic_adapter.md` |
| `bedrock_adapter.py` | 53KB | AWS Bedrock 适配 | `bedrock_adapter.md` |
| `gemini_native_adapter.py` | 37KB | Google Gemini API 适配 | `gemini_native_adapter.md` |
| `azure_identity_adapter.py` | 23KB | Azure 认证适配 | `azure_identity_adapter.md` |
| `codex_responses_adapter.py` | 61KB | OpenAI Codex 响应适配 | `codex_responses_adapter.md` |
| `codex_runtime.py` | 35KB | Codex 运行时 | `codex_runtime.md` |
| `gemini_schema.py` | 3KB | Gemini Schema 转换 | `gemini_schema.md` |

### 计费与配额

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `usage_pricing.py` | ~30KB | Token 用量统计和费用估算 | `usage_pricing.md` |
| `credits_tracker.py` | 28KB | 配额余额跟踪 | `credits_tracker.md` |
| `account_usage.py` | 25KB | 账户用量查询 | `account_usage.md` |
| `billing_view.py` | 11KB | 计费视图渲染 | `billing_view.md` |

### 凭证管理

| 文件 | 大小 | 职责 | 文档 |
|------|------|------|------|
| `credential_pool.py` | 109KB | 凭证池管理 | `credential_pool.md` |
| `credential_sources.py` | 19KB | 凭证来源 | `credential_sources.md` |
| `credential_persistence.py` | 5KB | 凭证持久化 | `credential_persistence.md` |

---

## 调用关系

```
run_agent.py:AIAgent
    │
    ├───→ agent_init.py
    │       ├─── 初始化配置
    │       ├─── 加载认证
    │       └─── 加载工具集
    │
    ├───→ conversation_loop.py
    │       ├─── 构建消息历史
    │       ├─── → chat_completion_helpers.py
    │       │       ├─── → anthropic_adapter.py
    │       │       ├─── → bedrock_adapter.py
    │       │       └─── → gemini_native_adapter.py
    │       ├─── 处理流式响应
    │       ├─── 解析工具调用
    │       ├─── → model_tools.py
    │       │       └─── → tools/<tool>.py
    │       ├─── 工具结果处理
    │       ├─── → context_compressor.py (必要时)
    │       └─── → memory_manager.py (记忆检索)
    │
    ├───→ error_classifier.py (错误时)
    └───→ curator.py (学习循环)
```

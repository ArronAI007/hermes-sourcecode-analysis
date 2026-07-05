# Hermes Agent 核心对话循环（conversation_loop.py）

> 文件路径：`/Users/arron/Desktop/ArronAI/hermes-sourcecode-analysis/agent/conversation_loop.py`
>
> 规模：~298KB，约 5,246 行
>
> 地位：从 `run_agent.AIAgent` 中提取的最大单一模块，驱动一次用户交互的完整生命周期

---

## 一、架构概述

```
┌─────────────────────────────────────────────────────────────────────┐
│                     核心对话循环架构（单轮对话）                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────┐     ┌──────────────┐     ┌─────────────────────┐    │
│   │ 用户输入  │────▶│  上下文构建   │────▶│   API 调用（LLM）    │    │
│   └──────────┘     └──────────────┘     └─────────────────────┘    │
│                                                  │                  │
│                                                  ▼                  │
│   ┌──────────┐     ┌──────────────┐     ┌─────────────────────┐    │
│   │ 最终结果  │◀────│  循环调度器   │◀────│   响应处理与分发     │    │
│   └──────────┘     └──────────────┘     └─────────────────────┘    │
│                          ▲                         │                │
│                          │                         ▼                │
│                          │            ┌─────────────────────┐       │
│                          └────────────│  工具调用执行        │       │
│                                       └─────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.1 职责定位

`conversation_loop.py` 是 **Hermes Agent 的心脏**。它负责：

- **驱动一轮完整对话**：从接收用户消息到返回最终答复
- **编排模型调用**：处理重试、回退、压缩、中断
- **分发工具调用**：解析模型输出的 `tool_calls`，调用相应函数，并将结果重新注入上下文
- **流式响应处理**：实时消费模型流式输出，支持 TTS 等下游管线
- **错误恢复**：面对各种 API 错误（速率限制、上下文溢出、认证失败、内容策略拒绝）进行分类和恢复
- **状态管理**：维护迭代预算、压缩状态、回退链、会话持久化

---

## 二、主要组件与函数详解

### 2.1 辅助函数（文件顶部 ~520 行）

#### `_image_error_max_dimension(error)`

从提供商返回的错误信息中提取图片尺寸上限。用于当图片过大被拒时，自动缩小图片后重试。

```python
def _image_error_max_dimension(error: Exception) -> Optional[int]:
    """Extract a provider-reported image dimension ceiling, if present."""
    # 从 error.message / error.body 中匹配 "max allowed size: 2048 pixels"
    match = re.search(r"max allowed size(?:\s+for [^:]+)?:\s*(\d{3,5})\s*pixels?", text)
```

**职责**：从错误文本中提取 `max allowed size`，返回 `512~8000` 范围内的像素值。

#### `_ollama_context_limit_error(agent, request_tokens)`

检测 Ollama 运行时上下文是否过小（< `MINIMUM_CONTEXT_LENGTH`），并生成用户友好的错误信息。

```python
def _ollama_context_limit_error(agent: Any, request_tokens: int) -> Optional[str]:
    """Return a user-facing error when Ollama is loaded with too little context."""
    if runtime_ctx >= MINIMUM_CONTEXT_LENGTH:
        return None
    # 返回提示：建议设置 model.ollama_num_ctx: 65536
```

**职责**：保护 Ollama 用户，防止因上下文窗口过小导致工具调用反复失败。

#### `_restore_or_build_system_prompt(agent, system_message, conversation_history)`

从会话数据库中恢复缓存的系统提示词，或在首次运行时重建。

```python
def _restore_or_build_system_prompt(agent, system_message, conversation_history):
    """Restore the cached system prompt from the session DB or build it fresh."""
    stored_prompt = None
    stored_state = "missing"  # missing / null / empty / present / stale_runtime
```

**四态区分**：

| 状态      | 含义                                                                 |
|-----------|----------------------------------------------------------------------|
| `missing` | 无会话行 — 合法首回合                                                    |
| `null`    | 会话行存在但 `system_prompt` 为 NULL — 旧版迁移残留                       |
| `empty`   | 会话行存在但 `system_prompt` 为空字符串 — 静默持久化 Bug                   |
| `present` | 存在可用提示词 — 逐字复用以维持前缀缓存命中                                  |

**职责**：确保系统提示词在跨轮次间**字节级稳定**，从而维持 Anthropic 的 prompt prefix cache 命中。

#### `_stored_prompt_matches_runtime(agent, prompt)`

检查持久化的系统提示词中的 `Model:` / `Provider:` 行是否与当前运行时一致，不一致则重建。

#### `_get_continuation_prompt(is_partial_stub, dropped_tools)`

生成当模型响应被截断时，继续生成的系统提示词：

```python
def _get_continuation_prompt(is_partial_stub: bool, dropped_tools: Optional[List[str]] = None) -> str:
    if is_partial_stub and dropped_tools:
        return "[System: Your previous tool call (...) was too large and the stream timed out ...]"
    elif is_partial_stub:
        return "[System: The previous response was cut off by a network error mid-stream ...]"
    else:
        return "[System: Your previous response was truncated by the output length limit ...]"
```

#### `_sync_failover_system_message(agent, api_messages, active_system_prompt)`

在提供商故障转移后，同步更新 `api_messages` 中的系统提示词身份行（`Model:` / `Provider:`），防止回退后仍报告旧提供商。

---

### 2.2 核心函数：`run_conversation()`

这是整个文件的**主干函数**，约 3,900 行，驱动一次完整用户交互。

#### 函数签名

```python
def run_conversation(
    agent,
    user_message: str,
    system_message: str = None,
    conversation_history: List[Dict[str, Any]] = None,
    task_id: str = None,
    stream_callback: Optional[callable] = None,
    persist_user_message: Optional[str] = None,
    persist_user_timestamp: Optional[float] = None,
    moa_config: Optional[dict[str, Any]] = None,
) -> Dict[str, Any]:
```

#### 返回值

```python
{
    "final_response": str,           # 最终用户可见的文本
    "messages": List[Dict],          # 完整的对话消息列表
    "api_calls": int,                # 本次轮次消耗的 API 调用次数
    "completed": bool,               # 是否成功完成
    "failed": bool,                  # 是否标记为失败
    "interrupted": bool,             # 是否被用户中断
    "partial": bool,                 # 是否返回部分结果（截断/不完整）
    "error": Optional[str],          # 错误详情
}
```

---

#### 阶段一：回合前准备（Prologue）

```python
# ── Per-turn setup (the prologue) ──
_ctx = build_turn_context(
    agent, user_message, system_message, conversation_history,
    task_id, stream_callback, persist_user_message, persist_user_timestamp,
    # ... 多个辅助函数引用
)
```

`build_turn_context`（来自 `agent/turn_context.py`）负责：

1. **stdio 守护**：安装安全标准输入输出包装，防止工具执行破坏终端
2. **重试计数器重置**：清空 `empty_content_retries`、`thinking_prefill_retries`
3. **用户消息清洗**：去除代理字符（surrogate）、非法字符
4. **todo/nudge 注入**：根据内存管理器决定是否需要记忆回顾
5. **系统提示词恢复/重建**：调用 `_restore_or_build_system_prompt`
6. **会话持久化准备**：初始化崩溃恢复检查点
7. **预压缩检查**：如果上下文已接近阈值，提前压缩
8. **`pre_llm_call` 插件钩子**：允许插件注入额外上下文
9. **外部记忆预取**：异步拉取相关记忆片段，缓存到 `_ext_prefetch_cache`

---

#### 阶段二：主循环（The Loop）

```python
while (api_call_count < agent.max_iterations
       and agent.iteration_budget.remaining > 0) or agent._budget_grace_call:
```

循环条件解读：
- 调用次数未达 `max_iterations`
- 迭代预算仍有剩余
- **或**：有"宽限调用"（`budget_grace_call`）—— 预算已耗尽但再给最后一次机会

**每轮迭代内部流程**：

```
1. 检查中断请求（用户发送新消息）
2. 消费迭代预算（或消耗宽限标志）
3. 触发 step_callback（网关钩子：agent:step 事件）
4. 处理 /steer 指令 drain
5. 构建 api_messages（API 调用用的消息副本）
    - 注入预取记忆到当前用户消息
    - 复制 reasoning_content 到 API 消息
    - 清理内部字段（finish_reason, _thinking_prefill 等）
    - 注入 MoA 聚合上下文
    - 注入 prefill 消息
    - 应用 Anthropic prompt caching
    - 清洗孤儿工具结果
    - 丢弃纯推理助手回合
    - 规范化工具调用 JSON
    - 去除代理字符
6. 估算请求 token 数，检查 Ollama 上下文限制
7. 预 API 压缩检查（如果接近阈值）
8. 发起 API 调用（含重试/回退/流式处理）
9. 响应后处理：
    - 验证响应形状
    - 检查 finish_reason（stop / length / content_filter / incomplete / tool_calls）
    - 处理截断（continuation prompt）
    - 处理内容策略拒绝
    - 处理工具调用
    - 处理空响应 / 纯推理响应
    - 处理最终文本响应
```

---

### 2.3 API 调用与重试机制

#### 重试循环

```python
while retry_count < max_retries:
    try:
        # 1. Nous Portal 速率限制守卫
        if agent.provider == "nous":
            # 检查是否已有其他会话记录了 Nous 的速率限制
            ...

        # 2. 重置流式传输跟踪
        agent._reset_stream_delivery_tracking()

        # 3. 针对当前提供商重新应用 reasoning echo
        agent._reapply_reasoning_echo_for_provider(api_messages)

        # 4. 构建 API 调用参数
        api_kwargs = agent._build_api_kwargs(api_messages)

        # 5. 应用 LLM 请求中间件
        _llm_request_mw = apply_llm_request_middleware(api_kwargs, ...)

        # 6. 触发 pre_api_request 插件钩子
        if has_hook("pre_api_request"):
            _invoke_hook("pre_api_request", ...)

        # 7. 优先使用流式路径（即使没有消费者）
        def _perform_api_call(next_api_kwargs):
            if _use_streaming:
                return agent._interruptible_streaming_api_call(
                    next_api_kwargs, on_first_delta=_stop_spinner
                )
            return agent._interruptible_api_call(next_api_kwargs)

        # 8. 执行 API 调用（通过中间件包装）
        response = run_llm_execution_middleware(api_kwargs, _perform_api_call, ...)

        # 9. 验证响应形状
        if not _transport.validate_response(response):
            response_invalid = True
            ...

        # 10. 检查 finish_reason
        finish_reason = _transport.normalize_response(response).finish_reason

        # 11. 处理内容策略拒绝
        if finish_reason == "content_filter":
            ...

        # 12. 处理输出长度截断
        if finish_reason == "length":
            ...

        break  # 成功，退出重试循环

    except InterruptedError:
        # 用户中断
        interrupted = True
        break

    except Exception as api_error:
        # 错误分类与恢复
        classified = classify_api_error(api_error, ...)
        # ... 详见下方错误处理章节
```

---

### 2.4 流式响应处理

#### 为什么优先使用流式

```python
# Always prefer the streaming path — even without stream consumers.
# Streaming gives us fine-grained health checking (90s stale-stream
# detection, 60s read timeout) that the non-streaming path lacks.
```

即使没有任何流消费者（TTS、UI 显示），流式路径也提供：

- **90 秒陈旧流检测**：如果模型卡住不输出 token，自动断开
- **60 秒读取超时**：防止连接无限挂起
- **细粒度健康检查**：通过 `on_first_delta` 回调检测首个 token 到达时间

#### 流式调用封装

```python
def _perform_api_call(next_api_kwargs):
    if _use_streaming:
        return agent._interruptible_streaming_api_call(
            next_api_kwargs, on_first_delta=_stop_spinner
        )
    return agent._interruptible_api_call(next_api_kwargs)
```

- `_interruptible_streaming_api_call`：来自 `run_agent.py`，包装为可中断的流式调用
- `on_first_delta`：当首个 token 到达时停止思考 spinner

#### 流式消费者检测

```python
elif not agent._has_stream_consumers():
    # No display/TTS consumer. Still prefer streaming for health checking,
    # but skip for Mock clients in tests (mocks return SimpleNamespace,
    # not stream iterators).
    from unittest.mock import Mock
    if isinstance(getattr(agent, "client", None), Mock):
        _use_streaming = False
```

流消费者包括：
- `stream_callback`（TTS 管线）
- `stream_delta_callback`（UI 增量显示）
- `thinking_callback`（思考状态显示）

---

## 三、工具调用处理流程

### 3.1 检测与验证

当 `assistant_message.tool_calls` 存在时：

```python
if assistant_message.tool_calls:
    # 1. 自动修复工具名拼写错误
    for tc in assistant_message.tool_calls:
        if tc.function.name not in agent.valid_tool_names:
            repaired = agent._repair_tool_call(tc.function.name)
            if repaired:
                tc.function.name = repaired

    # 2. 检查无效工具名（模型幻觉）
    invalid_tool_calls = [...]
    if invalid_tool_calls:
        # 最多重试 3 次，超过则返回错误
        if agent._invalid_tool_retries >= 3:
            return {...}
        # 否则注入工具错误结果，让模型在下一轮自纠正
        ...

    # 3. 验证 JSON 参数
    invalid_json_args = [...]
    if invalid_json_args:
        # 检测截断 vs 格式错误
        if _truncated:
            return {"error": "Response truncated due to output length limit"}
        # 最多重试 3 次
        if agent._invalid_json_retries < 3:
            continue
        else:
            # 注入恢复性工具结果
            ...
```

### 3.2 去重与限幅

```python
# 限制委派任务调用次数（防止递归爆炸）
assistant_message.tool_calls = agent._cap_delegate_task_calls(
    assistant_message.tool_calls
)
# 去重同一回合内的重复工具调用
assistant_message.tool_calls = agent._deduplicate_tool_calls(
    assistant_message.tool_calls
)
```

### 3.3 执行与后处理

```python
# 追加助手消息（含工具调用）到消息历史
messages.append(assistant_msg)

# 在工具执行前增量持久化
agent._flush_messages_to_session_db(messages, conversation_history)

# 关闭流式显示（防止工具输出包裹在响应框内）
if agent.stream_delta_callback:
    agent.stream_delta_callback(None)

# 执行工具调用
agent._execute_tool_calls(assistant_message, messages, effective_task_id, api_call_count)

# 检查工具护栏停止决策
if agent._tool_guardrail_halt_decision is not None:
    decision = agent._tool_guardrail_halt_decision
    final_response = agent._toolguard_controlled_halt_response(decision)
    break

# 重置截断重试计数器
truncated_tool_call_retries = 0

# 如果是纯 execute_code 调用，退还迭代预算
_tc_names = {tc.function.name for tc in assistant_message.tool_calls}
if _tc_names == {"execute_code"}:
    agent.iteration_budget.refund()
```

### 3.4 工具调用后压缩检查

```python
if agent.compression_enabled and _compressor.should_compress(_real_tokens):
    messages, active_system_prompt = agent._compress_context(
        messages, system_message, approx_tokens=..., task_id=effective_task_id
    )
    conversation_history = conversation_history_after_compression(agent, messages)
```

---

## 四、错误处理与故障转移机制

### 4.1 错误分类体系

所有 API 错误首先通过 `classify_api_error()`（来自 `agent/error_classifier.py`）进行分类：

```python
classified = classify_api_error(
    api_error,
    provider=getattr(agent, "provider", "") or "",
    model=getattr(agent, "model", "") or "",
    approx_tokens=approx_tokens,
    context_length=_ctx_len,
    num_messages=len(api_messages) if api_messages else 0,
)
```

返回的 `classified` 包含：

| 字段                 | 含义                                          |
|----------------------|-----------------------------------------------|
| `reason`             | 失败原因枚举（FailoverReason）                 |
| `status_code`        | HTTP 状态码                                   |
| `retryable`          | 是否可重试                                    |
| `should_compress`    | 是否应触发上下文压缩                          |
| `should_fallback`    | 是否应触发故障转移                            |
| `should_rotate_credential` | 是否应轮换凭证池                        |
| `is_auth`            | 是否为认证错误                                |

### 4.2 恢复路径优先级

当发生错误时，按以下优先级尝试恢复：

```
1. UnicodeEncodeError（代理字符/ASCII 编码问题）
   └─> 清洗消息并重试（最多 2 次）

2. 图片被拒（image_too_large / multimodal_tool_content_unsupported）
   └─> 缩小图片 / 降级工具内容为纯文本

3. Nous 付费权益刷新（billing + Nous Portal）
   └─> 刷新 OAuth 令牌并重试

4. 凭证池轮换（credential pool rotation）
   └─> 使用备选 API Key / OAuth 令牌

5. 认证失败 + 故障转移链（401/403 + fallback chain）
   └─> 切换到下一个提供商

6. 速率限制 / 计费耗尽（429 / 402）
   └─>  eagerly fallback（立即切换提供商）
   └─>  如果没有备选：指数退避等待

7. 上下文溢出（context_overflow）
   └─> 区分 "prompt too long" vs "max_tokens too large"
   └─> 压缩历史 或 降低输出 token 上限

8. Payload 过大（413）
   └─> 压缩历史（最多 3 次）

9. 内容策略拒绝（content_policy_blocked）
   └─> 尝试一次 fallback，否则终止

10. 非重试客户端错误（4xx 非 429/413）
    └─> 尝试 fallback，否则终止

11. 最大重试耗尽
    └─> 尝试主传输恢复（重建连接池）
    └─> 尝试 fallback
    └─> 终止并返回错误摘要
```

### 4.3 故障转移（Fallback）机制

```python
if agent._try_activate_fallback(reason=classified.reason):
    # 同步系统提示词中的 Model/Provider 身份
    active_system_prompt = _sync_failover_system_message(
        agent, api_messages, active_system_prompt
    )
    retry_count = 0
    compression_attempts = 0
    _retry.primary_recovery_attempted = False
    continue  # 使用新提供商重新开始
```

**关键设计**：
- `_fallback_index` 跟踪当前在故障转移链中的位置
- 每次 `try_activate_fallback()` 成功会递增索引
- 故障转移后**重置重试计数器**，给新提供商公平的尝试次数
- 系统提示词通过 `_sync_failover_system_message` 同步更新，确保后续调用报告正确身份

### 4.4 压缩恢复路径

```python
if classified.reason == FailoverReason.context_overflow:
    compression_attempts += 1
    if compression_attempts > max_compression_attempts:
        # 终止
        ...
    messages, active_system_prompt = agent._compress_context(
        messages, system_message, approx_tokens=approx_tokens, task_id=effective_task_id
    )
    conversation_history = conversation_history_after_compression(agent, messages)
    _retry.restart_with_compressed_messages = True
    break  # 回到外层循环，使用压缩后的消息重新调用
```

---

## 五、特殊场景处理

### 5.1 输出截断（finish_reason="length"）

```python
if finish_reason == "length":
    # 1. 检测是否是纯推理耗尽（thinking budget exhausted）
    if _thinking_exhausted:
        return {"error": "Model used all output tokens on reasoning..."}

    # 2. 检测内容过滤器导致的流中断
    if _cf_terminated and agent._fallback_index < len(agent._fallback_chain):
        # 激活 fallback，回滚部分响应
        ...

    # 3. 纯文本截断：追加部分响应 + continuation prompt，重试最多 4 次
    if not _trunc_has_tool_calls:
        length_continue_retries += 1
        if length_continue_retries < 4:
            messages.append(interim_msg)
            truncated_response_parts.append(assistant_message.content)
            messages.append({"role": "user", "content": _get_continuation_prompt(...)})
            continue

    # 4. 工具调用截断：增加 max_tokens 并重试最多 4 次
    if _trunc_has_tool_calls:
        truncated_tool_call_retries += 1
        agent._ephemeral_max_output_tokens = min(_tc_boost, _tc_boost_cap)
        continue
```

### 5.2 空响应处理

当模型返回空内容（无文本、无工具调用）时：

```python
if not agent._has_content_after_think_block(final_response):
    # 1. 优先：使用已流式传输的部分内容
    if agent._has_content_after_think_block(_partial_streamed):
        final_response = _recovered
        break

    # 2. 优先：使用上一轮工具调用时的内容（如果是纯家务工具）
    fallback = agent._last_content_with_tools
    if fallback and agent._last_content_tools_all_housekeeping:
        final_response = fallback
        break

    # 3. 后工具空响应 nudge（模型执行工具后沉默）
    if _prior_was_tool and not agent._post_tool_empty_retried:
        messages.append({"role": "assistant", "content": "(empty)"})
        messages.append({"role": "user", "content": "You just executed tool calls but returned an empty response..."})
        continue

    # 4. 纯推理预填充（模型只产出 reasoning，无可见文本）
    if _has_structured and agent._thinking_prefill_retries < 2:
        messages.append(interim_msg)  # 带有 _thinking_prefill 标志
        continue

    # 5. 空响应重试（最多 3 次）
    if agent._empty_content_retries < 3:
        agent._empty_content_retries += 1
        continue

    # 6. 尝试 fallback 提供商
    if agent._fallback_chain and agent._try_activate_fallback():
        continue

    # 7. 终止，返回 "(empty)"
    final_response = "(empty)"
    break
```

### 5.3 中断处理

```python
if agent._interrupt_requested:
    interrupted = True
    _turn_exit_reason = "interrupted_by_user"
    break
```

**流式中断**：
```python
except InterruptedError:
    # 保留已流式传输给用户的文本
    _partial = agent._strip_think_blocks(
        getattr(agent, "_current_streamed_assistant_text", "") or ""
    ).strip()
    if _partial:
        messages.append({"role": "assistant", "content": _partial})
        final_response = _partial
    else:
        final_response = f"{INTERRUPT_WAITING_FOR_MODEL_PREFIX}{api_elapsed:.1f}s elapsed)."
```

---

## 六、调用流程图

### 6.1 完整单轮对话流程

```
                        ┌─────────────────┐
                        │   用户发送消息   │
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  build_turn_context
                        │  （回合前准备）   │
                        └────────┬────────┘
                                 ▼
            ┌────────────────────────────────────────┐
            │         主循环：while 条件满足          │
            └────────┬───────────────────────────────┘
                     ▼
            ┌─────────────────┐
            │  检查中断请求    │
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │  消费迭代预算    │
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │  构建 api_messages
            │  （API 调用副本）│
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │  估算 token 压力 │
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │  预 API 压缩检查 │
            └────────┬────────┘
                     ▼
            ┌─────────────────────────┐
            │   API 调用 + 重试循环    │
            │  （最多 max_retries 次） │
            └────────┬────────────────┘
                     ▼
         ┌───────────────────────────┐
         │      响应形状验证          │
         │  validate_response()      │
         └───────────┬───────────────┘
                     ▼
         ┌───────────────────────────┐
         │    finish_reason 检查      │
         │  stop / length / content_  │
         │  filter / incomplete /     │
         │  tool_calls                │
         └───────────┬───────────────┘
                     ▼
    ┌──────────────────────────────────────────────┐
    │              分支处理                          │
    ├──────────────────┬───────────────────────────┤
    ▼                  ▼                           ▼
┌──────────┐   ┌──────────────┐          ┌────────────────┐
│ content_ │   │   length     │          │  tool_calls    │
│ _filter  │   │  （截断）     │          │  （工具调用）   │
└────┬─────┘   └──────┬───────┘          └───────┬────────┘
     │                │                          │
     ▼                ▼                          ▼
┌──────────┐   ┌──────────────┐          ┌────────────────┐
│尝试一次   │   │ continuation │          │ 验证工具名+JSON │
│fallback  │   │ prompt /     │          │ 去重+限幅      │
│或终止     │   │ fallback     │          │                │
└──────────┘   └──────────────┘          └───────┬────────┘
                                                  │
                                                  ▼
                                         ┌────────────────┐
                                         │ _execute_tool_ │
                                         │ _calls()       │
                                         └───────┬────────┘
                                                 │
                                                 ▼
                                         ┌────────────────┐
                                         │  工具结果注入   │
                                         │  messages      │
                                         └───────┬────────┘
                                                 │
                                                 ▼
                                         ┌────────────────┐
                                         │  压缩检查       │
                                         │  （如果阈值达） │
                                         └───────┬────────┘
                                                 │
                                                 ▼
                                         ┌────────────────┐
                                         │    continue    │
                                         │  （回到循环顶部）│
                                         └────────────────┘

                     ▼
            ┌─────────────────┐
            │   stop（最终文本）│
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │  去除 think 块   │
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │ 验证停止门检查   │
            │ （verify_on_stop）│
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │  finalize_turn   │
            │  （回合收尾）     │
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │   返回结果字典   │
            └─────────────────┘
```

### 6.2 API 错误恢复流程

```
┌─────────────────┐
│   API 调用异常   │
└────────┬────────┘
         ▼
┌─────────────────────────────┐
│ classify_api_error()        │
│ 错误分类                     │
└────────┬────────────────────┘
         ▼
┌──────────────────────────────────────────────┐
│               按分类路由                        │
├─────────────┬─────────────┬──────────────────┤
▶             ▶             ▶                  ▶
│             │             │                  │
▼             ▼             ▼                  ▼
Unicode     Image         Auth/Billing      Context
Encode      Rejection     /Rate Limit       Overflow
Error       Recovery      Recovery          Recovery
│             │             │                  │
▼             ▼             ▼                  ▼
清洗消息    缩小图片       凭证池轮换        压缩历史
重试 2 次   降级文本       Fallback 切换    或降低 max_tokens
            重试 1 次      或指数退避        重试 3 次
                              │                  │
                              ▼                  ▼
                        ┌──────────────────────────┐
                        │    max_retries 耗尽？      │
                        │    fallback 链耗尽？       │
                        └───────────┬──────────────┘
                                    │
                        ┌───────────┴───────────┐
                        ▼                       ▼
                   成功恢复（continue）     终止返回错误
```

---

## 七、各部分职责总结

| 组件/函数                          | 职责                                                              |
|------------------------------------|-------------------------------------------------------------------|
| `_image_error_max_dimension`       | 从错误文本中提取图片尺寸上限，用于自动缩小图片                     |
| `_ollama_context_limit_error`      | 检测 Ollama 上下文过小，返回用户友好的配置建议                      |
| `_restore_or_build_system_prompt`  | 从会话数据库恢复系统提示词，或首次构建并持久化；维护前缀缓存稳定性   |
| `_stored_prompt_matches_runtime`   | 验证持久化提示词的 Model/Provider 是否与当前运行时一致               |
| `_get_continuation_prompt`         | 生成截断/流中断后的 continuation prompt                            |
| `_sync_failover_system_message`    | 故障转移后同步更新 api_messages 中的系统提示词身份                   |
| `_content_policy_blocked_result`   | 构建内容策略拒绝的统一返回格式                                      |
| `run_conversation`                 | **核心驱动函数**：管理整轮对话的主循环、API 调用、工具分发、错误恢复 |
| `build_turn_context`               | 回合前准备：stdio 守护、消息清洗、系统提示恢复、预压缩、插件钩子      |
| `classify_api_error`               | 对 API 错误进行结构化分类，指导后续恢复路径                          |
| `_compress_context`                | 上下文压缩：摘要、剪枝、轮换会话                                     |
| `_execute_tool_calls`              | 执行模型请求的工具调用，将结果注入消息历史                           |
| `_try_activate_fallback`           | 激活故障转移链中的下一个提供商                                       |
| `_recover_with_credential_pool`    | 轮换凭证池中的备选 API Key / OAuth 令牌                             |
| `apply_anthropic_cache_control`    | 为 Anthropic 模型注入 prompt caching 控制标记                        |
| `normalize_usage`                  | 统一不同提供商的 token 使用报告格式                                  |
| `estimate_usage_cost`              | 估算本轮 API 调用的美元成本                                          |
| `finalize_turn`                    | 回合收尾：记忆回顾、会话持久化、资源清理、返回结果组装                 |

---

## 八、关键设计决策

1. **API 消息与内部消息的分离**：`messages` 是权威会话历史，`api_messages` 是每轮构建的 API 调用副本。这样可以安全地注入临时内容（预取记忆、MoA 上下文、prefill）而不污染持久化状态。

2. **流式优先**：即使没有流消费者，也优先使用流式路径以获取健康检查（超时检测）。

3. **错误分类先行**：所有错误先分类再处理，避免基于状态码的硬编码判断，支持新提供商快速适配。

4. **宽限调用（Grace Call）**：预算耗尽后仍给最后一次机会，防止在临界点附近因预算截断而失败。

5. **压缩是恢复手段而非预防手段**：压缩只在检测到压力/溢出时触发，而非每次调用前盲目执行，以保留完整上下文精度。

6. **每轮重置计数器**：`invalid_tool_retries`、`invalid_json_retries` 等在每个成功的 API 调用后重置，防止早期错误永久降低容错能力。

7. **空响应不立即放弃**：通过多层恢复（部分流恢复、上一轮内容回退、nudge、预填充、重试、fallback）最大化弱模型的可用性。

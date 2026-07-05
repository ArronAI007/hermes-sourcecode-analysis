# tests/ 目录解释

`tests/` 是 Hermes Agent 的测试套件，涵盖单元测试、集成测试、端到端测试、性能测试等。

---

## 目录结构

```
tests/
├─── conftest.py                # pytest 全局配置和夹具
├─── acp/                       # ACP 协议测试
├─── acp_adapter/               # ACP 适配器测试
├─── agent/                     # Agent 核心测试
│   ├─── test_conversation_loop.py
│   ├─── test_chat_completion.py
│   ├─── test_context_compressor.py
│   ├─── test_memory_manager.py
│   ├─── test_curator.py
│   ├─── test_error_classifier.py
│   └─── ...
├─── cli/                       # CLI 测试
├─── gateway/                   # 网关测试
├─── tools/                     # 工具测试
├─── run_agent/                 # run_agent 测试
├─── hermes_cli/                # CLI 工具测试
├─── hermes_state/              # 状态管理测试
├─── integration/               # 集成测试
├─── e2e/                       # 端到端测试
├─── stress/                    # 压力测试
├─── computer_use/              # 计算机使用测试
├─── cron/                      # 定时任务测试
├─── docker/                    # Docker 测试
├─── plugins/                   # 插件测试
├─── providers/                 # 提供商测试
├─── skills/                    # 技能测试
├─── website/                   # 网站测试
├─── tui_gateway/               # TUI 网关测试
├─── fakes/                     # 模拟对象
├─── fixtures/                  # 测试固件
├─── ci/                        # CI 测试
├─── manual/                    # 手动测试
├─── scripts/                   # 测试脚本
├─── honcho_plugin/             # Honcho 插件测试
└─── openviking_plugin/         # OpenViking 插件测试
```

---

## 测试类型

| 目录 | 类型 | 说明 |
|------|------|------|
| `agent/` | 单元测试 | 对话循环、压缩、记忆、错误处理等单元测试 |
| `tools/` | 单元测试 | 各工具的单独测试 |
| `gateway/` | 集成测试 | 网关消息路由、会话管理测试 |
| `cli/` | 集成测试 | 命令行交互测试 |
| `integration/` | 集成测试 | 多模块协作测试 |
| `e2e/` | E2E 测试 | 全流程端到端测试 |
| `stress/` | 压力测试 | 高并发、长时间运行测试 |
| `fakes/` | 模拟 | 模拟对象和模拟服务 |
| `fixtures/` | 固件 | 测试数据和配置 |

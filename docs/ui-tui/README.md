# ui-tui/ 目录解释

`ui-tui/` 是 Hermes Agent 的 TUI (终端用户界面) 子项目，基于 prompt_toolkit 构建的富文本终端界面。

---

## 目录结构

```
ui-tui/
├─── package.json             # Node.js 项目配置
├─── tsconfig.json            # TypeScript 配置
├─── tsconfig.build.json      # 构建配置
├─── vitest.config.ts         # 测试配置
├─── eslint.config.mjs        # ESLint 配置
├─── .prettierrc              # Prettier 配置
├─── .gitignore
├─── README.md
├─── src/                     # 源代码
└─── packages/                # 内部包
```

---

## 说明

TUI 是 CLI 的替代界面，提供：
- 固定输入区域
- 实时消息渲染
- 多行编辑
- 命令自动补全
- 会话历史浏览

其实际运行时由 `cli.py` 中的 prompt_toolkit 相关代码处理，ui-tui 是独立的前端项目。

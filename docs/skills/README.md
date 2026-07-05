# skills/ 目录解释

`skills/` 是 Hermes Agent 的技能系统，包含可被 Agent 学习和使用的自定义技能模块。技能是可复用的功能模块，可以在对话中被自动触发。

---

## 目录结构

```
skills/
├─── apple/                     # Apple 生态系统技能
├─── autonomous-ai-agents/      # 自主 AI Agent 技能
├─── computer-use/              # 计算机使用技能
├─── creative/                  # 创意技能
├─── data-science/              # 数据科学技能
├─── dogfood/                   # 内部使用技能
├─── email/                     # 邮件技能
├─── github/                    # GitHub 技能
├─── index-cache/               # 索引缓存
├─── media/                     # 媒体处理技能
├─── mlops/                     # MLOps 技能
├─── note-taking/               # 笔记技能
├─── productivity/              # 效率技能
├─── research/                  # 研究技能
├─── smart-home/                # 智能家居技能
├─── social-media/              # 社交媒体技能
├─── software-development/      # 软件开发技能
└─── yuanbao/                   # 元宝技能
```

---

## 技能系统说明

技能是 Hermes 的**自我学习循环**的核心组成部分：

1. **自动创建**：当 Agent 完成复杂任务后，`curator.py` 会自动提取可复用的模式创建技能
2. **持续改进**：在使用过程中，技能会根据反馈自我优化
3. **动态加载**：技能在运行时动态加载，不需要重启

每个技能通常包含：
- `skill.yaml` - 技能元数据
- `*.py` - 技能实现代码
- `prompts/` - 提示模板
- `examples/` - 示例数据

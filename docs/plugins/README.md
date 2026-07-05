# plugins/ 目录解释

`plugins/` 是 Hermes Agent 的插件系统，提供可扩展的功能模块。插件是比技能更低层的扩展机制，通常用于集成第三方服务。

---

## 目录结构

```
plugins/
├─── browser/                   # 浏览器插件
├─── context_engine/            # 上下文引擎插件
├─── cron_providers/            # 定时任务提供商
├─── dashboard_auth/            # 仪表盘认证
├─── disk-cleanup/              # 磁盘清理
├─── google_meet/               # Google Meet 集成
├─── hermes-achievements/       # 成就系统
├─── image_gen/                 # 图像生成插件
├─── kanban/                    # 看板插件
├─── memory/                    # 记忆插件
├─── model-providers/           # 模型提供商插件
├─── observability/             # 可观测性插件
├─── platforms/                 # 平台插件
├─── security-guidance/         # 安全引导
├─── spotify/                   # Spotify 集成
├─── teams_pipeline/            # Teams 流水线
├─── video_gen/                 # 视频生成
└─── web/                       # Web 插件
```

---

## 插件机制

插件通过标准化的接口注册到系统中：

1. 定义 `plugin.yaml` 描述插件元数据
2. 实现标准接口类
3. 在启动时动态加载

插件与技能的区别：
- **插件**：系统级扩展，通常是第三方服务集成
- **技能**：用户级功能，由 Agent 自动创建和管理

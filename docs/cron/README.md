# cron/ 目录解释

`cron/` 是 Hermes Agent 的定时任务调度系统。

---

## 目录结构

```
cron/
├─── __init__.py              # 导出接口
├─── jobs.py                  # 任务存储和管理
├─── scheduler.py             # 调度器执行
├─── lifecycle_guard.py         # 生命周期守护
├─── suggestion_catalog.py     # 建议目录
├─── suggestions.py           # 建议管理
├─── blueprint_catalog.py       # 蓝图目录
└─── scripts/                # 定时脚本
```

---

## 核心模块

| 文件 | 职责 |
|------|------|
| `jobs.py` | 任务存储（~/.hermes/cron/jobs.json）和 CRUD 操作 |
| `scheduler.py` | tick() 检查到期任务并执行，文件锁防止重复 |

---

## 任务管理 API

```python
from cron import (
    create_job,      # 创建任务
    get_job,        # 获取任务
    list_jobs,      # 列出所有任务
    remove_job,     # 删除任务
    update_job,     # 更新任务
    pause_job,      # 暂停任务
    resume_job,     # 恢复任务
    trigger_job,     # 手动触发任务
)
```

---

## 调用关系

```
gateway/run.py
    │
    ▼
每 60 秒 tick()
    │
    ▼
scheduler.py:tick()
    │
    ▼
检查到期任务 → 执行
```

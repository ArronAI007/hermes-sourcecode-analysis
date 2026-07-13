# =============================================================================
# cron/ - Cron 定时任务调度系统
# =============================================================================
#
# 本模块提供定时任务执行功能，允许 Agent：
#   - 按计划运行自动化任务（cron 表达式、时间间隔、单次）
#   - 自动安排提醒和后续任务
#   - 在隔离会话中执行任务（无先前上下文）
#
# 调度器由网关守护进程自动触发：
#     hermes gateway install    # 安装为用户服务
#     sudo hermes gateway install --system  # Linux 服务器：开机自启动服务
#     hermes gateway            # 或前台运行
#
# 工作机制：
#   - 网关每 60 秒触发一次调度器 tick
#   - 文件锁防止多个进程重复执行
# =============================================================================

"""
Cron job scheduling system for Hermes Agent.

This module provides scheduled task execution, allowing the agent to:
- Run automated tasks on schedules (cron expressions, intervals, one-shot)
- Self-schedule reminders and follow-up tasks
- Execute tasks in isolated sessions (no prior context)

Cron jobs are executed automatically by the gateway daemon:
    hermes gateway install    # Install as a user service
    sudo hermes gateway install --system  # Linux servers: boot-time system service
    hermes gateway            # Or run in foreground

The gateway ticks the scheduler every 60 seconds. A file lock prevents
duplicate execution if multiple processes overlap.
"""

from cron.jobs import (
    create_job,
    get_job,
    list_jobs,
    remove_job,
    update_job,
    pause_job,
    resume_job,
    trigger_job,
    JOBS_FILE,
)
from cron.scheduler import tick

__all__ = [
    "create_job",
    "get_job", 
    "list_jobs",
    "remove_job",
    "update_job",
    "pause_job",
    "resume_job",
    "trigger_job",
    "tick",
    "JOBS_FILE",
]

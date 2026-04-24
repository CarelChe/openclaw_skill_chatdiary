# ChatDiary (OpenClaw Skill)

把「讲故事」对话自动记录到 Obsidian 日记文件。

## 功能

- 触发词开始记录：讲故事 / 开始讲故事
- 触发词结束记录：不讲了 / 停止讲故事
- 结束时优先使用会话原文落盘，尽量避免 AI 复述误差
- 自动维护 # 话题（含语义去重）和 # 对话记录
- 可选每日总结脚本（daily_summary.py）
- 全本地存储，无云端依赖

## 安装

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/CarelChe/openclaw_skill_chatdiary chatdiary
cd chatdiary/scripts
```

## 最小配置

```bash
python3 config.py --set-path "/path/to/your/obsidian/diary"
python3 config.py --show
```

说明：
- 必填：diary_base（日记目录）
- 选填：user_name（默认 User）
- 用户名也可自动从 OpenClaw user.md 读取

配置优先级（高 -> 低）：
1. 环境变量 DIARY_LOGGER_PATH / DIARY_LOGGER_USER
2. ~/.diary-logger/config.json
3. 默认值（仅 user_name 有默认值）

## 使用方式

1. 在对话开头输入：讲故事 ... 或 开始讲故事 ...
2. 正常聊天，消息会持续缓存
3. 在对话结尾输入：不讲了 或 停止讲故事
4. 系统自动完成：
   - 写入对话记录
   - 更新话题
   - 追加分割线 ----

## 输出格式

```markdown
---
date: 2026-04-14
tags: 日记
---

# 话题
- 公园散步
- 天气晴朗

# 对话记录
- **14:30** User：我去了公园散步
- **14:30** AI：听起来很不错
----
```

## 常见问题

1. 提示未找到路径配置

```bash
python3 scripts/config.py --set-path "/path/to/your/diary"
```

2. 消息未落盘

- 检查 diary 路径是否存在且可写
- 执行 python3 scripts/config.py --show 确认配置
- 检查会话历史来源是否可读（使用 end-auto 时）

3. Obsidian 看不到新文件

- 在 Obsidian 执行 reload 或重启

## 项目结构

```text
chatdiary/
├── README.md
├── SETUP.md
├── CONFIGURATION.md
├── SKILL.md
├── .instructions.md
├── scripts/
│   ├── diary_logger.py
│   ├── state_manager.py
│   ├── config.py
│   └── daily_summary.py
└── 示例.md
```

## 隐私

- 日记内容与状态文件均保存在本地
- 项目不依赖第三方云端日志服务

## 许可证

本项目使用 MIT License，详见 LICENSE 文件。

## 开源发布完成

- ✅ 已替换仓库地址
- ✅ 已添加 MIT License
- 可选：补充 Issue 模板与最小 CI

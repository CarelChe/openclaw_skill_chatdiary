# ChatDiary (OpenClaw Skill)

把和 AI 的深度对话，自动沉淀为可回看的 Obsidian 日记。

ChatDiary 适合“边聊边记录”的场景：你只管表达，Skill 负责把一整轮对话整理进当天日记文件，并维护话题索引。

## 为什么值得用

- 几乎零负担：通过触发词开启/结束，不打断聊天
- 更可靠：优先从缓存写入，失败自动回退到会话文件
- 更干净：自动剥离触发词，不污染正文
- 更有结构：自动维护 # 话题、# 对话记录、分割线
- 更私密：本地文件存储，不依赖云端日志服务

## 核心能力

- 开始触发词：讲故事 / 开始讲故事
- 结束触发词：不讲了 / 停止讲故事
- 写入格式：- **HH:MM** 用户名：内容
- 话题更新：支持语义去重，避免同义话题重复堆积
- 可选脚本：支持每日自动总结（daily_summary.py）

## 30 秒快速开始

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/CarelChe/openclaw_skill_chatdiary chatdiary
cd chatdiary/scripts

# 必填：设置 Obsidian 日记目录
python3 config.py --set-path "/path/to/your/obsidian/diary"

# 可选：设置显示用户名（不设则自动读取 OpenClaw user.md）
python3 config.py --set-user "Your Name"

# 检查配置
python3 config.py --show
```

## 你会看到什么

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

## 工作机制（简版）

1. 你说“讲故事 ...”开始记录
2. 每轮 user/assistant 对话会进入缓存（pair）
3. 你说“不讲了”结束记录
4. 系统按顺序尝试落盘：
   - 主路径：本地缓存
   - 第一备用：--history-file 指定的历史文件
   - 第二备用：自动解析会话文件

## 常用命令（脚本调试/自检）

```bash
# 开始/结束
python3 diary_logger.py start
python3 diary_logger.py end-auto 话题1 话题2

# 手动指定会话文件结束
python3 diary_logger.py end-session ./session.json 话题1 话题2

# 写入一轮对话缓存
python3 diary_logger.py pair "用户消息" "AI回复"

# 查看状态与结构检查
python3 diary_logger.py status
python3 diary_logger.py check
```

## 配置说明

- 必填：diary_base（日记目录）
- 选填：user_name（默认 User）

配置优先级（高 -> 低）：

1. 环境变量 DIARY_LOGGER_PATH / DIARY_LOGGER_USER
2. ~/.diary-logger/config.json
3. 默认值（仅 user_name 有默认值）

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

## 隐私与许可证

- 日记内容和状态文件都保存在本地
- 不依赖第三方云端日志服务
- 许可证：MIT（见 LICENSE）

## 下一步

- 详细安装与排障：SETUP.md
- 配置机制详解：CONFIGURATION.md

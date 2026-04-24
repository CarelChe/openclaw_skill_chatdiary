# Setup Guide

这份文档只保留开源发布所需的最小步骤。

## 1. 前置要求

- Python 3.8+
- Obsidian 已安装
- 已准备一个用于存放日记的目录

## 2. 安装到 OpenClaw skills

```bash
cd ~/.openclaw/workspace/skills
git clone https://github.com/CarelChe/openclaw_skill_chatdiary chatdiary
cd chatdiary/scripts
```

## 3. 配置日记路径

推荐方式：

```bash
python3 config.py --set-path "/path/to/your/obsidian/diary"
python3 config.py --show
```

可选设置用户名：

```bash
python3 config.py --set-user "Your Name"
```

说明：如果不设置用户名，会尝试从 OpenClaw 的 user.md 自动读取，仍失败则使用 User。

## 4. 验证是否可写

```bash
python3 - << 'EOF'
import os
from config import DiaryLoggerConfig

cfg = DiaryLoggerConfig()
path = str(cfg.get_diary_base())
print("diary_base:", path)
print("exists:", os.path.exists(path))
print("writable:", os.access(path, os.W_OK))
EOF
```

## 5. 最小使用流程

1. 对话开头输入：讲故事 ...
2. 聊天若干轮
3. 对话结尾输入：不讲了
4. 打开 Obsidian 查看当天日期文件

## 6. 常见问题

1. 报错“未找到 Obsidian 日记库路径配置”

```bash
python3 config.py --set-path "/path/to/your/obsidian/diary"
```

2. 报错 ModuleNotFoundError

```bash
cd ~/.openclaw/workspace/skills/chatdiary/scripts
python3 config.py --show
```

3. Obsidian 看不到新文件

- 重载 Obsidian 或重启应用

## 7. 可选：每日自动总结

手动运行：

```bash
cd ~/.openclaw/workspace/skills/chatdiary/scripts
python3 daily_summary.py
```

cron 示例：

```bash
0 1 * * * cd ~/.openclaw/workspace/skills/chatdiary/scripts && python3 daily_summary.py >> ~/.diary-logger/summary.log 2>&1
```

## 8. 配置文件位置

- ~/.diary-logger/config.json
- ~/.diary-logger/.state.json

# ⚙️ 配置系统详解

Diary Logger の配置系统设计为灵活且用户友好，提供三种配置方式。

## 🎯 核心概念

Diary Logger 需要两个关键配置：

| 配置项 | 说明 | 示例 | 可选？ |
|--------|------|------|--------|
| `user_name` | 在日记中显示的用户名 | `Alice` | 是（默认：`User`） |
| `diary_base` | Obsidian 日记库的本地路径 | `/path/to/your/obsidian/diary` | 否 |

## 📍 配置加载流程

```
┌─────────────────────────────────────────────┐
│  应用启动时需要加载配置                      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
       ┌─────────────────────────┐
       │ 1️⃣  环境变量             │
       │ DIARY_LOGGER_PATH       │
       │ DIARY_LOGGER_USER       │
       └────────────┬────────────┘
                    │
        ┌───────────┴───────────┐
        │ 找到？  YES            │ NO
        │        ↓              │
        │     使用这些值         ▼
        │                   ┌─────────────────────────┐
        │                   │ 2️⃣  配置文件             │
        │                   │ ~/.diary-logger/        │
        │                   │ config.json             │
        │                   └────────────┬────────────┘
        │                                │
        │                ┌───────────────┴───────────────┐
        │                │ 文件存在？  YES              NO │
        │                │         ↓                  │
        │                │     读取配置文件             ▼
        │                │                      ┌──────────────────┐
        │                │                      │ 3️⃣  使用默认值    │
        │                │                      │ user_name="User" │
        │                │                      │ diary_base=      │
        │                │                      │   （未设置→错误） │
        │                │                      └──────────────────┘
        │                │
        └────────────────┴───────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────────┐
              │   ✅ 配置加载完成        │
              │  应用开始运行            │
              └──────────────────────────┘
```

## 🔄 三层配置优先级

### 第 1 层：命令行参数（最高优先级）

通过 `config.py` 设置：

```bash
# 设置日记库路径
python3 config.py --set-path "/path/to/diary"

# 设置用户名
python3 config.py --set-user "Your Name"

# 显示当前配置
python3 config.py --show
```

这会立即写入 `~/.diary-logger/config.json`，后续运行都会使用这些值。

### 第 2 层：环境变量

设置环境变量来临时覆盖配置文件：

```bash
# 临时设置（仅当前 shell session）
export DIARY_LOGGER_PATH="/path/to/diary"
export DIARY_LOGGER_USER="Your Name"

python3 diary_logger.py  # 会使用环境变量
```

**永久设置：**

在 `~/.zshrc` 或 `~/.bash_profile` 中添加：

```bash
export DIARY_LOGGER_PATH="/path/to/your/diary"
export DIARY_LOGGER_USER="Alice"
```

然后：
```bash
source ~/.zshrc
```

### 第 3 层：配置文件（最低优先级）

`~/.diary-logger/config.json` - 持久化的配置文件：

```json
{
  "user_name": "Alice",
  "diary_base": "/path/to/your/obsidian/diary"
}
```

## 📊 优先级对比表

| 场景 | 配置文件 | 环境变量 | 实际使用 | 原因 |
|------|--------|--------|---------|------|
| 都未设置 | — | — | 默认值 | 降级到默认值 |
| 只配置文件 | ✅ Alice | — | Alice | 使用配置文件 |
| 配置文件 + 环境变量 | Alice | Bob | Bob | 环境变量优先级更高 |
| 环境变量（未设置）| 已设置为 Alice | 未设置 | Alice | 环境变量未设置，回退到配置文件 |

## 🛠️ 实际使用场景

### 场景 1：标准个人用户

适合有固定 Obsidian 库的用户：

```bash
# 一次性设置
python3 config.py --set-path "/path/to/your/obsidian/diary"
python3 config.py --set-user "Alice"

# 此后每次使用都无需再设置
```

**特点：**
- ✅ 简单、一次性配置
- ✅ 无需每次设置
- ✅ 配置持久化

### 场景 2：多个项目使用不同日记库

使用环境变量为不同项目设置不同的日记库：

```bash
# 项目 A - 工作日记
export DIARY_LOGGER_PATH="/data/work-diary"
python3 diary_logger.py

# 项目 B - 个人日记
export DIARY_LOGGER_PATH="/data/personal-diary"
python3 diary_logger.py
```

**特点：**
- ✅ 灵活切换多个日记库
- ✅ 不污染全局配置
- ✅ 适合自动化脚本

### 场景 3：Docker 或容器化部署

使用环境变量注入配置：

```dockerfile
# Dockerfile
ENV DIARY_LOGGER_PATH="/data/diary"
ENV DIARY_LOGGER_USER="DefaultUser"
```

**特点：**
- ✅ 无需挂载配置文件
- ✅ 容器原生支持
- ✅ 易于自动化

### 场景 4：开发和测试

使用临时配置：

```bash
# 测试不同的设置
export DIARY_LOGGER_PATH="<TEST_DIARY_DIR>"
python3 config.py --show

# 验证工作后再切换回真实路径
export DIARY_LOGGER_PATH="/real/diary/path"
```

## 📝 配置文件格式

### 位置

```
~/.diary-logger/config.json
```

如果不存在，首次使用 `--set-path` 或 `--set-user` 时自动创建。

### 结构

```json
{
  "user_name": "Your Name",
  "diary_base": "/absolute/path/to/obsidian/diary"
}
```

### 规则

- **user_name**：
  - 类型：字符串
  - 长度：1-100 字符
  - 支持中文、英文、emoji
  - 示例：`"Alice"`, `"爱丽丝"`, `"Alice 🎯"`

- **diary_base**：
  - 类型：绝对路径字符串
  - 必须是有效的目录路径
  - 必须有读写权限
  - 示例：`"/path/to/your/obsidian/diary"`

## 🔐 环境变量参考

### DIARY_LOGGER_PATH

Obsidian 日记库的本地路径。

```bash
export DIARY_LOGGER_PATH="/path/to/your/obsidian/diary"
```

- **优先级：** 高于配置文件
- **可选：** 否（必须设置）
- **类型：** 目录路径
- **验证：** 路径必须存在且可写

### DIARY_LOGGER_USER

在日记中显示的用户名。

```bash
export DIARY_LOGGER_USER="Alice"
```

- **优先级：** 高于配置文件
- **可选：** 是（默认：`User`）
- **类型：** 字符串
- **最大长度：** 100 字符

## 🔧 programmatic 配置（For Developers）

### 在代码中使用配置

```python
from config import DiaryLoggerConfig

# 创建配置对象
config = DiaryLoggerConfig()

# 读取用户名
user_name = config.get_user_name()
print(f"User: {user_name}")

# 读取日记库路径
diary_path = config.get_diary_base()
print(f"Diary: {diary_path}")
```

### 设置配置

```python
from config import DiaryLoggerConfig

# 设置配置并持久化到文件
DiaryLoggerConfig.set_config(
    user_name="Bob",
    diary_base="/path/to/bob/diary"
)

# 验证
config = DiaryLoggerConfig()
print(config.get_user_name())  # Bob
```

## 🧪 测试配置

### 验证环境变量

```bash
echo $DIARY_LOGGER_PATH
echo $DIARY_LOGGER_USER
```

### 验证配置文件

```bash
cat ~/.diary-logger/config.json
```

### 验证生效的配置

```bash
cd ~/.openclaw/workspace/skills/diary-logger/scripts
python3 config.py --show
```

### Python 验证脚本

```bash
python3 << 'EOF'
import os
import json
from pathlib import Path

print("=" * 50)
print("🔍 Diary Logger 配置诊断")
print("=" * 50)

# 检查环境变量
print("\n📌 环境变量:")
diary_path = os.environ.get('DIARY_LOGGER_PATH', '(未设置)')
diary_user = os.environ.get('DIARY_LOGGER_USER', '(未设置)')
print(f"  DIARY_LOGGER_PATH: {diary_path}")
print(f"  DIARY_LOGGER_USER: {diary_user}")

# 检查配置文件
config_file = Path.home() / ".diary-logger" / "config.json"
print(f"\n📁 配置文件: {config_file}")
if config_file.exists():
    with open(config_file) as f:
        config = json.load(f)
    print(f"  user_name: {config.get('user_name', '(未设置)')}")
    print(f"  diary_base: {config.get('diary_base', '(未设置)')}")
else:
    print("  (配置文件不存在)")

# 加载最终配置
print("\n✅ 最终使用的配置:")
import sys
sys.path.insert(0, '.')
from config import DiaryLoggerConfig
config_obj = DiaryLoggerConfig()
print(f"  user_name: {config_obj.get_user_name()}")
print(f"  diary_base: {config_obj.get_diary_base()}")
EOF
```

## 🚨 常见配置问题

### Q: 修改配置后没有生效

**A: 原因可能是：**
1. 环境变量覆盖了新设置的配置文件值
   - 解决：`unset DIARY_LOGGER_PATH`
2. Python 进程缓存了旧配置
   - 解决：重启 Python 进程

### Q: 路径包含空格怎么办？

**A: 使用引号包裹路径：**
```bash
python3 config.py --set-path "/path/to/your/obsidian/diary"
```

### Q: 能否使用相对路径？

**A: 不推荐，会导致行为不确定。** 始终使用绝对路径：
```bash
# ❌ 不要这样做
python3 config.py --set-path "./diary"

# ✅ 这样做
python3 config.py --set-path "$HOME/Documents/diary"
```

### Q: 如何临时切换到不同的日记库测试？

**A: 使用环境变量：**
```bash
# 临时切换
export DIARY_LOGGER_PATH="<TEST_DIARY_DIR>"

# 运行程序
python3 diary_logger.py

# 切换回原来的
export DIARY_LOGGER_PATH="/original/diary/path"
```

## 📚 更多信息

- 查看 [README.md](README.md) 了解功能概述
- 查看 [SETUP.md](SETUP.md) 了解安装步骤
- 查看代码中的 `config.py` 了解技术实现

---

**需要帮助？** 查看 README.md 中的故障排除部分或提交 Issue！

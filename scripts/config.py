#!/usr/bin/env python3
"""
日记记录器配置模块
支持从以下来源读取配置（优先级从高到低）：
1. 环境变量
2. ~/.diary-logger/config.json
3. 从 OpenClaw user.md 读取用户名
"""

import json
import os
import re
from pathlib import Path


class DiaryLoggerConfig:
    """日记记录器配置管理"""
    
    DEFAULT_CONFIG_PATH = Path.home() / ".diary-logger" / "config.json"
    
    # 默认值
    DEFAULT_USER_NAME = "User"
    
    def __init__(self):
        self.user_name = None
        self.diary_base = None
        self.load_config()
    
    def _load_user_name_from_openclaw(self):
        """从 OpenClaw 的 user.md 文件中读取用户名"""
        # 尝试常见的 OpenClaw user.md 路径
        possible_paths = [
            Path.home() / ".openclaw" / "user.md",
            Path.home() / ".openclaw" / "agents" / "main" / "user.md",
        ]
        
        for user_md_path in possible_paths:
            if user_md_path.exists():
                try:
                    content = user_md_path.read_text(encoding="utf-8")
                    # 尝试从 frontmatter 中读取 name
                    name_match = re.search(r'^name:\s*["\']?([^"\'\n]+)["\']?', content, re.MULTILINE)
                    if name_match:
                        return name_match.group(1).strip()
                    # 尝试从第一行标题读取
                    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                    if title_match:
                        return title_match.group(1).strip()
                except (OSError, UnicodeDecodeError):
                    continue
        return None
    
    def load_config(self):
        """从多个来源加载配置"""
        # 1. 从环境变量读取
        self.user_name = os.getenv("DIARY_LOGGER_USER", None)
        self.diary_base = os.getenv("DIARY_LOGGER_PATH", None)
        
        # 2. 从配置文件读取
        if self.DEFAULT_CONFIG_PATH.exists():
            try:
                with open(self.DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.user_name = self.user_name or config.get("user_name")
                    self.diary_base = self.diary_base or config.get("diary_base")
            except (json.JSONDecodeError, OSError):
                pass
        
        # 3. 从 OpenClaw user.md 读取用户名（如果环境变量和配置文件都未设置）
        if not self.user_name:
            self.user_name = self._load_user_name_from_openclaw()
        
        # 4. 验证必须的配置
        if not self.user_name:
            self.user_name = self.DEFAULT_USER_NAME
        
        if not self.diary_base:
            raise ValueError(
                "未找到 Obsidian 日记库路径配置。\n"
                "请通过以下方式之一设置：\n"
                "  1. 环境变量：export DIARY_LOGGER_PATH=/path/to/your/diary\n"
                "  2. 配置文件：mkdir -p ~/.diary-logger && echo '{\"diary_base\": \"/path/to/your/diary\"}' > ~/.diary-logger/config.json\n"
                "  3. 命令行参数：python3 config.py --set-path /path/to/your/diary"
            )
    
    @classmethod
    def set_config(cls, user_name=None, diary_base=None):
        """保存配置到文件"""
        cls.DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        config = {}
        if cls.DEFAULT_CONFIG_PATH.exists():
            try:
                with open(cls.DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except json.JSONDecodeError:
                pass
        
        if user_name:
            config["user_name"] = user_name
        if diary_base:
            config["diary_base"] = diary_base
        
        with open(cls.DEFAULT_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return config
    
    def get_user_name(self):
        """获取用户名"""
        return self.user_name
    
    def get_diary_base(self):
        """获取日记库路径"""
        if not self.diary_base:
            raise ValueError("未配置 diary_base")
        return Path(self.diary_base)


# 全局配置实例
def get_config():
    """获取全局配置"""
    try:
        return DiaryLoggerConfig()
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--set-path" and len(sys.argv) > 2:
            path = sys.argv[2]
            DiaryLoggerConfig.set_config(diary_base=path)
            print(f"✅ 已设置日记库路径: {path}")
        elif sys.argv[1] == "--set-user" and len(sys.argv) > 2:
            user = sys.argv[2]
            DiaryLoggerConfig.set_config(user_name=user)
            print(f"✅ 已设置用户名: {user}")
        elif sys.argv[1] == "--show":
            config = get_config()
            print(f"用户名: {config.get_user_name()}")
            print(f"日记库: {config.get_diary_base()}")
        else:
            print("usage: config.py [--set-path <path>] [--set-user <name>] [--show]")
    else:
        print("用法: python3 config.py --set-path <path> --set-user <name>")

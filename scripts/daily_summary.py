#!/usr/bin/env python3
"""
每日凌晨执行的日记总结脚本
读取前一天的日记文件，生成固定格式的总结，并写回原文件。
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from config import DiaryLoggerConfig

# 从配置系统读取日记路径
_config = DiaryLoggerConfig()
DIARY_PATH = _config.get_diary_base()

# 用户名用于匹配日记中的对话记录
USER_NAME = _config.get_user_name()

# 动态生成匹配正则，支持配置的用户名
CONVERSATION_LINE_PATTERN = re.compile(
    rf"^- \*\*(?P<time>\d{{2}}:\d{{2}})\*\* (?P<role>{re.escape(USER_NAME)}|AI)：(?P<text>.*)$"
)


def get_yesterday_file():
    """获取前一天的日记文件路径"""
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    filename = f"{date_str} 记录.md"
    return DIARY_PATH / filename, date_str


def read_file(filepath):
    """读取文件内容"""
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return None


def write_file(filepath, content):
    """写入文件内容"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def extract_round_blocks(content):
    """按轮次提取内容块"""
    pattern = re.compile(r"^# 话题\s*\n.*?(?=^# 话题\s*$|\Z)", re.MULTILINE | re.DOTALL)
    return pattern.findall(content)


def extract_topics(content):
    """提取所有轮次里的非空话题条目"""
    topics = []
    for block in extract_round_blocks(content):
        topic_match = re.search(
            r"^# 话题\s*\n(.*?)(?=^# 对话记录\s*$|\Z)", block, re.MULTILINE | re.DOTALL
        )
        if not topic_match:
            continue

        for line in topic_match.group(1).splitlines():
            line = line.strip()
            if not line.startswith("-"):
                continue

            topic = line.lstrip("-").strip()
            if topic and topic != "（从对话内容中提取，可空）":
                topics.append(topic)

    return topics


def extract_conversation_lines(content):
    """提取所有轮次里的固定格式对话记录行"""
    entries = []
    for block in extract_round_blocks(content):
        conversation_match = re.search(
            r"^# 对话记录\s*\n(.*?)(?=^# 话题\s*$|\Z)", block, re.MULTILINE | re.DOTALL
        )
        if not conversation_match:
            continue

        for raw_line in conversation_match.group(1).splitlines():
            line = raw_line.strip()
            if not line or line in ("---", "----"):
                continue

            match = CONVERSATION_LINE_PATTERN.match(line)
            if not match:
                continue

            entries.append(
                {
                    "time": match.group("time"),
                    "role": match.group("role"),
                    "text": match.group("text").strip(),
                }
            )

    return entries


def summarize_conversations(topics, conversation_entries):
    """生成稳定的总结条目"""
    summary_items = []
    seen = set()

    for topic in topics:
        topic_text = topic.strip()
        if topic_text and topic_text not in seen:
            seen.add(topic_text)
            summary_items.append(f"话题：{topic_text}")

    for entry in conversation_entries:
        text = entry["text"].strip()
        if not text:
            continue

        if any(keyword in text for keyword in ["要", "会", "计划", "决定", "去", "做", "约", "谈", "处理"]):
            key = text[:60]
            if key not in seen:
                seen.add(key)
                summary_items.append(f"{entry['role']}：{text}")

    if not summary_items:
        summary_items.append("无明显事项")

    return summary_items


def generate_summary(content):
    """生成固定模板的总结内容"""
    topics = extract_topics(content)
    conversation_entries = extract_conversation_lines(content)
    summary_items = summarize_conversations(topics, conversation_entries)

    summary_lines = ["# 总结", ""]
    summary_lines.extend(f"- {item}" for item in summary_items)
    return "\n".join(summary_lines)


def update_file_with_summary(filepath, new_summary):
    """更新文件中的总结部分，保持文件名不变"""
    content = read_file(filepath)
    if not content:
        return False

    cleaned_content = content.rstrip()
    summary_pattern = re.compile(r"\n# 总结\n.*\Z", re.DOTALL)

    if summary_pattern.search(cleaned_content):
        cleaned_content = summary_pattern.sub("\n" + new_summary, cleaned_content)
    else:
        cleaned_content = cleaned_content + "\n\n" + new_summary

    write_file(filepath, cleaned_content + "\n")
    return True


def run_daily_summary():
    """执行每日总结"""
    file_path, date_str = get_yesterday_file()

    print(f"检查文件: {file_path}")

    if not file_path.exists():
        print("文件不存在，跳过总结")
        return {"status": "skipped", "reason": "file_not_found", "date": date_str}

    content = read_file(file_path)
    if not content:
        print("文件为空，跳过总结")
        return {"status": "skipped", "reason": "empty_file", "date": date_str}

    summary = generate_summary(content)
    success = update_file_with_summary(file_path, summary)
    if success:
        print(f"总结已写入 {file_path.name}")
        return {"status": "success", "date": date_str, "file": str(file_path)}

    return {"status": "error", "reason": "update_failed", "date": date_str}


if __name__ == "__main__":
    result = run_daily_summary()
    print(json.dumps(result, ensure_ascii=False, indent=2))

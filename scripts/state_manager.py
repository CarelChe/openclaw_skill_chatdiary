#!/usr/bin/env python3
"""
日记记录状态管理
存储和读取记录模式的状态
"""

import json
import os
from pathlib import Path

# 状态文件路径：放在通用的配置目录下
STATE_FILE = Path.home() / ".diary-logger" / ".state.json"
DEFAULT_STATE = {"recording": False, "date": None, "topics": [], "buffered_messages": [], "last_flushed_contents": []}


def _normalize_topics(topics):
    normalized = []
    seen = set()

    for topic in topics or []:
        topic_text = str(topic).strip()
        if not topic_text or topic_text in seen:
            continue
        seen.add(topic_text)
        normalized.append(topic_text)

    return normalized


def _normalize_buffered_messages(messages):
    normalized = []

    for item in messages or []:
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "")).strip().lower()
        if role not in ("user", "assistant"):
            continue

        content = str(item.get("content", "")).strip()
        if not content:
            continue

        time_value = str(item.get("time", "")).strip()
        if len(time_value) != 5 or time_value[2] != ":":
            continue

        normalized.append({"role": role, "content": content, "time": time_value})

    return normalized


def _normalize_state(state):
    normalized = dict(DEFAULT_STATE)

    if isinstance(state, dict):
        normalized["recording"] = bool(state.get("recording", False))

        date_value = state.get("date")
        normalized["date"] = None if date_value in (None, "") else str(date_value).strip()

        normalized["topics"] = _normalize_topics(state.get("topics", []))
        normalized["buffered_messages"] = _normalize_buffered_messages(
            state.get("buffered_messages", [])
        )
        # 保留 last_flushed_contents（每次 flush 后由 diary_logger.py 更新）
        raw_flushed = state.get("last_flushed_contents", [])
        if isinstance(raw_flushed, list):
            normalized["last_flushed_contents"] = [str(c) for c in raw_flushed if c]
        else:
            normalized["last_flushed_contents"] = []

    return normalized


def load_state():
    """加载状态"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return _normalize_state(json.load(f))
        except (OSError, json.JSONDecodeError):
            return dict(DEFAULT_STATE)
    return dict(DEFAULT_STATE)


def save_state(state):
    normalized = _normalize_state(state)
    temp_file = STATE_FILE.with_name(STATE_FILE.name + ".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    os.replace(temp_file, STATE_FILE)
    return normalized


def is_recording():
    state = load_state()
    return state.get("recording", False)


def start_recording(date_str, topics=None):
    state = {
        "recording": True,
        "date": None if date_str in (None, "") else str(date_str).strip(),
        "topics": _normalize_topics(topics or []),
        "buffered_messages": [],
    }
    return save_state(state)


def stop_recording():
    state = load_state()
    state["recording"] = False
    state["buffered_messages"] = []
    return save_state(state)


def add_topic(topic, date_str):
    """同一天内话题去重"""
    state = load_state()
    topic_text = str(topic).strip()
    normalized_date = None if date_str in (None, "") else str(date_str).strip()

    if not topic_text:
        return state

    if state.get("date") != normalized_date:
        state = {
            "recording": True,
            "date": normalized_date,
            "topics": [topic_text],
            "buffered_messages": [],
        }
    else:
        state["recording"] = True
        topics = _normalize_topics(state.get("topics", []))
        if topic_text not in topics:
            topics.append(topic_text)
        state["topics"] = topics

    return save_state(state)


def get_topics(date_str):
    state = load_state()
    normalized_date = None if date_str in (None, "") else str(date_str).strip()

    if state.get("date") == normalized_date:
        return state.get("topics", [])
    return []


def buffer_message(role, content, time_str, date_str):
    """缓存单条消息，等待 stop 时统一写入文件"""
    state = load_state()
    normalized_date = None if date_str in (None, "") else str(date_str).strip()
    role_value = str(role).strip().lower()
    text = str(content).strip()
    time_value = str(time_str).strip()

    if role_value not in ("user", "assistant") or not text:
        return state

    if len(time_value) != 5 or time_value[2] != ":":
        return state

    if state.get("date") != normalized_date:
        state["date"] = normalized_date
        state["buffered_messages"] = []

    buffered = _normalize_buffered_messages(state.get("buffered_messages", []))
    buffered.append({"role": role_value, "content": text, "time": time_value})
    state["buffered_messages"] = buffered

    return save_state(state)


def buffer_message_pair(user_content, assistant_content, time_str, date_str):
    """原子缓存一轮 user+assistant 消息"""
    state = load_state()
    normalized_date = None if date_str in (None, "") else str(date_str).strip()
    time_value = str(time_str).strip()

    if len(time_value) != 5 or time_value[2] != ":":
        return state

    if state.get("date") != normalized_date:
        state["date"] = normalized_date
        state["buffered_messages"] = []

    buffered = _normalize_buffered_messages(state.get("buffered_messages", []))

    user_text = str(user_content).strip()
    if user_text:
        buffered.append({"role": "user", "content": user_text, "time": time_value})

    assistant_text = str(assistant_content).strip()
    if assistant_text:
        buffered.append({"role": "assistant", "content": assistant_text, "time": time_value})

    state["buffered_messages"] = buffered
    return save_state(state)


def get_buffered_messages(date_str):
    """获取当天缓存消息"""
    state = load_state()
    normalized_date = None if date_str in (None, "") else str(date_str).strip()

    if state.get("date") != normalized_date:
        return []

    return _normalize_buffered_messages(state.get("buffered_messages", []))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: state_manager.py <load|start|stop|add_topic|get_topics|get_buffered> [args]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "load":
        print(json.dumps(load_state(), ensure_ascii=False, indent=2))
    elif cmd == "start":
        date = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(start_recording(date), ensure_ascii=False, indent=2))
    elif cmd == "stop":
        print(json.dumps(stop_recording(), ensure_ascii=False, indent=2))
    elif cmd == "add_topic":
        topic = sys.argv[2] if len(sys.argv) > 2 else ""
        date = sys.argv[3] if len(sys.argv) > 3 else ""
        print(json.dumps(add_topic(topic, date), ensure_ascii=False, indent=2))
    elif cmd == "get_topics":
        date = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(get_topics(date), ensure_ascii=False, indent=2))
    elif cmd == "get_buffered":
        date = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(get_buffered_messages(date), ensure_ascii=False, indent=2))

#!/usr/bin/env python3
"""
日记记录器核心模块
用途：自动管理日记文件的创建、格式化和消息写入
无需每次手动指定流程，直接调用对应函数即可
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from state_manager import (
    load_state,
    save_state,
    start_recording,
    stop_recording,
    buffer_message,
    buffer_message_pair,
    get_buffered_messages,
)
from config import DiaryLoggerConfig

# 从配置系统读取用户名和日记库路径
try:
    _config = DiaryLoggerConfig()
    USER_NAME = _config.get_user_name()
    DIARY_BASE = _config.get_diary_base()
    DIARY_BASE.mkdir(parents=True, exist_ok=True)
except ValueError as e:
    print(f"❌ 配置错误: {e}")
    exit(1)

# 触发词定义（来自 SKILL.md）
START_TRIGGERS = ["讲故事", "开始讲故事"]
STOP_TRIGGERS = ["停止讲故事", "不讲了"]
SEPARATOR_LINE = "----"
DEFAULT_BUFFER_FLUSH_THRESHOLD = 4


# ============ 触发词与状态检查函数 ============

def validate_start_trigger(msg):
    """
    检查消息开头是否包含开始触发词
    符合 SKILL.md：必须在消息**开头**
    """
    msg = msg.strip()
    for trigger in START_TRIGGERS:
        if msg.startswith(trigger):
            return True
    return False


def validate_stop_trigger(msg):
    """
    检查消息结尾是否包含停止触发词
    符合 SKILL.md：必须在消息**结尾**
    """
    msg = msg.strip()
    for trigger in STOP_TRIGGERS:
        if msg.endswith(trigger):
            return True
    return False


def strip_trigger_words(msg):
    """
    从消息中删除触发词
    符合 SKILL.md：触发词只用于判定状态，不写入正文
    
    处理规则：
    - "开始讲故事..." → "..."
    - "讲故事..." → "..."
    - "...停止讲故事" → "..."
    - "...不讲了" → "..."
    """
    msg = msg.strip()
    
    # 处理开始触发词（从开头删除）
    if msg.startswith("开始讲故事"):
        msg = msg[len("开始讲故事"):]
    elif msg.startswith("讲故事"):
        msg = msg[len("讲故事"):]

    msg = msg.lstrip(" \t，,。．.、;；:：!?？！")
    
    # 处理停止触发词（从结尾删除）
    if msg.endswith("停止讲故事"):
        idx = msg.rfind("停止讲故事")
        msg = msg[:idx]
    elif msg.endswith("不讲了"):
        idx = msg.rfind("不讲了")
        msg = msg[:idx]

    msg = msg.rstrip(" \t，,。．.、;；:：!?？！")
    
    return msg.strip()


def get_recording_status():
    """获取当前录制状态"""
    state = load_state()
    return {
        "recording": state.get("recording", False),
        "date": state.get("date"),
        "topics": state.get("topics", []),
        "buffered_count": len(state.get("buffered_messages", [])),
    }


# ============ 文件操作函数 ============


def get_today_file():
    """获取今天的日记文件路径"""
    today = datetime.now().strftime("%Y-%m-%d")
    return DIARY_BASE / f"{today}.md"


def get_current_time():
    """获取当前时间 HH:MM 格式"""
    return datetime.now().strftime("%H:%M")


def _get_buffer_flush_threshold():
    """读取缓存分段落盘阈值，避免状态文件无限增长"""
    raw = os.getenv("DIARY_LOGGER_BUFFER_FLUSH_THRESHOLD", "").strip()
    if not raw:
        return DEFAULT_BUFFER_FLUSH_THRESHOLD

    try:
        threshold = int(raw)
    except ValueError:
        return DEFAULT_BUFFER_FLUSH_THRESHOLD

    return max(10, threshold)


def _ensure_today_file_scaffold(file_path):
    """确保当天文件框架存在"""
    if not file_path.exists():
        ensure_front_matter(file_path)
        ensure_section(file_path, "话题")
        ensure_section(file_path, "对话记录")


def _is_hhmm(value):
    """判断字符串是否是 HH:MM 时间格式"""
    if not isinstance(value, str):
        return False

    text = value.strip()
    if len(text) != 5 or text[2] != ":":
        return False

    hour = text[:2]
    minute = text[3:]
    if not (hour.isdigit() and minute.isdigit()):
        return False

    return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59


def _resolve_message_time(message):
    """从会话消息中解析 HH:MM，失败则回退当前时间"""
    if not isinstance(message, dict):
        return get_current_time()

    for key in ("time", "hhmm"):
        value = message.get(key)
        if _is_hhmm(value):
            return str(value).strip()

    for key in ("timestamp", "created_at", "createdAt"):
        value = message.get(key)
        if not value:
            continue
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except ValueError:
            continue

    return get_current_time()


def _normalize_history_role(value):
    """统一会话 role，兼容常见命名"""
    role = str(value or "").strip().lower()
    if role in ("user", "human"):
        return "user"
    if role in ("assistant", "ai", "model"):
        return "assistant"
    return ""


def _strip_wechat_metadata(text):
    """剥离企业微信 webhook 的 Conversation info 元数据块，保留纯文本"""
    if not isinstance(text, str):
        return text
    # 匹配 Conversation info (untrusted metadata): 后跟 JSON 代码块，然后是实际文本
    pattern = r"Conversation info \(untrusted metadata\):\s*```json\s*\{[^}]+\}\s*```\s*"
    stripped = re.sub(pattern, "", text, flags=re.DOTALL)
    return stripped.strip()


def _normalize_history_messages(messages):
    """把会话历史转换为标准消息结构"""
    normalized = []

    for item in messages or []:
        if not isinstance(item, dict):
            continue

        # 处理 OpenClaw JSONL 格式：{"type":"message","message":{"role":..., "content":...}}
        inner = item
        if "message" in item and isinstance(item["message"], dict):
            inner = item["message"]

        role = _normalize_history_role(inner.get("role"))
        if not role:
            continue

        content = inner.get("content", "")
        # content 可能是字符串，也可能是 [{type:"text",text:"..."}] 格式
        if isinstance(content, list):
            text = "".join(c.get("text", "") for c in content if isinstance(c, dict))
            content = text
        content = _strip_wechat_metadata(str(content))
        content = content.strip()
        if not content:
            continue

        normalized.append(
            {
                "role": role,
                "content": content,
                "time": _resolve_message_time(inner) or _resolve_message_time(item),
            }
        )

    return normalized


def _slice_latest_round_from_history(messages):
    """
    从会话历史中切出“最近一轮讲故事”消息：
    - 起点：用户消息开头命中开始触发词
    - 终点：用户消息结尾命中停止触发词
    """
    normalized = _normalize_history_messages(messages)
    if not normalized:
        return []

    stop_index = -1
    for idx in range(len(normalized) - 1, -1, -1):
        item = normalized[idx]
        if item["role"] == "user" and validate_stop_trigger(item["content"]):
            stop_index = idx
            break

    if stop_index < 0:
        return []

    start_index = -1
    for idx in range(stop_index, -1, -1):
        item = normalized[idx]
        if item["role"] == "user" and validate_start_trigger(item["content"]):
            start_index = idx
            break

    if start_index < 0 or start_index > stop_index:
        return []

    sliced = []
    for idx in range(start_index, stop_index + 1):
        item = dict(normalized[idx])
        if item["role"] == "user":
            item["content"] = strip_trigger_words(item["content"])
        if item["content"]:
            sliced.append(item)

    return sliced


def load_round_messages_from_session_file(session_json_path):
    """从会话 JSON 文件中提取最近一轮完整对话"""
    path = Path(session_json_path)
    if not path.exists():
        return {"status": "error", "reason": "session_file_not_found", "path": str(path)}

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return {"status": "error", "reason": "session_file_unreadable", "path": str(path)}

    messages = []

    # 1) 先按标准 JSON 解析（单对象或数组）
    try:
        payload = json.loads(raw_text)
        if isinstance(payload, dict):
            if isinstance(payload.get("messages"), list):
                messages.extend(payload.get("messages", []))
            else:
                messages.append(payload)
        elif isinstance(payload, list):
            messages.extend(payload)
    except (OSError, json.JSONDecodeError):
        # 2) JSON 失败时按 JSONL 逐行解析
        messages = []
        try:
            for line in raw_text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                obj = json.loads(stripped)
                if isinstance(obj, dict) and isinstance(obj.get("messages"), list):
                    messages.extend(obj.get("messages", []))
                elif isinstance(obj, list):
                    messages.extend(obj)
                elif isinstance(obj, dict):
                    messages.append(obj)
        except json.JSONDecodeError:
            return {"status": "error", "reason": "invalid_session_json", "path": str(path)}

    if not messages:
        return {"status": "error", "reason": "session_messages_empty", "path": str(path)}

    round_messages = _slice_latest_round_from_history(messages)
    if not round_messages:
        return {"status": "error", "reason": "round_not_found", "path": str(path)}

    return {
        "status": "ok",
        "path": str(path),
        "messages": round_messages,
        "count": len(round_messages),
    }


def _default_openclaw_sessions_index():
    """返回默认 OpenClaw sessions.json 路径"""
    return Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"


def resolve_session_file_from_index(index_file_path=None):
    """从 sessions.json 中解析最新可用的 sessionFile"""
    if index_file_path:
        index_path = Path(index_file_path)
    else:
        env_path = Path(str(Path.home()))
        custom_path = None
        try:
            import os
            custom_path = os.getenv("OPENCLAW_SESSIONS_INDEX", "").strip()
        except Exception:
            custom_path = ""

        if custom_path:
            index_path = Path(custom_path)
        else:
            index_path = _default_openclaw_sessions_index()

    if not index_path.exists():
        return {
            "status": "error",
            "reason": "sessions_index_not_found",
            "index": str(index_path),
        }

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "error",
            "reason": "sessions_index_invalid",
            "index": str(index_path),
        }

    if not isinstance(payload, dict):
        return {
            "status": "error",
            "reason": "sessions_index_invalid",
            "index": str(index_path),
        }

    candidates = []
    for key, item in payload.items():
        if not isinstance(item, dict):
            continue
        session_file = str(item.get("sessionFile", "")).strip()
        if not session_file:
            continue
        updated_at = item.get("updatedAt", 0)
        try:
            updated_at = int(updated_at)
        except (TypeError, ValueError):
            updated_at = 0

        file_path = Path(session_file)
        if not file_path.exists():
            continue

        candidates.append(
            {
                "key": str(key),
                "session_file": str(file_path),
                "updated_at": updated_at,
            }
        )

    if not candidates:
        return {
            "status": "error",
            "reason": "session_file_not_found_in_index",
            "index": str(index_path),
        }

    # 优先选择最近更新的会话文件
    candidates.sort(key=lambda x: x["updated_at"], reverse=True)
    selected = candidates[0]

    return {
        "status": "ok",
        "index": str(index_path),
        "session_key": selected["key"],
        "session_file": selected["session_file"],
        "updated_at": selected["updated_at"],
    }


def _append_lines_to_end(content, lines):
    """把行内容直接追加到文件末尾"""
    block = "".join(lines)
    base = content.rstrip("\n")

    if not base:
        return block
    return base + "\n" + block


def _extract_existing_topics(content):
    """提取首个 # 话题 区块中的条目"""
    match = re.search(r"(?ms)^# 话题\s*\n(.*?)(?=^# [^\n]+\s*$|\Z)", content)
    if not match:
        return []

    topics = []
    seen = set()
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        topic = stripped.lstrip("-").strip()
        if not topic:
            continue
        if topic in seen:
            continue
        seen.add(topic)
        topics.append(topic)
    return topics


def _normalize_topic_text(topic):
    """把话题压缩成便于比对的文本"""
    text = str(topic).strip().lower()
    text = re.sub(r"[\s\t\n\r\uff0c,\u3002\uff0e\u3001;\uff1b:\uff1a!?\uff1f\uff01\uff08\uff09\[\]\u300a\u300b{}<>\u3008\u3009\'\u201c\u201d\u2018\u2019\u00b7-]+", "", text)
    text = re.sub(r"^(今天|昨天|明天|这次|这个|那个|最近|刚刚|刚才|一下|一会儿|有点|有些|关于)", "", text)
    text = re.sub(r"(这件事|这个事|那件事|那件事情|这件事情|的话题)$", "", text)
    return text


def _topics_semantically_same(left, right):
    """用轻量规则判断两个话题是否表达同一件事"""
    left_norm = _normalize_topic_text(left)
    right_norm = _normalize_topic_text(right)

    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    if left_norm in right_norm or right_norm in left_norm:
        return True

    left_chars = set(left_norm)
    right_chars = set(right_norm)
    if not left_chars or not right_chars:
        return False

    overlap = len(left_chars & right_chars) / max(len(left_chars | right_chars), 1)
    return overlap >= 0.7


def _ensure_conversation_section(content):
    """确保存在 # 对话记录 章节，不存在则创建在 # 话题 后"""
    if re.search(r"(?m)^# 对话记录\s*$", content):
        return content

    topic_match = re.search(r"(?m)^# 话题\s*$", content)
    if topic_match:
        insert_at = topic_match.end()
        return content[:insert_at] + "\n\n# 对话记录\n" + content[insert_at:]

    if content.startswith("---\n"):
        fm_end_match = re.search(r"(?m)^---\s*$", content[4:])
        if fm_end_match:
            fm_end = 4 + fm_end_match.end()
            prefix = content[:fm_end].rstrip("\n") + "\n\n"
            suffix = content[fm_end:].lstrip("\n")
            if suffix:
                return prefix + "# 对话记录\n\n" + suffix
            return prefix + "# 对话记录\n"

    base = content.rstrip("\n")
    if base:
        return base + "\n\n# 对话记录\n"
    return "# 对话记录\n"


def _append_lines_to_conversation_section(content, lines):
    """将对话行追加到 # 对话记录 章节内（在 # 附件 或其他后续标题前）"""
    if not lines:
        return content

    content = _ensure_conversation_section(content)
    dialog_match = re.search(r"(?m)^# 对话记录\s*$", content)
    if not dialog_match:
        return _append_lines_to_end(content, lines)

    section_start = dialog_match.end()
    remainder = content[section_start:]
    next_section = re.search(r"(?m)^# [^\n]+\s*$", remainder)

    if next_section:
        insert_at = section_start + next_section.start()
        prefix = content[:insert_at].rstrip("\n")
        suffix = content[insert_at:].lstrip("\n")
        block = "".join(lines)
        if prefix:
            prefix = prefix + "\n"
        if suffix:
            return prefix + block + "\n" + suffix
        return prefix + block

    return _append_lines_to_end(content, lines)


def _conversation_last_nonempty_line(content):
    """读取 # 对话记录 区块内最后一条非空行"""
    dialog_match = re.search(r"(?m)^# 对话记录\s*$", content)
    if not dialog_match:
        return ""

    section_start = dialog_match.end()
    remainder = content[section_start:]
    next_section = re.search(r"(?m)^# [^\n]+\s*$", remainder)
    section_body = remainder[:next_section.start()] if next_section else remainder

    lines = [line.strip() for line in section_body.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _render_buffered_lines(messages):
    """将缓存消息渲染为日记行。内容按单行输出，空行不产生记录行（靠上下行的时间戳表示间隔）。"""
    lines = []
    for item in messages:
        role = item.get("role")
        time_str = item.get("time")
        content = item.get("content")

        if role not in ("user", "assistant"):
            continue
        if not time_str:
            continue

        speaker = USER_NAME if role == "user" else "AI"

        if not content:
            continue

        raw_lines = content.splitlines()
        for rl in raw_lines:
            if rl.strip():
                if role == "user":
                    lines.append(f"- **{time_str} {speaker}：{rl}**\n")
                else:
                    lines.append(f"- **{time_str} {speaker}：** {rl}\n")

    return lines


def _consume_buffer_head(date_str, count):
    """消费 state 中前 count 条缓存消息"""
    if count <= 0:
        return

    state = load_state()
    if state.get("date") != date_str:
        return

    buffered = list(state.get("buffered_messages", []))
    state["buffered_messages"] = buffered[count:]
    save_state(state)


def flush_buffered_messages(add_separator=False):
    """
    将当前缓存写入文件并只清空已写入部分缓存。
    - add_separator=False: 中途分段落盘，不追加分割线，不结束 recording
    - add_separator=True: 结束时落盘，追加分割线
    """
    file_path = get_today_file()
    _ensure_today_file_scaffold(file_path)

    today = datetime.now().strftime("%Y-%m-%d")
    buffered_messages = get_buffered_messages(today)
    if not buffered_messages:
        return {"status": "skipped", "reason": "buffer_empty", "flushed_count": 0}

    flush_messages = list(buffered_messages)

    # 中途分段落盘时只写完整对话对，避免留下孤立 user 行
    if not add_separator and len(flush_messages) % 2 == 1:
        flush_messages = flush_messages[:-1]

    if not flush_messages:
        return {
            "status": "skipped",
            "reason": "incomplete_pair_only",
            "flushed_count": 0,
        }

    # 如果 flush 前 buffer 里只有 AI 消息（user 被触发词 strip 成空），不 flush
    # 这种 AI-only pair 是触发词场景的副产物，不应推动正常的 flush 计数
    if len(flush_messages) == 1 and flush_messages[0].get("role") == "assistant":
        return {
            "status": "skipped",
            "reason": "ai_only_no_flush",
            "flushed_count": 0,
        }

    # 只 flush 完整的一对（user + AI），不拆散 pair
    # 保留末尾不完整的一对，由 end_auto 处理
    if len(flush_messages) % 2 == 1:
        flush_messages = flush_messages[:-1]

    content = file_path.read_text(encoding="utf-8")
    lines_to_write = _render_buffered_lines(flush_messages)
    if add_separator:
        last_conversation_line = _conversation_last_nonempty_line(content)
        if lines_to_write or last_conversation_line not in ("---", "----"):
            lines_to_write.append(SEPARATOR_LINE + "\n")

    if lines_to_write:
        content = _append_lines_to_conversation_section(content, lines_to_write)
        file_path.write_text(content, encoding="utf-8")

    _consume_buffer_head(today, len(flush_messages))

    # 记录本次 flush 的原始消息内容，用于 session 备份去重
    flushed_contents = [msg.get("content", "") for msg in flush_messages if msg.get("content")]
    if flushed_contents:
        state = load_state()
        state["last_flushed_contents"] = flushed_contents
        save_state(state)

    return {
        "status": "flushed",
        "file": str(file_path),
        "flushed_count": len(flush_messages),
        "add_separator": bool(add_separator),
    }


def maybe_flush_buffer_if_near_full():
    """缓存接近上限时自动分段落盘"""
    status = get_recording_status()
    if not status.get("recording"):
        return {"status": "skipped", "reason": "not_recording"}

    threshold = _get_buffer_flush_threshold()
    buffered_count = int(status.get("buffered_count", 0))
    if buffered_count < threshold:
        return {
            "status": "skipped",
            "reason": "below_threshold",
            "buffered_count": buffered_count,
            "threshold": threshold,
        }

    result = flush_buffered_messages(add_separator=False)
    result["buffered_count"] = buffered_count
    result["threshold"] = threshold
    return result


def _build_topics_section(topics):
    """构建标准 # 话题 章节内容"""
    topic_line = "- " + "\n- ".join(topics) + "\n"
    return "# 话题\n" + topic_line


def _normalize_round_topics(topics):
    """规范化本轮输入话题：去空、去重、最多 3 个"""
    normalized = []
    seen = set()

    for topic in topics or []:
        topic_text = str(topic).strip()
        if not topic_text or topic_text in seen:
            continue
        seen.add(topic_text)
        normalized.append(topic_text)

    return normalized[:3]


def _upsert_primary_topics_section(content, topics):
    """
    只更新最前面的 # 话题 章节：
    - 若存在，原位替换该章节内容
    - 若不存在，插入到首个 # 对话记录 之前（或 front matter 后）
    """
    new_topics_section = _build_topics_section(topics)

    first_topic_match = re.search(r"(?m)^# 话题\s*$", content)
    if first_topic_match:
        start = first_topic_match.start()
        remainder = content[start:]
        next_boundary = re.search(r"(?m)^(# [^\n]+\s*$|(?:---|----)\s*$)", remainder[1:])
        if next_boundary:
            end = start + 1 + next_boundary.start()
        else:
            end = len(content)

        prefix = content[:start].rstrip("\n") + "\n\n"
        suffix = content[end:].lstrip("\n")
        if suffix:
            return prefix + new_topics_section + "\n\n" + suffix
        return prefix + new_topics_section + "\n"

    dialog_match = re.search(r"(?m)^# 对话记录\s*$", content)
    if dialog_match:
        insert_at = dialog_match.start()
        prefix = content[:insert_at].rstrip("\n") + "\n\n"
        suffix = content[insert_at:].lstrip("\n")
        return prefix + new_topics_section + "\n\n" + suffix

    if content.startswith("---\n"):
        fm_end_match = re.search(r"(?m)^---\s*$", content[4:])
        if fm_end_match:
            fm_end = 4 + fm_end_match.end()
            prefix = content[:fm_end].rstrip("\n") + "\n\n"
            suffix = content[fm_end:].lstrip("\n")
            if suffix:
                return prefix + new_topics_section + "\n\n" + suffix
            return prefix + new_topics_section + "\n"

    base = content.lstrip("\n")
    if base:
        return new_topics_section + "\n\n" + base
    return new_topics_section + "\n"


def ensure_front_matter(file_path):
    """确保文件头存在（仅第一次）"""
    if not file_path.exists():
        today = datetime.now().strftime("%Y-%m-%d")
        front_matter = f"""---
date: {today}
tags: 日记
---

"""
        file_path.write_text(front_matter, encoding="utf-8")
        return True
    return False


def ensure_section(file_path, section_name):
    """确保指定章节存在"""
    content = file_path.read_text(encoding="utf-8")
    section_header = f"\n# {section_name}\n"

    if section_header.strip() not in [line.strip() for line in content.split("\n")]:
        if section_name == "话题":
            section_content = section_header + "- \n\n"
        elif section_name == "对话记录":
            section_content = section_header
        file_path.write_text(content + section_content, encoding="utf-8")
        return True
    return False


def start_daily_log(topics=None):
    """
    开始今天的日记记录
    - 创建/打开日记文件
    - 初始化文件框架
    - 更新状态为 recording
    """
    file_path = get_today_file()
    today = datetime.now().strftime("%Y-%m-%d")

    # 新建文件时创建框架
    if not file_path.exists():
        ensure_front_matter(file_path)
        ensure_section(file_path, "话题")
        ensure_section(file_path, "对话记录")

    # 更新状态
    start_recording(today, topics or [])

    return {
        "status": "started",
        "file": str(file_path),
        "date": today,
        "topics": topics or [],
    }


def append_user_message(user_content):
    """
    缓存用户消息（stop 时统一写入）
    格式：- **HH:MM** {USER_NAME}：[内容]
    """
    if not user_content or not user_content.strip():
        return {"status": "skipped", "reason": "empty_content"}

    status = get_recording_status()
    if not status.get("recording"):
        return {"status": "error", "reason": "not_recording"}

    today = datetime.now().strftime("%Y-%m-%d")
    time_str = get_current_time()
    clean_content = strip_trigger_words(user_content)
    if not clean_content:
        return {"status": "skipped", "reason": "empty_content"}

    buffer_message("user", clean_content, time_str, today)
    return {"status": "buffered", "type": "user", "time": time_str}


def append_assistant_message(assistant_content):
    """
    缓存 AI 响应（stop 时统一写入）
    格式：- **HH:MM** AI：[内容]
    """
    if not assistant_content or not assistant_content.strip():
        return {"status": "skipped", "reason": "empty_content"}

    status = get_recording_status()
    if not status.get("recording"):
        return {"status": "error", "reason": "not_recording"}

    today = datetime.now().strftime("%Y-%m-%d")
    time_str = get_current_time()
    clean_content = assistant_content.strip()
    if not clean_content:
        return {"status": "skipped", "reason": "empty_content"}

    buffer_message("assistant", clean_content, time_str, today)
    return {"status": "buffered", "type": "assistant", "time": time_str}


def append_message_pair(user_content, assistant_content):
    """
    原子地缓存用户消息 + AI 回复对
    在 stop 时统一写入，避免中间轮次漏记
    """
    if (not user_content or not user_content.strip()) and (not assistant_content or not assistant_content.strip()):
        return {"status": "skipped", "reason": "empty_content"}

    status = get_recording_status()
    if not status.get("recording"):
        return {"status": "error", "reason": "not_recording"}

    today = datetime.now().strftime("%Y-%m-%d")
    time_str = get_current_time()
    clean_user = strip_trigger_words(user_content) if user_content and user_content.strip() else ""
    clean_assistant = assistant_content.strip() if assistant_content and assistant_content.strip() else ""

    if not clean_user and not clean_assistant:
        return {"status": "skipped", "reason": "empty_content"}

    # 如果 user 消息被触发词 strip 成空（停止词场景），只缓存 AI 回复，不占 buffer 位
    if not clean_user:
        buffer_message("assistant", clean_assistant, time_str, today)
    else:
        buffer_message_pair(clean_user, clean_assistant, time_str, today)

    flush_result = maybe_flush_buffer_if_near_full()
    return {
        "status": "buffered",
        "type": "pair",
        "time": time_str,
        "flush": flush_result,
    }


def end_daily_log(topics=None, source_messages=None):
    """
    结束今天的日记记录
    - 追加分割线 ---
    - 更新话题
    - 更新状态为 idle
    """
    file_path = get_today_file()
    _ensure_today_file_scaffold(file_path)

    content = file_path.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")

    # 优先使用会话原文；若未提供则回退到缓存
    if source_messages is None:
        flush_result = flush_buffered_messages(add_separator=True)
        if flush_result.get("status") != "flushed":
            return {
                "status": "error",
                "reason": flush_result.get("reason", "buffer_flush_failed"),
                "hint": "若为 buffer_empty，说明对话轮次未成功写入 pair 缓存；请检查每轮 pair 是否执行成功。",
                "message_source": "buffer",
                "written_count": 0,
                "topics": _normalize_round_topics(topics or []),
                "added_topics": [],
                "duplicate_topics": [],
            }

        # flush 后重新读取内容，确保话题更新基于最新文本
        content = file_path.read_text(encoding="utf-8")
        messages_to_write = [{}] * int(flush_result.get("flushed_count", 0))
        message_source = "buffer"
    else:
        messages_to_write = _normalize_history_messages(source_messages)
        message_source = "session_history"
        if not messages_to_write:
            return {
                "status": "error",
                "reason": "source_messages_empty",
                "message_source": message_source,
                "written_count": 0,
                "topics": _normalize_round_topics(topics or []),
                "added_topics": [],
                "duplicate_topics": [],
            }

    if source_messages is not None:
        buffered_lines = _render_buffered_lines(messages_to_write)
        last_conversation_line = _conversation_last_nonempty_line(content)

        # 去重检查：pair flush 时用户消息被 strip 成空，只写了 AI 回复。
        # session 备份找到的 round 第一条 user 消息是触发词（如"不讲了"），
        # 所以应比较 pair 最后写入的 AI 回复 与 session 备份第一对中的 AI 回复。
        skip_write = False
        if buffered_lines:
            state = load_state()
            last_flushed = state.get("last_flushed_contents", [])
            # 提取 session 备份第一条 AI 消息的实际内容（第一对中的 AI）
            first_ai_content = None
            for line in buffered_lines:
                if "**" in line and re.search(r"\*\*\s+AI[：：]", line):
                    stripped = re.sub(r"^\- \*\*[^*]+\*\*\s+AI[：：]", "", line, count=1)
                    cleaned = re.sub(r"\s+", " ", stripped.replace("\n", " ")).strip()
                    if cleaned:
                        first_ai_content = cleaned
                        break
                # 遇到 user 消息就跳过，继续找 AI
                if "**" in line and re.search(r"\*\*\s+[^：]+[：：]", line) and "AI" not in line:
                    continue
            if first_ai_content and last_flushed:
                # 检查 session 备份的第一个 AI 内容是否已在本轮 last_flushed 中
                # 如果是，说明这轮内容已被 pair 写入，跳过 session 备份写入
                if first_ai_content in last_flushed:
                    skip_write = True

        lines_to_write = list(buffered_lines)
        if buffered_lines or last_conversation_line not in ("---", "----"):
            lines_to_write.append(SEPARATOR_LINE + "\n")

        if lines_to_write and not skip_write:
            content = _append_lines_to_conversation_section(content, lines_to_write)
        elif skip_write:
            # 跳过写入但仍然更新话题
            pass

    # 更新 # 话题：合并已存在条目 + 本轮新话题，并保持在 # 对话记录 上方
    existing_topics = _extract_existing_topics(content)
    round_topics = _normalize_round_topics(topics or [])

    normalized_topics = list(existing_topics)
    added_topics = []
    duplicate_topics = []

    for topic_text in round_topics:
        if any(_topics_semantically_same(topic_text, existing_topic) for existing_topic in normalized_topics):
            duplicate_topics.append(topic_text)
            continue
        normalized_topics.append(topic_text)
        added_topics.append(topic_text)

    if normalized_topics:
        content = _upsert_primary_topics_section(content, normalized_topics)

    file_path.write_text(content, encoding="utf-8")

    # 更新状态
    stop_recording()

    return {
        "status": "ended",
        "file": str(file_path),
        "topics": round_topics,
        "added_topics": added_topics,
        "duplicate_topics": duplicate_topics,
        "message_source": message_source,
        "written_count": len(messages_to_write),
    }


def log_message_pair(user_msg, assistant_msg, is_first=False):
    """
    一步到位：缓存用户消息 + AI 回复
    """
    return append_message_pair(user_msg, assistant_msg)


def _split_front_matter(content):
    """拆分 front matter 与正文"""
    if not content.startswith("---\n"):
        return "", content

    closing_match = re.search(r"(?m)^---\s*$", content[4:])
    if not closing_match:
        return "", content

    end_idx = 4 + closing_match.end()
    front_matter = content[:end_idx]
    body = content[end_idx:]
    return front_matter, body


def _extract_top_sections(body):
    """提取一级标题章节（# 标题）"""
    matches = list(re.finditer(r"(?m)^# ([^\n]+)\s*$", body))
    sections = []

    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        section_body = body[start:end]
        sections.append((title, section_body))

    return sections


def check_and_fix_daily_structure():
    """
    结构自检并自动修复：
    1) front matter
    2) # 话题（唯一）
    3) # 对话记录（唯一，完整保留 user/AI 行）
    4) # 附件（可选）
    """
    file_path = get_today_file()
    if not file_path.exists():
        return {"status": "skipped", "reason": "file_not_found", "file": str(file_path)}

    original = file_path.read_text(encoding="utf-8")
    issues = []

    front_matter, body = _split_front_matter(original)
    if not front_matter:
        issues.append("missing_front_matter")
        today = datetime.now().strftime("%Y-%m-%d")
        front_matter = f"---\ndate: {today}\ntags: 日记\n---"

    sections = _extract_top_sections(body)
    topic_sections = [s for s in sections if s[0] == "话题"]
    dialog_sections = [s for s in sections if s[0] == "对话记录"]
    attachment_sections = [s for s in sections if s[0] == "附件"]
    extra_sections = [s for s in sections if s[0] not in ("话题", "对话记录", "附件")]

    if not topic_sections:
        issues.append("missing_topic_section")
    if len(topic_sections) > 1:
        issues.append("duplicate_topic_sections")
    if not dialog_sections:
        issues.append("missing_dialog_section")
    if len(dialog_sections) > 1:
        issues.append("duplicate_dialog_sections")
    if len(attachment_sections) > 1:
        issues.append("duplicate_attachment_sections")

    topics = []
    topic_seen = set()
    for _, topic_body in topic_sections:
        for raw_line in topic_body.splitlines():
            line = raw_line.strip()
            if not line.startswith("-"):
                continue
            topic = line.lstrip("-").strip()
            if not topic or topic in topic_seen:
                continue
            topic_seen.add(topic)
            topics.append(topic)

    conversation_lines = []
    for _, dialog_body in dialog_sections:
        for raw_line in dialog_body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "---":
                line = "----"
                if "legacy_separator_found" not in issues:
                    issues.append("legacy_separator_found")
            conversation_lines.append(line)

    attachment_lines = []
    for _, attachment_body in attachment_sections:
        for raw_line in attachment_body.splitlines():
            line = raw_line.rstrip()
            if line:
                attachment_lines.append(line)

    rebuilt = []
    rebuilt.append(front_matter.rstrip("\n"))
    rebuilt.append("")
    rebuilt.append("")
    rebuilt.append("# 话题")
    if topics:
        rebuilt.extend(f"- {topic}" for topic in topics)
    else:
        rebuilt.append("- ")
    rebuilt.append("")
    rebuilt.append("")
    rebuilt.append("# 对话记录")
    rebuilt.extend(conversation_lines)

    if attachment_lines:
        rebuilt.append("")
        rebuilt.append("")
        rebuilt.append("# 附件")
        rebuilt.extend(attachment_lines)

    for title, extra_body in extra_sections:
        cleaned_lines = [line.rstrip() for line in extra_body.splitlines() if line.strip()]
        if not cleaned_lines:
            continue
        rebuilt.append("")
        rebuilt.append("")
        rebuilt.append(f"# {title}")
        rebuilt.extend(cleaned_lines)

    normalized = "\n".join(rebuilt).rstrip("\n") + "\n"
    fixed = normalized != original
    if fixed:
        issues.append("structure_reordered")
        file_path.write_text(normalized, encoding="utf-8")

    return {
        "status": "fixed" if fixed else "ok",
        "file": str(file_path),
        "fixed": fixed,
        "issues": issues,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: diary_logger.py <start|end|end-session|end-auto|user|assistant|status|pair|check> [args...]"
        )
        print("\nExamples:")
        print('  diary_logger.py start "话题1" "话题2"')
        print('  diary_logger.py user "用户消息"')
        print('  diary_logger.py assistant "AI回复"')
        print('  diary_logger.py pair "用户消息" "AI回复"')
        print("  diary_logger.py end 话题1 话题2")
        print("  diary_logger.py end-session ./session.json 话题1 话题2")
        print("  diary_logger.py end-auto 话题1 话题2")
        print("  diary_logger.py check")
        print("  diary_logger.py status")
        sys.exit(1)

    print("\n【审计提示】触发词检查命令（符合 SKILL.md）：")
    print('  diary_logger.py check-start "[用户消息]"  # 检查是否可以开始')
    print('  diary_logger.py check-stop "[用户消息]"   # 检查是否应该停止')

    cmd = sys.argv[1]

    if cmd == "start":
        topics = sys.argv[2:] if len(sys.argv) > 2 else []
        result = start_daily_log(topics)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "end":
        topics = sys.argv[2:] if len(sys.argv) > 2 else []
        result = end_daily_log(topics)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "end-session":
        session_file = sys.argv[2] if len(sys.argv) > 2 else ""
        topics = sys.argv[3:] if len(sys.argv) > 3 else []
        loaded = load_round_messages_from_session_file(session_file)
        if loaded.get("status") != "ok":
            # 自动回退：会话原文不可用时，尝试消费 buffer，避免上层漏掉 fallback
            fallback_result = end_daily_log(topics)
            if fallback_result.get("status") == "ended":
                print(
                    json.dumps(
                        {
                            "status": "ended_with_fallback",
                            "session_error": loaded,
                            "fallback": fallback_result,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                sys.exit(0)

            print(
                json.dumps(
                    {
                        "status": "error",
                        "reason": "end_session_and_fallback_failed",
                        "session_error": loaded,
                        "fallback": fallback_result,
                        "hint": "请检查 session 文件路径；若 fallback 为 buffer_empty，说明本轮 pair 未成功缓存。",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(1)

        result = end_daily_log(topics, source_messages=loaded.get("messages", []))
        result["session_file"] = loaded.get("path")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "end-auto":
        raw_args = sys.argv[2:] if len(sys.argv) > 2 else []

        # 支持可选参数：--history-file <path>
        history_file = ""
        topics = []
        idx = 0
        while idx < len(raw_args):
            token = raw_args[idx]
            if token == "--history-file" and idx + 1 < len(raw_args):
                history_file = raw_args[idx + 1]
                idx += 2
                continue
            topics.append(token)
            idx += 1

        # 主路径：优先消费 buffer
        primary_result = end_daily_log(topics)
        if primary_result.get("status") == "ended":
            print(json.dumps(primary_result, ensure_ascii=False, indent=2))
            sys.exit(0)

        # 第一备用：优先使用实时 history 导出文件（由上层 sessions_history 工具生成）
        if history_file:
            loaded_from_history = load_round_messages_from_session_file(history_file)
            if loaded_from_history.get("status") == "ok":
                result = end_daily_log(topics, source_messages=loaded_from_history.get("messages", []))
                result["status"] = "ended_with_history_backup"
                result["primary"] = primary_result
                result["history_file"] = loaded_from_history.get("path")
                print(json.dumps(result, ensure_ascii=False, indent=2))
                sys.exit(0)

        # 备用路径：buffer 不可用时再尝试 session 文件
        resolved = resolve_session_file_from_index()
        if resolved.get("status") != "ok":
            print(
                json.dumps(
                    {
                        "status": "error",
                        "reason": "end_auto_primary_and_session_resolve_failed",
                        "primary": primary_result,
                        "session_resolve_error": resolved,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(1)

        loaded = load_round_messages_from_session_file(resolved.get("session_file", ""))
        if loaded.get("status") != "ok":
            print(
                json.dumps(
                    {
                        "status": "error",
                        "reason": "end_auto_primary_and_session_read_failed",
                        "primary": primary_result,
                        "session_resolved": resolved,
                        "session_error": loaded,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(1)

        result = end_daily_log(topics, source_messages=loaded.get("messages", []))
        result["status"] = "ended_with_session_backup"
        result["primary"] = primary_result
        result["session_file"] = loaded.get("path")
        result["session_key"] = resolved.get("session_key")
        result["sessions_index"] = resolved.get("index")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "user":
        msg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        result = append_user_message(msg)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "assistant":
        msg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        result = append_assistant_message(msg)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "pair":
        user_msg = sys.argv[2] if len(sys.argv) > 2 else ""
        assistant_msg = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        result = log_message_pair(user_msg, assistant_msg)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "status":
        result = get_recording_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "check":
        result = check_and_fix_daily_structure()
        print(json.dumps(result, ensure_ascii=False, indent=2))

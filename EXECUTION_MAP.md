# Skill 执行路由表

## 定义
- **AI自由发挥** ：需要创意、上下文理解或自然语言处理的步骤
- **脚本严格执行** ：确定性、幂等、数据转换的操作，在 diary_logger.py 中自动处理

---

## 启动阶段（start trigger 触发）

| 步骤 | 执行者 | 处理逻辑 | 代码位置 |
|------|-------|--------|---------|
| 检测触发词 ("讲故事"/"开始讲故事") | 脚本 | 使用 `validate_start_trigger()` 识别 | diary_logger.py:37-43 |
| **生成角色化回复** | **AI 自由发挥** | **按 OpenClaw 角色自然聊天，不提流程信息** | **.instructions.md 第6-10行** |
| 调用 start 子命令 | 脚本 | 执行 `python3 diary_logger.py start` | SKILL.md 第二章 |
| 初始化文件框架 | 脚本 | 创建 YAML front matter, # 话题, # 对话记录 | diary_logger.py:339-350 |
| 更新状态 recording=true | 脚本 | 调用 `start_recording(date, [])` | state_manager.py |
| 缓存首轮对话对（兜底） | 脚本 | 执行 `python3 diary_logger.py pair "[用户]" "[AI回复]"` | diary_logger.py |

---

## 中间轮次（持续对话）

| 步骤 | 执行者 | 处理逻辑 | 代码位置 |
|------|-------|--------|---------|
| 接收用户消息 | 脚本 | 监听输入 | - |
| **生成角色化回复** | **AI 自由发挥** | **按角色自然聊天，遵循对话风格** | **.instructions.md 第6-10行** |
| 缓存本轮对话对（兜底） | 脚本 | 执行 `python3 diary_logger.py pair "[用户]" "[AI回复]"` | diary_logger.py |

---

## 结束阶段（stop trigger 触发）

| 步骤 | 执行者 | 处理逻辑 | 代码位置 |
|------|-------|--------|---------|
| 检测结束触发词 ("停止讲故事"/"不讲了") | 脚本 | 使用 `validate_stop_trigger()` 识别 | diary_logger.py:45-51 |
| **生成最后一句 AI 回复** | **AI 自由发挥** | **符合角色的自然结尾，不主动说"已记录"** | **.instructions.md 第33-36行** |
| **生成本轮话题关键词** | **AI 自由发挥** | **默认 1 个；两件事提 2 个；最多 3 个** | **.instructions.md** |
| 缓存最后一轮对话对（兜底） | 脚本 | 执行 `python3 diary_logger.py pair "[用户]" "[AI回复]"` | diary_logger.py |
| 自动解析当前 sessionFile | 脚本 | 从 OpenClaw `sessions.json` 读取最新可用 `sessionFile` | diary_logger.py |
| 调用 end-auto 子命令传递话题 | 脚本 | 执行 `python3 diary_logger.py end-auto [话题...]` | diary_logger.py |
| **[脚本内部流程开始 - 全自动]** | | | |
| 从会话 JSON 切片最近一轮 | 脚本 | `_slice_latest_round_from_history()` 仅保留开始触发词到结束触发词之间消息 | diary_logger.py |
| 清理触发词 | 脚本 | `strip_trigger_words()` 移除首尾的触发词 | diary_logger.py:53-82 |
| 渲染为日记行格式 | 脚本 | `_render_buffered_lines()` 生成 `- **HH:MM** {USER_NAME}：...` | diary_logger.py:289-299 |
| 追加到文件 # 对话记录 | 脚本 | `_append_lines_to_conversation_section()` 插入对话 | diary_logger.py:203-232 |
| **自动追加分割线** | 脚本 | 在末尾追加 `----` | diary_logger.py:475-477 |
| **提取已有话题** | 脚本 | `_extract_existing_topics()` 从文件读取旧话题 | diary_logger.py:152-172 |
| **话题去重 (语义比对)** | 脚本 | `_normalize_topic_text()` 规范化 + `_topics_semantically_same()` 比对 | diary_logger.py:175-200 |
| **去重逻辑：若新话题与旧话题语义相同，则不添加** | 脚本 | `end_daily_log()` 在第475-480行执行 | diary_logger.py:475-480 |
| **更新 # 话题 区块** | 脚本 | `_upsert_primary_topics_section()` 替换或新建 | diary_logger.py:248-285 |
| **清空缓存** | 脚本 | `stop_recording()` 重置 buffered_messages | state_manager.py |
| **返回脚本执行结果** | 脚本 → AI 显示 | 显示文件路径、写入数量、话题列表 | diary_logger.py:482-483 |
| **[脚本内部流程结束]** | | | |
| 通知用户脚本执行结果 | **AI** | **必须告知成功/失败、记录路径（end-session 或 end）、写入条数或失败原因、topics、duplicate_topics** | **.instructions.md** |
| **写回 OpenClaw 记忆** | **AI 自由发挥** | **从本轮对话提取 1-3 条可跨天复用的事实** | **.instructions.md 第39-42行** |
| end-auto 失败时回退 | 脚本 | 先尝试 `end-session`（手动路径），再执行 `python3 scripts/diary_logger.py end [话题...]` | .instructions.md |

---

## 关键约束检查

### ✅ 脚本端严格执行的操作（用户不需要操心）
1. 文件结构管理（目录、front matter、标题）
2. 每轮 pair 兜底缓存（user/assistant 原文）
3. 会话原文切片（开始触发词到结束触发词）
4. 触发词清理（自动从 # 对话记录 中移除）
5. 分割线追加（自动在每轮末尾）
6. **语义去重**（自动比对旧话题，避免重复）
7. 话题合并顺序（脚本确保去重后再写入）

### ⚠️ AI 中间有误操作的风险点
1. **话题生成时包含重复**（e.g., 生成"散步"和"今天的散步"）
   - 脚本会自动去重，所以不会真正重复写入
   - 但 AI 应该自己避免这种低效
2. **AI 回复时主动说"已开始记录"或"已结束"**  
   - 脚本不检查这个，必须靠 AI 自律遵循 .instructions.md

### 🔒 AI 绝对不能做的事
1. 手动写文件、修改 markdown（脚本负责所有文件 I/O）
2. 生成分割线、更新话题结构（脚本自动处理）
3. 改写用户消息或 AI 回复内容（必须原样记录）
4. 在非对话阶段润色、压缩、补写历史正文
5. 调用除 `diary_logger.py start/end-session/end/check` 以外的脚本

---

## 命令时序参考

```bash
# 启动
python3 scripts/diary_logger.py start

# 结束（优先，自动解析会话路径）
python3 scripts/diary_logger.py end-auto "话题1" "话题2" "话题3"

# 结束（次优，手动指定会话路径）
python3 scripts/diary_logger.py end-session ./session.json "话题1" "话题2" "话题3"

# 结束（回退，原文不可用时）
python3 scripts/diary_logger.py end "话题1" "话题2" "话题3"

# 可选检查
python3 scripts/diary_logger.py check
```

---

## 代码验证清单

- [x] `validate_start_trigger()` 脚本端检测：仅处理"讲故事"/"开始讲故事"
- [x] `validate_stop_trigger()` 脚本端检测：仅处理"停止讲故事"/"不讲了"  
- [x] `strip_trigger_words()` 脚本端清理：自动移除触发词及周围标点
- [x] `_slice_latest_round_from_history()` 会话切片：只记录开始触发词到结束触发词范围
- [x] `_normalize_topic_text()` 去重预处理：统一大小写、删除标点、移除冗余前缀后缀
- [x] `_topics_semantically_same()` 语义比对：70% 字符重叠 + 包含检测
- [x] `end_daily_log()` 去重循环：在第 475-480 行先去重再写入
- [x] 分割线自动追加：在第 476 行由脚本判断是否需要追加 `----`
- [x] 话题更新：在第 480 行调用 `_upsert_primary_topics_section()` 后才写入文件

---

## 结论

**AI 的职责范围（仅限这两项可自由发挥）：**
1. 每轮对话中根据角色生成自然回复
2. 结束时从本轮对话中自由提炼 1-3 个核心话题

**其他所有步骤由脚本严格执行，包括但不限于：**
- 触发检测、状态管理、消息缓存
- 触发词清理、分割线追加、文件 I/O
- 话题去重、语义比对、最终落盘
- 内存读写（如已实现，由 .instructions.md 约束）

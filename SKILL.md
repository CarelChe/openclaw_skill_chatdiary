---
name: ChatDiary
description: "讲故事对话日记 skill。用户以'讲故事'或'开始讲故事'触发开始；以'不讲了'或'停止讲故事'触发结束；记录中按 OpenClaw 提供的角色设定进行一问一答式聊天，并在结束时把本轮对话写入 Obsidian 日记库当天文件，更新 # 话题，追加 ---- 分割线。"
---

# ChatDiary Skill

## 目标

把用户的“讲故事”对话变成一轮完整的故事聊天，并在结束时落盘到 Obsidian 的当天日记文件中。

核心原则：记录源必须优先来自会话原文（sessions_history / session logs），而不是 AI 二次复述。

## 触发规则

- 开始：用户消息开头包含“讲故事”或“开始讲故事”。
- 开始：用户消息只要以“讲故事”或“开始讲故事”开头即可，后面可以直接接标点和正文，例如“开始讲故事，今天天气很好”也算触发。
- 结束：用户消息结尾包含“不讲了”或“停止讲故事”。
- 触发词只用于状态判定，不写入正文。

## 对话规则

- skill 开始后，按 OpenClaw 提供的角色设定回复用户。
- 对话风格固定为：像非常要好的朋友，不啰嗦，理性、有自己的主见，不随意恭维或附和，会从多角度帮助用户分析问题。
- 在重要话题（关系、长期目标、重大决策、持续情绪）上，主动提出有深度的问题，引导用户继续聊下去。
- 每次回复前，先读取 OpenClaw 记忆中与该用户相关的近期事实（如昨天提到的人、事、计划、情绪），确保上下文连续。
- 用户发一句，AI 回一句，算一次对话。
- 从 skill 被触发到结束，视为一轮对话。
- 回复保持自然聊天口吻，不输出内部流程、状态提示或脚本细节。
- 对话阶段允许 AI 正常回复；非对话写入阶段不允许 AI 改写、压缩、润色任何历史对话正文。

## 记忆规则

- 对话中若出现可跨天延续的事实（计划、关系、偏好、阶段性目标、关键事件），要写入 OpenClaw 记忆。
- 结束一轮后，至少同步 1-3 条高价值记忆，避免“昨天说过，今天忘了”。
- 记忆内容用短句，保留可复用事实，不记录冗余寒暄。

## 结束规则

当检测到结束触发词时：

1. 先生成并发送本轮最后一句 AI 回复。
2. 再生成本轮话题关键词：
	- 默认提取 1 个核心话题。
	- 若本轮明确讨论了 2 件事，则提取 2 个话题。
	- 每轮最多提取 3 个话题。
3. 优先从 sessions_history / session logs 拉取当前会话原文，切出“开始触发词到结束触发词”之间的最近一轮完整对话。
4. 调用结束脚本，将这轮原文一次性写入当天文件。
5. 文件若不存在，则在 Obsidian 笔记库的“日记”文件夹下新建 `yyyy-mm-dd.md`。
6. 结束脚本会在对话记录末尾追加 `----`。
6. 结束脚本会把话题更新到文件最开始的 `# 话题` 区块，并先做语义去重；如果新话题和旧话题表达的是同一件事，就不要再重复更新。
7. 完成后必须通知用户执行结果，内容至少包含：
	- 是否完成记录（成功/失败）
	- 通过哪条路径完成（end-session 会话原文 / end 缓存回退）
	- 写入条数或失败原因
	- 本轮提取了哪些话题
	- 哪些话题被判定为语义重复并去重

## 脚本约定

- 开始阶段仍使用 `scripts/diary_logger.py start` 开启录制状态。
- 每轮对话都调用 `scripts/diary_logger.py pair <用户消息> <AI回复>` 做兜底缓存（即使主路径最终走 end-session）。
- 默认缓存落盘阈值为 2（约等于每轮 user+assistant 完成后就分段写入一次）。
- 结束阶段优先使用 `scripts/diary_logger.py end-auto <话题...>` 落盘（先消费 buffer 缓存）。
- 若 buffer 不可用，`end-auto` 先使用 sessions_history 导出的实时 history 文件作为第一备用。
- 若 history 备用不可用，`end-auto` 再把 session 文件作为第二备用路径。
- 如需手动指定会话路径，再使用 `scripts/diary_logger.py end-session <session_json_path> <话题...>`。
- 结束后可运行 `scripts/diary_logger.py check` 做结构自检。

## 脚本自动处理的步骤（AI 无需操心）

一旦调用 `python3 scripts/diary_logger.py end-auto [话题...]`，以下操作全部由脚本负责完成：

- ✅ 先把 buffer 中未落盘消息写入当天文件
- ✅ 若 buffer 为空或主路径失败，优先读取 sessions_history 导出的实时 history 文件（若已提供）
- ✅ 若 history 备用失败，再自动解析 `sessions.json` 并读取 `sessionFile` 作为第二备用
- ✅ 从会话 JSON 中提取最近一轮“开始触发词 -> 结束触发词”之间的全部 user/assistant 消息（仅备用路径）

如需手动路径，也可调用 `python3 scripts/diary_logger.py end-session [session_json_path] [话题...]`，后续流程一致：

- ✅ 自动从消息中清除开始/停止触发词及周围标点
- ✅ 按 `- **HH:MM** {USER_NAME}：...` 格式渲染并写入文件；消息内容按单行拆分，空行（`\n`）不产生记录行，靠上下行时间戳体现间隔
- ✅ 在对话末尾自动追加 `----` 分割线
- ✅ 从文件现有内容中提取已记录的话题列表
- ✅ 对新话题与已有话题进行字符级语义去重（70% 相似度阈值）
- ✅ 若新话题表达同一件事（如"散步" vs "今天的散步"），则不重复添加
- ✅ 更新文件最开头的 `# 话题` 区块
- ✅ 清空状态文件中的缓存消息队列

回退路径（仅当会话原文不可用时）：

- 使用 `python3 scripts/diary_logger.py end [话题...]`
- 从缓存读取消息并落盘
- 仍保持相同日记格式与话题更新逻辑

兜底缓存策略：
- 语义类似的话题不会重复写入 `# 话题`，并在结束通报中标明为“重复话题”。
## 记录源优先级（最关键）

**为完全避免数据丢失，end-auto 会按以下优先级尝试记录源：**

1. **Buffer**（主路径）：本地缓存，通过 pair 命令积累
	- 问题：pair 命令可能未被执行 → buffer 为空
	- 优点：最快速，本地可靠
   
2. **--history-json** 参数（第一备用，推荐）：sessions_history 工具直接返回的 JSON
	- **完全实时**，来自 OpenClaw 内存，**不依赖任何文件异步刷盘**
	- AI 调用 `sessions_history(sessionKey, limit, includeTools=false)` 工具获取当前会话消息
	- 通过 `--history-json '<json_string>'` 参数直接传给脚本
	- 无需手动写文件，完全避免文件系统延迟
   
3. **--history-file** 参数（第二备用）：sessions_history 工具导出到文件
	- 如果 --history-json 不可用，可先导出为文件再传
	- 通过 `--history-file <path>` 参数指定文件路径
	- 略低于 --history-json（涉及文件 I/O）
   
4. **自动 session 文件**（第三备用）：从 sessions.json 自动解析
	- 作为最后的保障，脚本会自动查找 ~/.openclaw/agents/main/sessions/sessions.json
	- 读取最新会话的 sessionFile 路径
	- 问题：可能延迟（文件未实时刷盘），但比无数据强

## 端到端例子

```bash
# 1. 启动
python3 scripts/diary_logger.py start

# 2. 对话轮次（本轮通常不需要调用 pair，因为 sessions_history 会处理）
# 用户和 AI 正常对话...

# 3. 结束时：AI 调用 sessions_history 工具 → 获得 JSON → 传给 end-auto
HISTORY_JSON='{"messages": [{"role": "user", "content": "讲故事，..."}, {"role": "assistant", "content": "好的，..."}]}'
python3 scripts/diary_logger.py end-auto --history-json "$HISTORY_JSON" "话题1" "话题2"
```
pair 执行硬约束：

- 每轮用户消息 + AI 回复之后，`pair` 必须调用且返回成功。
- 若 `pair` 调用失败，必须立即重试一次；仍失败则向用户通报“缓存失败”，并在结束时优先走 history 备用路径。

	✅ 先把 buffer 中未落盘消息写入当天文件
	✅ 若 buffer 为空，优先尝试 --history-json 参数（最实时）
	✅ 若 history-json 不可用，再尝试 --history-file 参数
	✅ 若 history 都不可用，最后自动解析 sessions.json 作为保障
2. 结束前从本轮对话中自由提炼 1-3 个核心话题关键词
3. 结束后向用户通报记录结果（成功/失败、记录路径、写入条数、重复话题）

如需手动路径，也可调用 `python3 scripts/diary_logger.py end-session <session_json_path> <话题...>`，后续流程一致：

- 一轮记录的有效范围：从用户消息开头命中“讲故事/开始讲故事”开始，到用户消息结尾命中“不讲了/停止讲故事”结束。
- 该范围内的 user/assistant 消息必须完整保留、按原顺序写入，不得跳过、合并、改写。
- 若触发词出现在边界句：
	- 开始句：删除句首触发词后记录其余正文。
	- 结束句：删除句尾触发词后记录其余正文。

## 角色来源

详细角色设定来自 OpenClaw 提供的角色上下文。这份内容是对话风格的唯一来源。

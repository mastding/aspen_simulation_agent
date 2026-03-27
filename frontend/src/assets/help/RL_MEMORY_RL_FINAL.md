# 记忆系统与 RL 优化最终实现说明

## 1. 文档目的

本文档用于总结 `aspen_simulation_new` 当前已经落地的两类优化：

1. 记忆系统优化
2. 强化学习（RL）训练与奖励优化

本文档只描述当前仓库里已经实现并接入主链路的内容，不描述未落地设想。

## 2. 当前实现总览

当前系统已经从最初的“规则检索 + 基础 reward”升级为以下结构：

### 2.1 记忆系统

- 规则字段提取
- 语义画像 `semantic_profile`
- 分层匹配 `must / anchor / should`
- 动态方法词表 `dynamic_method_aliases`
- 保守版动态组分词表 `dynamic_component_aliases`
- 检索前保守 `query enrichment`
- 基于 `memory_usage_events` 的质量重排
- 低质量记忆候选预览与审查
- 记忆页与运行详情页联动排查

### 2.2 RL 系统

- reward v2
- failure taxonomy
- task-specific validators
- family-specific validators
- task-template validators
- 训练摘要接入 failure categories / validator gaps / memory quality
- prompt 增量生成接入这些训练信号
- 训练页可直接查看增量来源与样本链路

---

## 3. 记忆系统最终实现

## 3.1 记忆检索主链路

核心文件：
- `backend/app/memory/matching.py`
- `backend/app/memory/pipeline_ops.py`
- `backend/app/memory/storage_ops.py`
- `backend/app/memory/core_ops.py`

当前记忆检索不是向量数据库方案，也不是纯 LLM 检索，而是：

1. 从 query 中提取 `match_fields`
2. 构建 `semantic_profile`
3. 做分层结构匹配
4. 叠加词法分
5. 叠加语义分
6. 叠加质量分
7. 最终重排返回候选记忆

## 3.2 规则字段提取

当前提取字段主要包括：

- `methods`
- `equipment`
- `equipment_ids`
- `streams`
- `ops`
- `flow`
- `components`

这些字段主要来自：
- 词表
- 正则
- 别名归一化

其中：
- `equipment_ids` 优先识别显式设备实例
- `streams` 优先识别显式流股 token
- `methods` 识别物性方法
- `components` 识别组分及别名

## 3.3 语义画像 `semantic_profile`

当前每条记忆和每次 query 还会构建 `semantic_profile`，内容包括：

- `task_title`
- `task_type`
- `task_family`
- `entities`
- `actions`
- `control_variables`
- `expected_outputs`
- `constraints`
- `query_expansion_terms`
- `summary_text`

语义画像的作用是：
- 不是替代规则匹配
- 而是在结构字段之外提供额外语义重排能力

## 3.4 分层匹配

当前不再使用早期“多个字段全硬匹配”的方式，而是：

- `must`
  - `equipment_ids`
- `anchor`
  - `equipment`
  - `streams`
- `should`
  - `ops`
  - `components`
  - `flow`
  - `methods`

输出包括：
- `must_passed`
- `anchor_passed`
- `should_score`
- `ranking_score`
- `structured_match_score`

这解决了早期“只要一个操作词没写全就误杀相关记忆”的问题。

## 3.5 动态方法词表

新增表：
- `dynamic_method_aliases`

已实现能力：
- 记忆写入时自动发现新方法候选
- 候选经过多次出现后升级为 `validated`
- 已验证方法会参与后续方法提取和检索重排
- 已提供回填脚本与指标统计

解决的问题：
- 新物性方法不再只能靠人工改代码词表
- 修复了 `ELECNRTL` / `NRTL-HOC` 被错误识别成 `NRTL` 的问题

## 3.6 保守版动态组分词表

新增表：
- `dynamic_component_aliases`

当前实现策略是保守版：
- 只接受高置信的显式组分候选
- 先接入特征提取和重排
- 不进入强过滤链路

已提供：
- 回填脚本
- 指标统计
- 审查页 approve / reject
- 批量审核

## 3.7 Query Enrichment

当前在调用 `memory_search_experience` 后端检索前，会做保守型 `query enrichment`。

目标：
- 不依赖 agent 自己把 query 写完整
- 系统侧补充部分结构信息

当前已补内容包括：
- `task_type`
- 部分 canonical `equipment`
- 已验证的动态 `methods`
- 已验证的保守 `components`

原则：
- 只做保守补充
- 优先加分和重排
- 避免误判导致强过滤误杀

## 3.8 记忆质量重排

当前记忆排序不再只看：
- 关键词
- 语义
- reward

现在已经接入基于 `memory_usage_events` 聚合出的质量信号：

- `retrieved_count`
- `applied_count`
- `success_after_use`
- `success_rate`
- `avg_reward_after_use`
- `recency_days`

这些信号会形成 `quality_score`，进入最终排序。

当前实现效果：
- 高质量记忆更容易排前
- 低质量记忆不直接删除，但会降权

## 3.9 低质量记忆候选预览

当前 `/api/memory/quality` 已支持返回：

- `memory_usage_stats_total`
- `memory_usage_stats_retrieved_total`
- `memory_usage_stats_applied_total`
- `memory_usage_stats_success_total`
- `memory_usage_stats_avg_reward_after_use`
- `low_quality_candidates`

前端记忆页已接入低质量候选展示与跳转。

## 3.10 记忆系统前端观测

当前前端已经支持：

- 运行详情页查看本次命中的记忆
- 运行详情页查看 `memory_search_experience`
- 运行详情页查看 `memory_get_experience`
- 从运行详情跳到记忆页
- 记忆页按 `rollout_id` 过滤
- alias 审查页查看来源 rollout 与示例文本
- alias 批量 approve / reject

---

## 4. RL 优化最终实现

## 4.1 reward v2

核心文件：
- `backend/app/rl/reward.py`
- `backend/app/services/chat_execution_service.py`

当前 reward v2 已经不是只基于工具调用次数，而是综合：

- `base_reward`
- `result_accuracy`
- `time_efficiency`
- `memory_utilization`
- `failure_penalty`
- `task_specific_score`

## 4.2 failure taxonomy

当前已引入 failure taxonomy，并贯穿：

- `tool_execution`
- `task_progress`
- `error` span
- `reward` span
- 训练摘要

常见分类包括：
- `simulation_config_error`
- `simulation_timeout`
- `simulation_connection_error`
- `simulation_remote_error`
- `simulation_runtime_error`
- `result_fetch_error`
- `result_timeout`
- `result_format_error`
- `schema_generation_error`
- `memory_tool_error`

当前 reward 已按失败类型施加不同惩罚权重。

## 4.3 task-specific validators

reward 当前已经支持任务型 validator。

`validator_profile` 中会描述：
- `families`
- `task_templates`
- `asks_change`
- `asks_query`
- `asks_calculation`
- `expects_simulation`
- `expects_result`
- `requested_outputs`
- `query_only`

`validator_scores` 中会记录具体 validator 得分。

## 4.4 family-specific validators

当前 family-specific validator 已覆盖：

- `separation_delivery`
- `mixing_delivery`
- `heat_exchange_delivery`
- `pressure_change_verification`

并与基础 validator 共同使用：
- `simulation_execution`
- `result_retrieval`
- `change_closed_loop`
- `process_round_completion`

## 4.5 task-template validators

当前又进一步细化到任务模板级别：

- `result_query`
- `parameter_change`
- `unit_calculation`
- `process_execution`

这使得 reward 能区分：
- 查询类任务不应强制要求重跑仿真
- 修改参数类任务必须形成“修改-运行-取结果”闭环
- 单元计算类任务必须真正交付目标结果
- 流程类任务必须完成轮次或阶段

## 4.6 训练摘要接入 failure taxonomy / validator gaps

核心文件：
- `reinforcement_learning/src/train_offline_and_generate_prompts.py`

训练摘要当前已包含：
- `top_failure_categories`
- `failure_category_count`
- `progress_stage_count`
- `top_validator_gaps`
- `validator_gap_count`

这些信号会用于：
- 训练报告
- prompt 增量生成
- APO 候选评分
- 前端训练页展示

## 4.7 训练摘要接入记忆质量信号

当前训练脚本还会读取 `memory_usage_events`，汇总：

- `total_usage_events`
- `rollouts_with_memory_hits`
- `avg_hit_rank`
- `avg_match_score`
- `memory_quality_bands`
- `high_quality_hit_success_rate`
- `low_quality_hit_success_rate`
- `top_hit_memories`
- `memory_hit_rollout_samples`

这些信息已经开始影响：
- 训练摘要
- prompt 增量生成
- APO 候选评分

## 4.8 prompt 增量来源审计

当前训练结果新增：
- `prompt_increment_rationale`

每条记录包含：
- `target`
- `bullet`
- `reasons`
- `evidence`
- `failure_categories`
- `validator_gaps`
- `memory_signals`

这意味着现在不仅知道“生成了哪些增量”，还知道：
- 为什么生成
- 对应了哪些失败模式
- 对应了哪些 validator gap
- 是否由低质量记忆命中所推动

---

## 5. 前端观测与排查闭环

## 5.1 运行详情页

当前运行详情页已支持展示：

- Reward Breakdown
- Validator Profile
- Validator Scores
- Failure Categories
- Progress Timeline
- Memory Search Results
- Memory Fetch Details

## 5.2 训练页

当前训练页已支持展示：

- Success Rate
- Avg Reward
- Top Failure Categories
- Top Validator Gaps
- Memory Usage Summary
- Top Hit Memories
- Failure Rollout Samples
- Why These Prompt Increments
- Prompt Increment Rationale

并支持直接跳转：
- `/runs/{rollout_id}`
- `/memory?...`

因此现在可以从训练结果一路排查到：
- 哪个 rollout 失败
- 哪条记忆被频繁命中
- 哪种 failure category 在主导训练信号
- 哪个 validator gap 在推动 prompt 增量

---

## 6. 当前版本的结论

### 6.1 记忆系统

当前记忆系统已经从“静态规则匹配”升级为：

- 规则抽取
- 语义增强
- 动态词表自增长
- 历史质量重排
- 低质量候选审查

这已经是一个可解释、可观测、可持续迭代的版本。

### 6.2 RL 系统

当前 RL 系统已经从“基础 reward + 离线训练”升级为：

- 多维 reward v2
- failure taxonomy
- task-specific / family-specific / template-specific validators
- 训练摘要接入 failure / validator / memory quality 三类信号
- prompt 增量来源可审计
- 训练页与运行/记忆排查链路打通

这已经达到当前项目阶段一个完整、可用、可审计的版本。

---

## 7. 后续可选优化

以下属于后续增强，不属于当前主干缺口。

### 7.1 记忆系统

- 将动态组分候选从保守模式扩展到更广的中文别名发现
- 引入 `stream_roles / numeric_constraints / result_targets` 的更细粒度语义增强
- 进一步做记忆冲突检测与合并

### 7.2 RL 系统

- APO 候选去重与评分缓存
- 更细的模板化 validator
- 基于真实训练 run 的批量回归验收
- 将 `prompt_increment_rationale` 写入帮助中心与操作手册

---

## 8. 相关主要文件

### 8.1 记忆系统
- `backend/app/memory/matching.py`
- `backend/app/memory/pipeline_ops.py`
- `backend/app/memory/storage_ops.py`
- `backend/app/memory/core_ops.py`
- `backend/app/services/memory_api_service.py`
- `frontend/src/views/MemoryView.vue`
- `frontend/src/views/RunDetailView.vue`
- `frontend/src/views/RunsView.vue`

### 8.2 RL 与训练
- `backend/app/rl/reward.py`
- `backend/app/services/chat_execution_service.py`
- `reinforcement_learning/src/train_offline_and_generate_prompts.py`
- `frontend/src/views/TrainingView.vue`

## 9. 文档结论

当前仓库里的记忆优化和 RL 优化已经不再是零散 patch，而是形成了统一闭环：

- 在线执行侧有可观测信号
- 记忆系统有动态增长和质量重排
- 训练侧能消费 failure / validator / memory quality 信号
- 前端可以从训练结论直接跳回运行与记忆细节做排查

因此，当前版本已经具备较强的工程可用性与可解释性。

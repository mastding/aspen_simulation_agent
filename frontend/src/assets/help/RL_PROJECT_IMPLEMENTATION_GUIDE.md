# RL 训练与记忆系统实现指南（按当前项目实际调用链路）

## 目录
1. [系统架构概览](#系统架构概览)
2. [记忆系统详解](#记忆系统详解)
3. [RL 训练流程](#rl-训练流程)
4. [强化学习算法](#强化学习算法)
5. [完整示例](#完整示例)

---

## 系统架构概览

本系统是一个面向化工流程模拟的智能助手，后端主入口为 `backend/main_with_rl.py`，核心能力包括：
- 在线任务执行（SSE 流式）
- 历史经验记忆沉淀与检索
- RL 采样与离线训练（RGO/APO）
- 训练产物评审与发布

### 核心组件

```text
backend/
├── app/memory/          # 记忆系统
│   ├── extractors.py    # 从 spans 提取策略/配置/错误链
│   ├── matching.py      # 结构字段抽取与匹配
│   ├── storage_ops.py   # 记忆入库 + md 文档落盘
│   └── pipeline_ops.py  # 自动沉淀与检索
├── app/rl/
│   └── reward.py        # 奖励计算
├── app/services/
│   ├── chat_execution_service.py  # 在线执行主流程
│   ├── rl_job_service.py          # RL 任务管理
│   ├── rl_worker_service.py       # RL 任务执行
│   └── training_process_service.py# 训练子进程
└── app/training/
    └── artifacts.py     # 训练产物对比与发布概览
```

---

## 记忆系统详解

## 2.1 记忆提取（Memory Extraction）

提取逻辑来自真实执行轨迹 `spans`，重点函数位于 `backend/app/memory/extractors.py`：

- `extract_strategy_from_spans(...)`：提取思路与关键回复片段。
- `extract_config_snippet_from_spans(...)`：提取 `run_simulation` 配置片段。
- `extract_run_simulation_attempts_from_spans(...)`：提取失败重试链。
- `extract_pitfall_details_from_spans(...)`：提取失败原因、修复动作、经验教训。
- `extract_reward_and_tool_count(...)`：提取 reward 与工具调用次数。

## 2.2 记忆存储（Memory Storage）

存储模块：`backend/app/memory/storage_ops.py`

### 存储形态

1. **SQLite 结构化记录**  
   表：`memory_cases`、`memory_documents`、`memory_usage_events`
2. **Markdown 经验文档**  
   路径：`backend/rl_data/memory_docs/{memory_id}.md`

### 存储操作

- `upsert_memory_case(...)`：按 task_hash 幂等更新记忆。
- `write_memory_markdown_and_index(...)`：生成 md 内容并同步索引。
- `backfill_memory_documents(...)`：历史补全 md 文档与特征。

## 2.3 记忆检索（Memory Retrieval）

检索主逻辑：`backend/app/memory/pipeline_ops.py::search_memory_cases`

### 检索策略（实际实现）

1. 从 `memory_cases` 读取候选（按更新时间，最多 1500 条）。
2. 抽取查询与候选的结构字段：
   - 设备、物流、操作、组分、方法等（`matching.extract_match_fields`）
3. 若查询包含结构化约束，先执行硬/软匹配过滤（`match_required_fields`）。
4. 词法加权打分：
   - token 命中
   - exact query 命中
   - task_type boost
   - memory_kind boost
   - reward boost
5. 按 `unit/process` 做多样化选取后返回 `top_k`。

### 重要说明

- 当前实现**没有接入向量数据库**。
- 当前实现**没有 embedding 检索链路**。
- 检索是“结构匹配 + 词法打分 + 类型编排”。

## 2.4 记忆管道（Memory Pipeline）

在线任务结束后自动触发记忆沉淀（`chat_execution_service` -> `auto_upsert_memory_from_rollout`）：

1. 读取 rollout spans。
2. 计算 reward 与仿真指标。
3. 若 reward 低于阈值则跳过。
4. 生成并 upsert 多种记忆类型：
   - `success_golden`
   - `success_recovered`
   - `process_global`
   - `process_stage`
   - `pitfall_recovery`
   - `pitfall_failure`
5. 写入 SQLite 与 md 文档。

---


## 2.5 语义画像与分层检索（2026-03 第一版）

当前项目已在原有规则字段基础上，新增 `semantic_profile` 结构，并写入 `memory_cases.features_json`。

### semantic_profile 结构

新增字段包括：
- `task_title`：任务标题
- `task_type`：`unit/process`
- `task_family`：任务家族，如 `mixing_calculation`、`pressure_adjustment_task`
- `entities`：设备类型、设备实例、输入/输出流股、组分、物性方法
- `actions`：关键动作，如 `mix_streams`、`modify_conditions`
- `expected_outputs`：预期输出，如 `product_temperature`、`component_composition`
- `query_expansion_terms`：检索扩展词

### 当前检索逻辑

`backend/app/memory/pipeline_ops.py::search_memory_cases` 现已改为：

1. 先抽取 query 的 `match_fields` 与 `semantic_profile`。
2. 对每条 memory 读取 `features_json` 中的 `match_fields` 与 `semantic_profile`。
3. 结构匹配改成三层：
   - `must`：`equipment_ids`
   - `anchor`：`equipment`、`streams`
   - `should`：`ops`、`components`、`flow`、`methods`
4. 计算 `structured_match_score`。
5. 计算 `semantic_score`。
6. 最终与词法命中、`memory_kind`、`reward` 一起重排。

### 与旧逻辑的差异

旧逻辑的问题是：`ops/components` 也作为硬过滤条件，导致大量“对象一致但描述不完全一致”的经验被提前过滤。

现在的改法是：
- 设备实例仍然是强约束
- 设备类型与流股作为锚点
- 操作词、组分、方法改成加分项
- 当结构匹配略弱但语义画像高度相似时，允许候选进入重排

### 当前边界

这一版仍然是“规则增强的语义画像”，不是 LLM 在线抽取，也不是向量数据库检索。
其目标是先在不引入线上额外模型依赖的前提下，提高召回与重排稳定性。

## RL 训练流程
## 3.1 训练任务生命周期

状态流转（`rl_job_service.py` + `rl_worker_service.py`）：

```text
queued -> running -> completed
                 -> failed
                 -> stopped
```

阶段流转：

```text
collecting -> training -> done
```

## 3.2 采样阶段（Collection）

两种采样模式：

1. `internal`  
   后端直接循环调用 `execute_user_task(...)`。
2. `script_sse`  
   启动 `reinforcement_learning/src/collect_online_trajectories.py`，通过 `/api/chat/stream` 收集 rollout。

## 3.3 奖励计算（Reward Calculation）

实现：`backend/app/rl/reward.py::calculate_reward(...)`

奖励由以下维度组成：
- 完成度（completion/progress）
- 效率（重试或额外调用的衰减项）
- 恢复能力（失败后恢复成功）
- 工具链完整性（schema/result）
- 错误惩罚（config/runtime/unknown）

说明：工具调用次数只影响效率项，不是唯一评价标准。

## 3.4 训练阶段（Training）

训练子进程由 `training_process_service.py` 启动：

- `--algo rgo`
- `--algo apo --apo-iters --apo-sample-size --apo-exploration`

实际训练脚本：
- `reinforcement_learning/src/train_offline_and_generate_prompts.py`

主要产物目录：

```text
reinforcement_learning/outputs/training_runs/run_xxx/
├── training_result.json
├── training_report.md
├── error_pattern_summary.json
├── system_prompt_candidate-*.txt
├── schema_check_prompt_candidate-*.txt
├── thought_process_prompt_candidate-*.txt
└── apo_result.json (仅 APO)
```

## 3.5 产物发布

接口：`POST /api/training/publish`

- Dry Run：只预览差异，不改线上文件。
- Apply：调用 `apply_prompt_candidates.py`（可选 `apply_schema_candidate.py`）写入目标文件，并自动备份。

---

## 强化学习算法

## 4.1 RGO（默认）

入口：`train_algo=rgo`

特点：
- 基于轨迹统计与错误分布生成提示词增量建议
- 规则驱动优化，不更新模型权重

## 4.2 APO

入口：`train_algo=apo`

核心：
- 从候选增量池中迭代采样
- 对候选进行评分（`_apo_score_candidate`）
- 接受更优候选

参数：
- `apo-iters`：迭代轮数
- `apo-sample-size`：每轮候选数量
- `apo-exploration`：探索强度（采样覆盖比例）

---

## 完整示例

## 5.1 端到端流程

1. 用户在工作台提交任务。  
2. 系统检索历史经验并注入上下文。  
3. Agent 调用工具完成仿真与结果提取。  
4. 写入 spans 与 reward。  
5. 自动沉淀记忆（SQLite + md）。  
6. 在 RL Lab 发起采样 + 训练。  
7. 查看训练产物差异。  
8. 在发布页执行 Dry Run/Apply。  

## 5.2 关键实现结论

- 记忆是“结构化数据库 + md 文档”双存储。  
- 记忆检索当前是规则与词法机制，不是向量检索。  
- 奖励是多因子模型，工具调用次数仅为子项。  
- 训练后需要显式发布，不会自动覆盖线上提示词。  

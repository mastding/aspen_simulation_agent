<template>
  <SettingsLayout
    title="帮助中心"
    subtitle="本页按系统菜单梳理功能与常见操作，便于快速定位问题与排障。"
    :active="activeTab"
    :groups="sidebarGroups"
    @select="activeTab = $event"
  >
    <!-- 功能概览 -->
    <section v-if="activeTab === 'overview'" class="gh-panel">
      <div class="gh-panel-header">
        <div>
          <div class="gh-panel-header-title">功能概览</div>
          <div class="gh-panel-header-sub">系统主要功能模块说明</div>
        </div>
      </div>
      <div class="gh-panel-body">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
          <div v-for="section in sections" :key="section.title" class="gh-stat-card">
            <div class="gh-stat-label">{{ section.title }}</div>
            <div style="font-size: 13px; color: #656d76; margin-top: 8px; line-height: 1.5;">
              {{ section.description }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 使用指南 -->
    <section v-if="activeTab === 'agent'" class="gh-panel">
      <div class="gh-panel-header">
        <div class="gh-panel-header-title">智能体调用流程</div>
      </div>
      <div class="gh-panel-body">
        <div class="help-markdown" v-html="agentHtml"></div>
      </div>
    </section>

    <!-- 经验中心 -->
    <section v-if="activeTab === 'memory'" class="gh-panel">
      <div class="gh-panel-header">
        <div class="gh-panel-header-title">经验中心实现</div>
      </div>
      <div class="gh-panel-body">
        <div class="help-markdown" v-html="memoryHtml"></div>
      </div>
    </section>

    <!-- 训练算法 -->
    <section v-if="activeTab === 'training'" class="gh-panel">
      <div class="gh-panel-header">
        <div class="gh-panel-header-title">训练算法与流程</div>
      </div>
      <div class="gh-panel-body">
        <div class="help-markdown" v-html="trainingHtml"></div>
      </div>
    </section>

    <!-- 数据库 -->
    <section v-if="activeTab === 'database'" class="gh-panel">
      <div class="gh-panel-header">
        <div class="gh-panel-header-title">数据库实现</div>
      </div>
      <div class="gh-panel-body">
        <div class="help-markdown" v-html="databaseHtml"></div>
      </div>
    </section>

    <!-- 常见问题 -->
    <section v-if="activeTab === 'faqs'" class="gh-panel">
      <div class="gh-panel-header">
        <div class="gh-panel-header-title">常见问题</div>
      </div>
      <div class="gh-panel-body">
        <div style="display: flex; flex-direction: column; gap: 16px;">
          <div v-for="(faq, index) in faqs" :key="index" style="border-bottom: 1px solid #d1d9e0; padding-bottom: 16px;" :style="index === faqs.length - 1 ? 'border-bottom: none; padding-bottom: 0;' : ''">
            <div style="font-size: 14px; font-weight: 600; color: #1f2328; margin-bottom: 8px;">
              {{ faq.question }}
            </div>
            <div style="font-size: 13px; color: #656d76; line-height: 1.6;">
              {{ faq.answer }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 关于系统 -->
    <section v-if="activeTab === 'about'" class="gh-panel">
      <div class="gh-panel-header">
        <div class="gh-panel-header-title">关于系统</div>
      </div>
      <div class="gh-panel-body">
        <div class="help-markdown" v-html="aboutHtml"></div>
      </div>
    </section>
  </SettingsLayout>
</template>

<script setup>
import { ref, computed } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import SettingsLayout from '../components/SettingsLayout.vue';
import '../assets/github-theme.css';

const activeTab = ref('overview');

const sidebarGroups = [
  {
    label: '',
    items: [
      { id: 'overview', label: '功能概览', icon: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M0 1.75A.75.75 0 0 1 .75 1h4.253c1.227 0 2.317.59 3 1.501A3.744 3.744 0 0 1 11.006 1h4.245a.75.75 0 0 1 .75.75v10.5a.75.75 0 0 1-.75.75h-4.507a2.25 2.25 0 0 0-1.591.659l-.622.621a.75.75 0 0 1-1.06 0l-.622-.621A2.25 2.25 0 0 0 5.258 13H.75a.75.75 0 0 1-.75-.75Zm7.251 10.324.004-5.073-.002-2.253A2.25 2.25 0 0 0 5.003 2.5H1.5v9h3.757a3.75 3.75 0 0 1 1.994.574ZM8.755 4.75l-.004 7.322a3.752 3.752 0 0 1 1.992-.572H14.5v-9h-3.495a2.25 2.25 0 0 0-2.25 2.25Z"/></svg>' },
      { id: 'agent', label: '智能体调用', icon: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M5.5 3.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM2 6.5a.5.5 0 0 1 .5-.5h6a.5.5 0 0 1 .5.5V8h2V6.5a.5.5 0 0 1 .5-.5h2a.5.5 0 0 1 .5.5v3a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1-.5-.5V8H9v2.5a.5.5 0 0 1-.5.5h-6a.5.5 0 0 1-.5-.5v-4Z"/></svg>' },
      { id: 'memory', label: '经验中心', icon: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M8 .5a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15ZM8 2a6 6 0 1 0 0 12A6 6 0 0 0 8 2Zm.75 2.75a.75.75 0 0 0-1.5 0v2.5h-2.5a.75.75 0 0 0 0 1.5h2.5v2.5a.75.75 0 0 0 1.5 0v-2.5h2.5a.75.75 0 0 0 0-1.5h-2.5Z"/></svg>' },
      { id: 'training', label: '训练算法', icon: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M1.5 1.75V13.5h13.75a.75.75 0 0 1 0 1.5H.75a.75.75 0 0 1-.75-.75V1.75a.75.75 0 0 1 1.5 0Zm14.28 2.53-5.25 5.25a.75.75 0 0 1-1.06 0L7 7.06 4.28 9.78a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042l3.25-3.25a.75.75 0 0 1 1.06 0L10 7.94l4.72-4.72a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042Z"/></svg>' },
      { id: 'database', label: '数据库', icon: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M8 1c-3.314 0-6 1.119-6 2.5V12.5C2 13.881 4.686 15 8 15s6-1.119 6-2.5V3.5C14 2.119 11.314 1 8 1ZM3.5 3.5c0-.415 1.791-1.5 4.5-1.5s4.5 1.085 4.5 1.5S10.709 5 8 5 3.5 3.915 3.5 3.5ZM12.5 12.5c0 .415-1.791 1.5-4.5 1.5s-4.5-1.085-4.5-1.5V5.67C4.945 6.472 6.4 7 8 7s3.055-.528 4.5-1.33Z"/></svg>' },
      { id: 'faqs', label: '常见问题', icon: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-6.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM6.92 6.085h.001a.749.749 0 1 1-1.342-.67c.169-.339.516-.644.932-.856C6.922 4.34 7.41 4.2 8 4.2c.72 0 1.337.212 1.776.55.453.348.724.862.724 1.45 0 .463-.143.836-.394 1.14a2.41 2.41 0 0 1-.534.434 3.08 3.08 0 0 0-.136.093.749.749 0 0 1-.2.553.75.75 0 0 1-1.236-.226v-.463c0-.26.14-.5.368-.63.126-.073.263-.159.382-.256a.9.9 0 0 0 .2-.182c.065-.078.1-.17.1-.3 0-.162-.08-.293-.243-.418C8.57 5.833 8.336 5.7 8 5.7c-.36 0-.593.07-.748.148a.727.727 0 0 0-.332.337ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"/></svg>' },
      { id: 'about', label: '关于系统', icon: '<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-6.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM6.5 7.75A.75.75 0 0 1 7.25 7h1a.75.75 0 0 1 .75.75v2.75h.25a.75.75 0 0 1 0 1.5h-2a.75.75 0 0 1 0-1.5h.25v-2h-.25a.75.75 0 0 1-.75-.75ZM8 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"/></svg>' },
    ],
  },
];

const sections = [
  {
    title: '工作台',
    description: '用户输入自然语言任务，前端通过流式请求调用 /api/chat/stream，后端 Agent 自动执行 get_schema → run_simulation → get_result 工具链完成模拟。',
  },
  {
    title: '任务历史',
    description: '查看 rollout 执行记录、步骤 spans、每日趋势、高频错误，以及当前已并入该页面的文件产物列表。',
  },
  {
    title: '经验中心',
    description: '基于规则匹配 + 语义相似度的经验检索系统。成功任务自动提取经验（策略/配置/避坑），新任务执行前自动检索 top-K 相关经验注入 prompt。',
  },
  {
    title: '训练工作台',
    description: '基于 RGO（规则引导离线优化）算法，支持离线和在线两种训练操作方式。采样阶段收集轨迹数据，训练阶段优化提示词，在线模式支持多轮迭代自动发布。',
  },
  {
    title: '训练发布',
    description: '评审训练产物并发布提示词增量；同时支持在线编辑当前提示词和维护 Schema 文件。',
  },
  {
    title: '系统设置',
    description: '配置 LLM 模型参数和 Aspen 服务地址，并提供用户管理入口。配置会写入本地文件，通常需要手动重启后端后才会完全生效。',
  },
];

const faqs = [
  {
    question: '模拟失败怎么办？',
    answer: '先到任务历史查看该 rollout 的执行过程（spans）、高频错误和相关产物信息，重点定位 run_simulation / get_result 的报错。系统会自动区分 config、runtime、timeout、connection 等错误，并在单次任务内最多进行 100 轮工具迭代。',
  },
  {
    question: '经验检索是如何工作的？',
    answer: '执行新任务时，系统从任务文本提取结构化特征（设备类型/组分/物性方法等），然后在 memory_cases 表中进行多维度打分：文本匹配 + 结构化匹配（must/anchor/should 三层）+ 语义相似度 + 经验质量评估。按任务类型差异化选择 top-K 经验注入到 Agent 的 prompt 中。',
  },
  {
    question: 'RGO 训练是什么？',
    answer: 'RGO（Rule-Guided Offline Optimization，规则引导离线优化）分析轨迹数据中的高频错误模式（如配置错误、运行时错误），提取成功修复路径，自动生成针对性的提示词优化补丁写入 OPTIMIZATION_ZONE 区域。',
  },
  {
    question: 'Reward 是怎么计算的？',
    answer: 'Reward 基于多维度加权：任务完成度（run_simulation + get_result 是否成功）× 0.55 + 工具效率（重试次数的指数衰减）× 0.20 + 错误恢复能力 × 0.15 + 流水线完整度 × 0.10 - 错误惩罚。Process 模式还考虑多轮完成进度。',
  },
  {
    question: '在线训练模式是什么？',
    answer: '在线训练支持多轮迭代：每轮先采样执行任务收集轨迹，然后训练生成候选提示词，自动发布并热重载 prompt 模块，下一轮使用新提示词继续采样。第 2 轮起禁用经验检索，纯测试新提示词效果。',
  },
  {
    question: '训练后的提示词如何发布？',
    answer: '在训练发布页面选择训练运行并勾选提示词增量后执行发布，系统会把候选内容写入当前生效的 app/prompts 目录。发布完成后，可在同页的“提示词管理”中继续查看和编辑当前内容。',
  },
];

const agentMarkdown = `## 整体架构

用户发送消息 → 前端流式请求 → 后端 \`chat_stream\` → \`execute_user_task\` → AutoGen Agent 循环调用工具 → 流式返回结果

### 技术栈
- 前端：Vue 3 + fetch + ReadableStream 解析 SSE 数据流
- 后端：FastAPI + AutoGen AgentChat + AgentLightning
- AgentLightning：InMemoryLightningStore 管理 rollout 生命周期，emit_message/emit_annotation/emit_reward 发射事件
- LLM：通过 OpenAI 兼容接口调用（支持 DeepSeek 等模型）

## 前端调用链路

\`\`\`
PromptComposer.vue → WorkspaceView.vue sendMessage()/sendMessageViaSse()
  → POST /api/chat/stream { message, session_id, task_type, equipment_type, ... }
  → 前端逐段解析 SSE 数据流
\`\`\`

前端通过 \`fetch\` 发起 POST 请求，并从响应流中逐段解析 \`data:\` 事件。事件类型包括：
- \`rollout_started\` — 任务开始，返回 rollout_id
- \`memory_hits\` — 经验检索命中结果
- \`memory_context\` — 注入的经验上下文
- \`update\` (thought) — Agent 思考过程
- \`update\` (tool_calling) — 工具调用请求
- \`update\` (tool_results) — 工具执行结果
- \`done\` — 任务完成，包含 reward 评分
- \`heartbeat\` — 每 15 秒心跳保活

## 后端处理链路

### 1. SSE 入口 — \`chat_stream_service.py\`

\`\`\`python
async def chat_stream(payload, deps):
    # 1. 校验 session_id, message
    # 2. 检查是否有正在运行的任务（防并发）
    # 3. 创建 CancellationToken + asyncio.Queue
    # 4. 启动 _worker 协程执行任务
    # 5. 返回 StreamingResponse (SSE)
\`\`\`

### 2. 任务执行核心 — \`chat_execution_service.py:execute_user_task\`

这是整个系统的核心函数，完整流程：

\`\`\`
execute_user_task()
  ├── 1. 创建 AspenTask，递增 task_counter
  ├── 2. store.start_rollout() — AgentLightning InMemoryLightningStore 创建 rollout 对象
  ├── 3. persist_rollout_start() — 写入 SQLite rollouts 表
  ├── 4. 经验检索 build_memory_context_for_task(top_k=5)
  │     ├── 语义匹配 + 规则匹配
  │     └── 注入到用户消息前缀
  ├── 5. 构建 effective_user_message
  │     ├── [经验检索策略] 指引
  │     └── [当前任务] 用户原始消息
  ├── 6. reset_agent → get_agent (创建 AssistantAgent)
  ├── 7. Agent 循环执行 ← 核心循环
  │     └── agent.on_messages_stream() 流式处理
  │         ├── ThoughtEvent → 记录思考过程
  │         ├── ToolCallRequestEvent → 工具调用请求
  │         ├── ToolCallExecutionEvent → 工具执行结果
  │         └── ModelClientStreamingChunkEvent → LLM 流式输出
  ├── 8. 计算 reward（calculate_reward_v1）
  ├── 9. 自动提取经验（auto_upsert_memory_from_rollout）
  └── 10. persist_rollout_status → 更新最终状态
\`\`\`

### 3. Agent 创建 — \`agent_factory.py\`

\`\`\`python
# 创建 LLM 客户端
model_client = OpenAIChatCompletionClient(
    api_key, base_url, model,
    temperature=..., max_tokens=..., timeout=...
)

# 创建 Agent
agent = AssistantAgent(
    name="aspen_expert",
    model_client=model_client,
    system_message=system_prompt,  # 来自 llm_prompt.py
    tools=[get_schema, run_simulation, get_result,
           memory_search_experience, memory_get_experience],
    reflect_on_tool_use=True,      # 工具执行后反思
    model_client_stream=True,      # 流式输出
    max_tool_iterations=100,       # 最大工具调用轮次
)
\`\`\`

### 4. System Prompt 构建 — \`llm_prompt.py\`

System Prompt 由多个模块拼接而成：

\`\`\`
system_prompt = f"""
角色：化工流程模拟专家

[经验检索策略]
  → 先调用 memory_search_experience
  → 命中则调用 memory_get_experience
  → 优先复用历史配置

1. 获取 Schema: {schema_get_prompt}
   检查要求: {schema_check_prompt}
   思考流程: {thought_process_prompt}

2. 调用 run_simulation 运行模拟
   失败则根据报错重试

3. 调用 get_result 获取结果: {result_get_prompt}

[OPTIMIZATION_ZONE] — 训练优化区域
  → RGO 训练产生的策略补丁写入此区域
"""
\`\`\`

### 5. 工具调用循环机制

Agent 基于 AutoGen 的 \`on_messages_stream\` 实现自主循环：

\`\`\`
用户消息 → LLM 推理 → 决定调用工具
  → 执行工具 → 获取结果 → LLM 继续推理
  → 决定是否继续调用工具或生成最终回复
  → 循环直到 LLM 输出最终文本回复
\`\`\`

每次工具调用都会：
1. 记录 span 到 SQLite（tool_call_request / tool_execution）
2. 通过 SSE 推送进度事件到前端
3. 分类错误类型（config/runtime/timeout/connection）
4. 更新进度阶段（schema_generation → simulation → result_fetch）

### 6. 自动恢复机制

当 prompt token 超过 14000 时，系统自动触发 \`auto_resume\`：
- 截断已有上下文
- 构建恢复 prompt（包含已执行工具快照）
- 重新发起 Agent 调用

上下文溢出时也会自动恢复，最多重试 2 次。
`;

const memoryMarkdown = `## 经验系统架构

\`\`\`
任务完成 → reward ≥ 阈值 → 自动提取经验
  ├── 策略摘要（思考链 + 最终回复）
  ├── 关键配置（最后一次 run_simulation 的 config）
  ├── 避坑经验（失败链路 + 修复方法）
  └── 匹配特征（设备/组分/物性方法/操作类型）

新任务 → 经验检索（top-K）→ 注入 Agent prompt
\`\`\`

## 经验存储结构

### 数据库表 \`memory_cases\`

| 字段 | 说明 |
|------|------|
| memory_id | 唯一标识，格式 \`mem-{task_hash[:16]}\` |
| task_hash | 任务文本 + 经验类型的 SHA1 哈希 |
| task_text | 原始任务描述 |
| task_type | unit / process |
| strategy_text | 策略摘要（思考链 + 回复） |
| config_snippet | 关键配置 JSON（run_simulation 参数） |
| pitfalls_text | 避坑经验摘要 |
| failure_reason | 失败原因 |
| fix_action | 修复动作 |
| lesson | 经验教训 |
| reward | 任务奖励值 |
| features_json | 匹配特征（设备/组分/方法等） |

### 经验类型分类

| 类型 | 触发条件 | 说明 |
|------|----------|------|
| success_golden | 一次成功（run_calls=1） | 最高质量，reward ≥ 0.98 |
| success_recovered | 重试后成功 | 包含避坑经验 |
| pitfall_recovery | 有失败但最终恢复 | 记录错误修复路径 |
| pitfall_failure | 有失败未恢复 | 记录失败原因 |
| process_global | 流程任务全局经验 | 多轮模拟的整体策略 |
| process_stage | 流程任务阶段经验 | 每个阶段的配置 |

## 经验提取流程 — \`pipeline_ops.py:auto_upsert_memory_from_rollout\`

\`\`\`python
def auto_upsert_memory_from_rollout(rollout_id, task_text, reward, ...):
    # 1. 检查 reward 是否达到阈值（默认 0.8）
    if reward < min_reward: return

    # 2. 从 spans 提取信息
    spans = query_spans_sqlite(rollout_id)
    strategy_text = extract_strategy_from_spans(spans)      # 思考链摘要
    config_snippet = extract_config_snippet_from_spans(spans) # 最后一次配置
    pitfall_details = extract_pitfall_details_from_spans(spans) # 避坑详情

    # 3. 根据任务类型和执行结果分类存储
    if task_type == "unit":
        if 一次成功: upsert_case(kind="success_golden")
        elif 重试成功: upsert_case(kind="success_recovered")
        if 有失败: upsert_case(kind="pitfall_recovery/failure")
    else:  # process
        if 有完成轮次: upsert_case(kind="process_global")
        for 每个阶段: upsert_case(kind="process_stage")
\`\`\`

### 经验特征提取 — \`matching.py:build_memory_features\`

从任务文本、策略、配置中提取结构化匹配特征：

\`\`\`python
features = {
    "methods": ["NRTL", "PENG-ROB"],     # 物性方法
    "equipment": ["radfrac", "heatx"],     # 设备类型
    "equipment_ids": ["B1", "HX-1"],       # 设备ID
    "components": ["CH3OH", "H2O"],        # 化学组分
    "streams": ["FEED1", "PRODUCT"],       # 物流名称
    "ops": ["分离", "换热"],               # 操作类型
    "flow": ["混合", "回流"],              # 流程动词
    "semantic_profile": {                   # 语义画像
        "task_family": "distillation_task",
        "task_type": "unit",
        "entities": {...},
        "actions": [...],
    }
}
\`\`\`

## 经验检索流程 — \`pipeline_ops.py:search_memory_cases\`

\`\`\`
用户消息 → 特征提取 → 查询增强 → 多维度打分 → 排序选择
\`\`\`

### 打分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 文本匹配 | token 命中数 × 1.0 | 分词后逐 token 匹配 |
| 精确匹配 | +1.5 | 完整查询文本命中 |
| 任务类型 | +0.8 | unit/process 类型一致 |
| 经验类型 | 0.2~1.2 | golden > process_global > recovered > pitfall |
| reward 加成 | reward × 0.3 | 高 reward 经验优先 |
| 结构化匹配 | ranking_score | 设备/组分/方法的 must/anchor/should 三层匹配 |
| 语义相似度 | semantic_score | task_family + 实体重叠度加权 |
| 质量评估 | quality_score | 历史使用成功率 + 平均 reward + 时效性 |

### 结构化匹配三层机制 — \`matching.py:match_required_fields\`

\`\`\`
must 层（设备ID）: 必须全部命中，否则过滤
anchor 层（设备类型/物流）: 至少命中一个
should 层（操作/组分/方法）: 加权评分
\`\`\`

### 经验选择策略

按任务类型差异化选择：
- **unit 模式**: 优先选 1 条 golden/recovered + 最多 2 条 pitfall
- **process 模式**: 优先选 1 条 process_global + 最多 2 条 stage + 2 条 pitfall

## 经验注入 — \`core_ops.py:build_memory_context_for_task\`

检索到的经验被格式化后注入到用户消息前缀：

\`\`\`
【历史最佳实践参考（请优先复用）】
1. 任务: 模拟甲醇-水精馏塔...
   类型: unit | reward: 0.95
   策略: 先获取 RadFrac schema，设置 20 块理论板...
   配置片段: {"blocks_RadFrac": {...}}
   风险: run_simulation 首次因进料位置错误失败...
请保持与上述实践一致，优先最小改动。
\`\`\`

## 经验使用追踪

每次经验被检索命中，系统记录到 \`memory_usage_events\` 表：
- 命中排名、匹配分数、查询文本
- 任务最终状态（succeeded/failed）
- 任务 reward 和工具调用次数

这些数据用于计算经验质量指标，低质量经验会被降权。

---

## 完整示例：混合器任务的经验生成与检索

以下以一个真实的三股物流混合器任务为例，完整展示经验从生成到检索的全流程。

### 第一阶段：任务执行

用户输入任务：
> 将如下三股物流混合，计算混合后产品物流的温度、压力及各组分流量。物性方法采用CHAO-SEA。
> FEED1：温度100℃，压力2MPa；丙烷(C3):10, 正丁烷(NC4):15, 正戊烷(NC5):15, 正己烷(NC6):10 kmol/h
> FEED2：温度120℃，压力2.5MPa；丙烷:15, 正丁烷:15, 正戊烷:10, 正己烷:10 kmol/h
> FEED3：温度100℃，气相分数0.5；丙烷:25, 正丁烷:0, 正戊烷:15, 正己烷:10 kmol/h

Agent 执行过程（来自 rollout \`ro-b6f4d4f455ce\` 的 spans 记录）：

\`\`\`
span[1] prompt_assignment  → 提示词版本分配
span[2] task_started        → task_id: online_1
span[3] thought             → "我将按照经验检索策略开始分析这个任务"
span[4] tool_call_request   → memory_search_experience(query="三股物流混合...", top_k=3)
span[5] tool_execution      → result: {total: 0, items: []}  ← 首次执行，无历史经验
span[6] thought             → "没有找到相关经验，需要重新生成配置"
span[7] tool_call_request   → get_schema(block_types=["Mixer"])
span[8] tool_execution      → 返回 Mixer 的 JSON Schema
span[9] thought             → "分析配置：1个Mixer(M1), 3股进料, 1股产品, CHAO-SEA"
span[10] tool_call_request  → run_simulation(config={...})  ← 一次成功！
span[11] tool_execution     → result: {success: true}
span[12] tool_call_request  → get_result(...)
span[13] tool_execution     → 返回温度97.63℃, 压力13.49bar, 各组分流量
span[14] reward             → reward: 0.98 (一次成功，满分级别)
\`\`\`

### 第二阶段：Reward 计算

\`chat_execution_service.py\` 在任务结束时调用 \`calculate_reward_v1\`：

\`\`\`python
# rl/reward.py — Unit 模式 reward 计算
mode = "unit"
run_calls = 1, run_success = 1, get_result_success = 1

completion = 1.0   # run_simulation 成功 + get_result 成功
efficiency = exp(-0.35 × 0) = 1.0  # retry_count=0，一次成功
recovery = 0.0     # 无失败，不需要恢复
pipeline = 0.5 + 0.5 = 1.0  # get_schema(0.5) + get_result(0.5)
penalty = 0        # 无错误

reward = 1.0×0.55 + 1.0×0.20 + 0.0×0.15 + 1.0×0.10 - 0
       = 0.55 + 0.20 + 0.0 + 0.10 = 0.85
# 实际系统中 success_golden 类型会提升到 max(reward, 0.98) = 0.98
\`\`\`

### 第三阶段：经验自动提取

\`pipeline_ops.py:auto_upsert_memory_from_rollout\` 被调用：

\`\`\`python
# 触发条件检查
reward = 0.98 >= min_reward(0.8)  ✓ 达到阈值

# 从 spans 提取信息
strategy_text = extract_strategy_from_spans(spans)
  → 提取最后2条 thought + 最后1条 assistant_response
config_snippet = extract_config_snippet_from_spans(spans)
  → 提取最后一次 run_simulation 的 config 参数
pitfall_details = extract_pitfall_details_from_spans(spans)
  → 无失败，pitfalls 为空

# 分类判断：unit 模式 + run_success=1 + run_calls=1 + get_result_success=1
# → 命中 "success_golden" 分支（一次成功的黄金经验）
upsert_memory_case(
    task_text = "将如下三股物流混合...",
    task_type = "unit",
    tags = ["unit", "kind:success_golden", "equipment:mixer"],
    memory_kind = "success_golden",
    reward = max(0.98, 0.98) = 0.98,
    lesson = "一次成功的模拟任务，配置参数可直接复用。",
)
\`\`\`

### 第四阶段：经验存储

\`storage_ops.py:upsert_memory_case\` 执行：

\`\`\`python
# 1. 计算 task_hash（去重键）
hash_input = normalize("将如下三股物流混合...") + "|success_golden|mixer-golden"
task_hash = sha1(hash_input)  → "270bf987d9c78601..."
memory_id = "mem-270bf987d9c78601"

# 2. 提取匹配特征
features = matching.build_memory_features(task_text, strategy_text, config_snippet)
\`\`\`

实际存入数据库的 \`features_json\`：

\`\`\`json
{
  "match_fields": {
    "methods": ["CHAO-SEA"],
    "equipment": ["mixer"],
    "equipment_ids": ["PROD-1"],
    "streams": ["FEED1", "FEED2", "FEED3", "PRODUCT"],
    "components": ["C3", "NC4", "NC5", "NC6", "C3H8", "C4H10", "C5H12", "C6H14"],
    "ops": ["混合", "温度", "压力", "流量", "组成", "计算", "模拟"],
    "flow": ["混合", "生成"]
  },
  "semantic_profile": {
    "task_title": "将如下三股物流混合，计算混合后产品物流的温度、压力及各组分流量",
    "task_type": "unit",
    "task_family": "mixing_calculation",
    "entities": {
      "equipment_types": ["mixer"],
      "stream_inputs": ["FEED1", "FEED2", "FEED3"],
      "stream_outputs": ["PRODUCT"],
      "components": ["C3", "NC4", "NC5", "NC6"],
      "thermo_methods": ["CHAO-SEA"]
    },
    "actions": ["calculate_product_conditions", "mix_streams"],
    "expected_outputs": ["product_temperature", "product_pressure",
                         "component_flowrates", "component_composition"]
  }
}
\`\`\`

同时写入 Markdown 文档到 \`rl_data/memory_docs/mem-270bf987d9c78601.md\`。

数据库 \`memory_cases\` 表中的完整记录：

| 字段 | 值 |
|------|-----|
| memory_id | mem-270bf987d9c78601 |
| task_hash | 270bf987d9c78601... |
| task_type | unit |
| tags_json | ["unit", "kind:success_golden", "equipment:mixer"] |
| reward | 0.98 |
| tool_call_count | 4 |
| source_rollout_id | ro-b6f4d4f455ce |
| lesson | 一次成功的模拟任务，配置参数可直接复用 |

\`config_snippet\` 存储了完整的 run_simulation 配置（约 3KB JSON），包含：
- components: C3/NC4/NC5/NC6 的 CAS 号和数据库名
- property_methods: CHAO-SEA
- blocks: M1 (Mixer)
- streams: FEED-1/FEED-2/FEED-3/PROD-1
- stream_data: 每股流的温度/压力/组成/流量

### 第五阶段：经验检索（新任务触发）

当用户发起一个类似的混合器任务时，\`search_memory_cases\` 被调用。

假设新任务：
> 使用设备：混合器 Mixer，进料1：温度100℃，压力2MPa，丙烷(C3):10, 正丁烷(NC4):15...

#### 步骤 1：特征提取

\`\`\`python
# matching.py:extract_match_fields
query_fields = {
    "methods": [],                    # 新任务未指定物性方法
    "equipment": ["mixer"],           # 识别到混合器
    "equipment_ids": [],
    "streams": ["FEED1"],
    "components": ["C3", "NC4"],
    "ops": ["混合", "温度", "压力"],
    "flow": ["混合"]
}

# matching.py:build_semantic_profile
query_profile = {
    "task_type": "unit",
    "task_family": "mixing_calculation",  # 推断为混合计算
    "actions": ["mix_streams", "calculate_product_conditions"],
    "expected_outputs": ["product_temperature", "product_pressure"]
}
\`\`\`

#### 步骤 2：查询增强

\`\`\`python
# pipeline_ops.py:_enrich_query_structures
# 如果 equipment 为空但 task_family 是 mixing_calculation，自动补充 mixer
enriched_fields["equipment"] = ["mixer"]
\`\`\`

#### 步骤 3：遍历所有经验，多维度打分

对 \`mem-270bf987d9c78601\` 这条经验的打分过程：

\`\`\`python
# 1. 结构化匹配 — match_required_fields()
must 层 (equipment_ids):  query=[] → 无要求，跳过 ✓
anchor 层 (equipment):    query=["mixer"] ∩ mem=["mixer"] → 命中 ✓
anchor 层 (streams):      query=["FEED1"] ∩ mem=["FEED1","FEED2","FEED3","PRODUCT"] → 命中 ✓
should 层 (components):   query=["C3","NC4"] ∩ mem=["C3","NC4","NC5","NC6",...] → ratio=1.0
should 层 (ops):          query=["混合","温度","压力"] ∩ mem=["混合","温度","压力",...] → ratio=1.0
should 层 (methods):      query=[] → 无要求
→ structured_match_score ≈ 2.8

# 2. 语义相似度 — score_semantic_similarity()
task_family: mixing_calculation == mixing_calculation → +0.8
task_type: unit == unit → +0.4
equipment_types: ["mixer"] ∩ ["mixer"] → +1.1
components: overlap → +0.9 × ratio
actions: overlap → +1.0 × ratio
→ semantic_score ≈ 4.2

# 3. 文本匹配
token_hits: "混合", "温度", "压力", "C3", "NC4" 等命中 → +5.0

# 4. 经验类型加成
kind = "success_golden" → +1.2（最高加成）

# 5. reward 加成
reward = 0.98 → +0.98 × 0.3 = +0.294

# 6. 任务类型加成
task_type: unit == unit → +0.8

# 7. 质量评估（基于 memory_usage_events）
# 该经验被使用过 5 次，4 次成功 → success_rate=0.8
quality_score = 0.8×0.8 + 0.77×0.5 + 0.8×0.3 + recency_boost
             ≈ 1.265

# 最终得分
total_score ≈ 5.0 + 2.8 + 4.2 + 1.2 + 0.294 + 0.8 + 1.265 ≈ 15.56
\`\`\`

#### 步骤 4：经验选择策略

\`\`\`python
# unit 模式选择策略
pick_one(["success_golden", "success_recovered"])  # 选1条最佳经验
pick_many(["pitfall_recovery", "pitfall_failure"], 2)  # 选最多2条避坑经验
# 补充到 top_k=5
\`\`\`

#### 步骤 5：经验注入到 Agent Prompt

\`\`\`python
# core_ops.py:build_memory_context_for_task
context_text = """
【历史最佳实践参考（请优先复用）】
1. 任务: 将如下三股物流混合，计算混合后产品物流的温度、压力及各组分流量
   类型: unit | reward: 0.98
   策略: 分析配置：1个Mixer(M1), 3股进料, 1股产品, CHAO-SEA...
   配置片段: {"components": [{"cid": "C3", ...}], "blocks": [{"name": "M1", "type": "Mixer"}], ...}
   风险: (无)
请保持与上述实践一致，优先最小改动，避免推翻已验证配置。
"""
\`\`\`

这段文本被拼接到用户消息前面，Agent 会优先参考历史配置。

#### 步骤 6：使用追踪

\`\`\`python
# core_ops.py:log_memory_usage_events
INSERT INTO memory_usage_events(
    usage_id='muse-xxx',
    rollout_id='ro-新任务id',
    memory_id='mem-270bf987d9c78601',
    hit_rank=1,
    match_score=16.29,
    status='pending'  -- 任务结束后更新为 succeeded/failed
)
\`\`\`

实际数据库中该经验的使用记录：

| usage_id | rollout_id | hit_rank | match_score | status | reward |
|----------|------------|----------|-------------|--------|--------|
| muse-4f75... | ro-a806... | 3 | 16.29 | succeeded | 0.77 |
| muse-0c09... | ro-3480... | 2 | 16.29 | succeeded | 0.77 |
| muse-b2e2... | ro-f76d... | 2 | 16.29 | succeeded | 0.77 |
| muse-d254... | ro-a4b6... | 2 | 16.28 | succeeded | 0.77 |

可以看到该经验被多次检索使用，每次使用后任务都成功（reward ≈ 0.77），验证了经验的有效性。

---

## 完整示例：失败恢复经验的生成与检索

以下以一个三塔串联精馏任务为例，展示失败经验如何被提取、存储，并在后续任务中被检索使用。

### 原始任务（rollout \`ro-23d2a9684a20\`）

> 使用三个 RadFrac 精馏塔（T1/T2/T3）串联分离四组分混合物。
> 进料：100℃, 1.2bar, 100kmol/h, nC6:nC8:nC10:nC12 各 0.25 摩尔分数。
> T1 塔顶分出 nC6，T2 塔顶分出 nC8，T3 塔顶分出 nC10，塔底得到 nC12。
> 物性方法 PENG-ROB。

### 第一阶段：任务执行 — 13 次 run_simulation 尝试

\`\`\`
span 序列（关键节点）：

[1] memory_search_experience → total: 0（首次执行，无历史经验）
[2] memory_search_experience → total: 0（宽泛搜索仍无命中）
[3] get_schema(["DSTWU", "RadFrac"]) → 获取 Schema 成功
[4] thought → "先使用 DSTWU 简捷塔获取初值"

--- 第 1 次 run_simulation → ❌ 配置错误 ---
错误: stream_data 配置写入错误: 'NoneType' object has no attribute 'SetValueUnitAndBasis'
原因: 流量配置格式不正确

--- 第 2 次 run_simulation → ❌ 配置错误 ---
错误: 同上，修正不彻底

--- 第 3 次 run_simulation → ❌ 配置错误 ---
错误: blocks_DSTWU_data 配置写入错误: 'nC6不是一个有效值'
原因: 组分标识符 cid 命名不符合 Aspen 规范

[thought] → "问题可能是 cid 的命名，让我使用更简单的组分标识符"

--- 第 4 次 run_simulation → ❌ 运行时错误 ---
错误: 模拟引擎加载后 WARNING: STREAM FEED-1 IS A FEED STREAM...
原因: 修正了 cid 但流股配置仍有问题

... 经过多次调整 ...

--- 第 8 次 run_simulation → ❌ 运行时错误 ---
错误: WHILE CHECKING INPUT SPECIFICATIONS

--- 第 9-13 次 → 部分成功，部分运行时错误 ---
T1 收敛成功，T2 有 WARNING，T3 不收敛
逐步调整回流比、理论板数、进料位置

--- 最终成功 ---
[thought] → "太好了！这次模拟成功了。让我获取结果"
get_result → 成功获取四个产品的组成和流量
\`\`\`

### 第二阶段：Reward 计算

\`\`\`python
# 来自 reward span 的实际数据
{
  "reward": 0.2296,
  "task_mode": "process",
  "task_completion": 1.0,        # 最终成功完成
  "tool_efficiency": 0.1979,     # 14次调用，效率很低
  "pipeline_quality": 1.0,       # get_schema + get_result 都成功
  "run_simulation_calls": 14,
  "run_simulation_success": 5,
  "run_simulation_fail_total": 9,  # 9次失败！
  "failure_categories": ["simulation_config_error", "simulation_runtime_error"],
  "failure_penalty": 0.25,        # 失败惩罚
  "elapsed_seconds": 899.45       # 耗时 15 分钟
}

# Process 模式 reward 计算
completion = 1.0    # rounds_completed(5) >= expected_rounds
progress = 1.0      # 5/5 = 1.0
overhead = 14 - 5 = 9  # 多余调用
efficiency = exp(-0.18 × 9) = 0.1979  # 效率极低
penalty = config_fail × 0.12 + runtime_fail × 0.06 = 大量惩罚

reward = 1.0×0.45 + 1.0×0.20 + 0.1979×0.20 + ... - penalty
       = 0.2296  ← 低 reward，但仍然成功完成
\`\`\`

### 第三阶段：经验自动提取

\`pipeline_ops.py:auto_upsert_memory_from_rollout\` 被调用：

\`\`\`python
reward = 0.2296 >= min_reward(0.8)?  → ❌ 不满足！

# 但是！这个 rollout 是通过 RL 训练采样执行的，
# 训练流程中 min_reward 阈值更低，或者通过
# build_memory_from_rollouts 批量构建时被纳入。
# 实际上系统为这个 rollout 生成了两条经验：
\`\`\`

#### 经验 1：process_global（全局策略经验）

\`\`\`python
upsert_memory_case(
    memory_id = "mem-fe31aac0deef414c",
    task_type = "process",
    tags = ["process", "kind:process_global", "equipment:azeotropic_distillation"],
    memory_kind = "process_global",
    reward = 0.2296,
    strategy_text = "先使用DSTWU简捷塔获取初值，再切换RadFrac...",
    config_snippet = "{完整的三塔配置JSON}",
    pitfalls_text = "run_simulation 失败链路\\n第1次: 配置错误...",
    failure_reason = "模拟引擎运行时错误...",
    fix_action = "太好了！这次模拟成功了。让我获取结果",
    lesson = "优先复用已知的配置/运行错误修复方案，避免重复踩坑。",
)
\`\`\`

#### 经验 2：pitfall_recovery（避坑恢复经验）

\`\`\`python
upsert_memory_case(
    memory_id = "mem-31dbc6cadc441b78",
    task_type = "process",
    tags = ["process", "kind:pitfall_recovery", "equipment:azeotropic_distillation"],
    memory_kind = "pitfall_recovery",
    reward = max(0.01, 0.2296 × 0.85) = 0.19516,  # 打折存储
    pitfalls_text = """
run_simulation 失败链路
第1次尝试: 错误类型=模拟配置错误
  错误信息=stream_data配置写入错误: 'NoneType' object has no attribute 'SetValueUnitAndBasis'
第2次尝试: 错误类型=模拟配置错误
  错误信息=同上
第3次尝试: 错误类型=模拟配置错误
  错误信息=blocks_DSTWU_data配置写入错误: 'nC6不是一个有效值'
第4次尝试: 错误类型=模拟运行错误
  错误信息=WARNING STREAM FEED-1...
...
第13次尝试: 错误类型=模拟运行错误
  错误信息=T1 T2 T3 Calculations begin...
""",
    failure_reason = "模拟引擎运行时错误（T3不收敛）",
    fix_action = "太好了！这次模拟成功了。让我获取结果",
    lesson = "优先复用已知的配置/运行错误修复方案，避免重复踩坑。",
)
\`\`\`

#### 提取逻辑 — \`extractors.py\` 的工作

\`\`\`python
# extract_run_simulation_attempts_from_spans(spans)
# 遍历所有 tool_execution span，找到 tool_name="run_simulation" 的结果
# 对每次尝试分类：
attempts = [
    {seq:1,  is_error:True,  error_type:"模拟配置错误", error_text:"'NoneType'..."},
    {seq:2,  is_error:True,  error_type:"模拟配置错误", error_text:"'NoneType'..."},
    {seq:3,  is_error:True,  error_type:"模拟配置错误", error_text:"'nC6不是一个有效值'"},
    {seq:4,  is_error:True,  error_type:"模拟运行错误", error_text:"WARNING..."},
    ...
    {seq:14, is_error:False, error_type:"none"}  # 最终成功
]

# build_pitfall_summary(attempts)
# → 汇总所有失败尝试，生成 pitfalls_text

# extract_pitfall_details_from_spans(spans)
# → 找到最后一次失败和之后的 thought（修复思路）
# → failure_reason = 最后一次失败的错误文本
# → fix_action = 失败后 Agent 的修复思考
# → lesson = "run_simulation 执行失败后通过修正配置重试成功"
\`\`\`

### 第四阶段：后续任务检索到避坑经验

当用户发起一个新的精馏塔任务（rollout \`ro-c663c1d16435\`）：

> 使用设备：换热器 Heater、反应器 RStoic、精馏塔 RadFrac
> 进料 → 换热器 → 反应器 → 精馏塔 → 产品

系统检索到 5 条经验，按 hit_rank 排列：

| rank | memory_id | 类型 | 分数 | 说明 |
|------|-----------|------|------|------|
| 1 | mem-fe31...414c | process_global | 18.63 | 三塔串联全局策略 |
| 2 | mem-8232...dc74 | process_stage | 17.34 | 阶段配置（第1阶段） |
| 3 | mem-ffd2...74f6 | process_stage | 17.34 | 阶段配置（第2阶段） |
| 4 | mem-31db...1b78 | pitfall_recovery | 17.23 | ⚠️ 避坑经验 |
| 5 | mem-3364...ef73 | process_stage | 17.33 | 阶段配置（第3阶段） |

#### 避坑经验的打分过程

\`\`\`python
# pipeline_ops.py:search_memory_cases 对 mem-31dbc6cadc441b78 的打分

# 1. 文本匹配
token_hits = 11 / 19 tokens  → +11.0
# "精馏塔", "RadFrac", "分离", "产品" 等命中

# 2. 结构化匹配
anchor(equipment): query=["radfrac","heatx","rstoic"] ∩ mem=["distl","radfrac","rplug"]
  → "radfrac" 命中 ✓
should(components): query 组分 ∩ mem 组分 → 部分命中
should(methods): query 无 ∩ mem=["PENG-ROB"] → 无加成
→ structured_match_score ≈ 1.6

# 3. 语义相似度
task_family: 都涉及精馏分离 → +0.8
task_type: process == process → +0.4
equipment_types: radfrac 命中 → +1.1
→ semantic_score ≈ 4.15

# 4. 经验类型加成
kind = "pitfall_recovery" → +0.5（低于 golden 的 1.2，但仍有加成）

# 5. reward 加成
reward = 0.19516 → +0.19516 × 0.3 = +0.059

# 6. 任务类型加成
process == process → +0.8

# 总分 ≈ 11.0 + 1.6 + 4.15 + 0.5 + 0.059 + 0.8 = 18.11
# 实际记录: match_score = 17.23
\`\`\`

#### 经验选择策略 — 为什么 pitfall 被选中

\`\`\`python
# pipeline_ops.py — process 模式选择策略
mode = "process"

# 第一步：选 1 条全局策略
pick_one(["process_global", "success_recovered", "success_golden"])
→ 选中 mem-fe31...414c (process_global, score=18.63)

# 第二步：选最多 2 条阶段经验
pick_many(["process_stage"], 2)
→ 选中 mem-8232...dc74 (score=17.34)
→ 选中 mem-ffd2...74f6 (score=17.34)

# 第三步：选最多 2 条避坑经验 ← 关键！
pick_many(["pitfall_recovery", "pitfall_failure"], 2)
→ 选中 mem-31db...1b78 (pitfall_recovery, score=17.23) ✅

# 第四步：补充到 top_k=5
→ 补充 mem-3364...ef73 (process_stage)
\`\`\`

#### 注入到 Agent Prompt 的内容

\`\`\`
【历史最佳实践参考（请优先复用）】

1. 任务: 使用三个 RadFrac 精馏塔串联分离四组分混合物...
   类型: process | reward: 0.23
   策略: 先使用DSTWU简捷塔获取初值，再切换RadFrac...
   配置片段: {"components": [...], "blocks": [T1,T2,T3], ...}
   风险: (无)

2. 任务: 同上（第1阶段配置）
   策略: 第1阶段：优先最小化修改，保留已验证的上游配置
   ...

3. 任务: 同上（第2阶段配置）
   ...

4. 任务: 同上  ← ⚠️ 避坑经验
   类型: process | reward: 0.20
   策略: (空)
   配置片段: {最终成功的配置}
   风险: run_simulation 失败链路
     第1次: 配置错误 - 'NoneType' object has no attribute 'SetValueUnitAndBasis'
     第2次: 配置错误 - 同上
     第3次: 配置错误 - 'nC6不是一个有效值'
     第4次: 运行时错误 - WARNING STREAM FEED-1...
     ...

5. 任务: 同上（第3阶段配置）
   ...

请保持与上述实践一致，优先最小改动，避免推翻已验证配置。
\`\`\`

Agent 看到第 4 条避坑经验后，会：
1. 避免使用 \`nC6\` 这样的 cid 命名（改用 Aspen 标准名称）
2. 注意 stream_data 的流量配置格式
3. 参考最终成功的配置，减少试错次数

#### 实际效果验证

该避坑经验被后续任务使用的记录：

| rollout | hit_rank | match_score | 任务结果 | reward |
|---------|----------|-------------|----------|--------|
| ro-c663... | 4 | 17.23 | succeeded | 0.13 |
| ro-a806... | 2 | 6.02 | succeeded | 0.77 |

经验被成功检索并帮助后续任务避免了相同的配置错误。
`;


const trainingMarkdown = `## 训练系统架构

\`\`\`
训练工作台 → 创建 RL Job → 采样阶段（收集轨迹）→ 训练阶段（优化提示词）→ 发布阶段
\`\`\`

支持离线和在线两种训练模式：

| 维度 | 选项 | 说明 |
|------|------|------|
| 算法 | RGO | 规则引导离线优化，基于轨迹数据生成提示词补丁 |
| 模式 | offline | 单轮：采样 → 训练，不自动发布 |
| 模式 | online | 多轮迭代：采样 → 训练 → 自动发布 → 再采样 |

## 训练任务创建 — \`rl_job_service.py:start_rl_job\`

\`\`\`python
POST /api/rl/jobs/start
{
    "tasks": ["模拟甲醇-水精馏塔...", "模拟换热器..."],
    "max_tasks": 4,
    "run_training": true,
    "training_mode": "online",      # test / online
    "online_iterations": 3,         # 在线迭代轮数
    "train_algo": "rgo",
    "collection_backend": "internal"
}
\`\`\`

系统创建 job 后通过 \`asyncio.create_task\` 异步执行。

## 采样阶段 — \`rl_worker_service.py:_run_collection_phase\`

\`\`\`
for 每个任务消息:
    1. 创建 CancellationToken
    2. 调用 execute_user_task() — 与工作台相同的 Agent 执行流程
    3. 收集 rollout_id 和执行状态
    4. 记录到 task_results
\`\`\`

采样阶段复用了工作台的完整 Agent 执行链路，每个任务都会：
- 经过经验检索（在线模式第 2 轮起禁用经验，纯测试新提示词）
- 完整执行 get_schema → run_simulation → get_result
- 计算 reward 并持久化到 SQLite

## 训练阶段 — \`training_process_service.py:run_training_subprocess\`

训练通过子进程调用 RL 训练脚本：

\`\`\`bash
python rl/src/train_prompt.py \\
    --db-path data/rollouts.db \\
    --mode online \\
    --prompt-dir backend/prompt/ \\
    --schema-dir backend/schema/ \\
    --output-root rl/training_runs/ \\
    --algo rgo \\
    --tag {job_id}
\`\`\`

### RGO 算法流程（规则引导离线优化）

\`\`\`
1. 从 SQLite 读取所有 rollout 轨迹数据
2. 分析失败模式：
   - 配置错误（schema 参数不正确）
   - 运行时错误（模拟不收敛）
   - 超时/连接错误
3. 提取高频错误模式和成功修复路径
4. 生成提示词优化补丁（写入 OPTIMIZATION_ZONE）
5. 输出候选提示词文件：
   - system_prompt_candidate.txt
   - schema_check_prompt_candidate.txt
   - thought_process_prompt_candidate.txt
6. 生成训练报告 training_report.md
\`\`\`

## Reward 计算 — \`rl/reward.py:calculate_reward_v1\`

Reward 是训练的核心信号，基于多维度加权计算：

### Unit 模式（单设备任务）

\`\`\`
reward = completion × 0.55 + efficiency × 0.20
       + recovery × 0.15 + pipeline × 0.10 - penalty

completion: run_simulation 成功且 get_result 成功 → 1.0
efficiency: exp(-0.35 × retry_count)  # 重试越少越高
recovery:   有失败但最终成功 → 1.0
pipeline:   get_schema(0.5) + get_result(0.5)
penalty:    config_fail × 0.10 + runtime_fail × 0.05
\`\`\`

### Process 模式（多设备流程任务）

\`\`\`
reward = completion × 0.45 + progress × 0.20
       + efficiency × 0.20 + recovery × 0.10
       + pipeline × 0.05 - penalty

completion: 完成轮次 ≥ 预期轮次 → 1.0
progress:   完成轮次 / 预期轮次
efficiency: exp(-0.18 × overhead)  # 多余调用越少越高
\`\`\`

### 结果准确性评估

系统还会推断用户期望的输出类型（温度/压力/流量/组成），检查实际结果是否覆盖：

\`\`\`python
requested_outputs = infer_requested_outputs(user_message)
# → {"temperature", "composition", "flowrate"}
coverage = 实际返回中命中的输出类型 / 期望输出类型数
\`\`\`

## 在线训练迭代 — \`rl_worker_service.py:run_rl_job\`

\`\`\`
for iteration in range(1, online_iterations + 1):
    1. 采样阶段：执行所有任务，收集轨迹
    2. 训练阶段：运行 RGO 生成候选提示词
    3. 自动发布：
       a. 调用 apply_prompt_candidates.py 覆盖 prompt 文件
       b. 热重载 prompt 模块（importlib.reload）
       c. 下一轮采样使用新提示词
    4. 在线模式第 2 轮起禁用经验检索，纯测试新提示词效果
\`\`\`

## 提示词发布

\`\`\`
1. 读取训练产物目录 training_runs/run_{id}/
2. 执行 apply_prompt_candidates.py
   → 将候选提示词覆盖到 backend/prompt/ 目录
3. 发布后可在提示词管理页面查看和编辑当前生效的提示词
\`\`\`
`;

const databaseMarkdown = `## 数据库概览

系统使用 SQLite 作为持久化存储，主数据库文件位于 \`rl_data/aspen_trajectories.db\`。

初始化代码：\`telemetry/repository.py:init_rollout_tables\`

## 核心表结构

### rollouts — 任务执行记录

| 字段 | 类型 | 说明 |
|------|------|------|
| rollout_id | TEXT PK | 任务唯一标识 |
| attempt_id | TEXT | 尝试标识 |
| status | TEXT | running / succeeded / failed / stopped |
| mode | TEXT | online / test |
| start_time | REAL | 开始时间戳 |
| end_time | REAL | 结束时间戳 |
| input_json | TEXT | 任务输入（task_id, user_requirement） |
| metadata_json | TEXT | 元数据（source, user_message, task_type 等） |
| user_id | TEXT | 用户ID |

### spans — 执行跨度记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| rollout_id | TEXT | 关联的 rollout |
| span_id | TEXT | 跨度唯一标识 |
| name | TEXT | 类型名称（见下表） |
| attributes_json | TEXT | 详细属性 JSON |

span name 类型：

| name | 说明 | attributes 内容 |
|------|------|-----------------|
| task_started | 任务开始 | task_id, message |
| thought | Agent 思考 | content |
| tool_call_request | 工具调用请求 | tool_calls: [{function_name, args}] |
| tool_execution | 工具执行结果 | tool_results: [{call_id, result, is_error}] |
| task_progress | 进度事件 | stage, tool_name, status |
| memory_retrieval | 经验检索 | hit_count, memory_ids, scores |
| prompt_assignment | 提示词分配 | version_id, bucket, mode |
| reward | 奖励计算 | reward, metrics, breakdown |
| assistant_response | 最终回复 | content |
| error | 错误记录 | error, traceback |

### memory_cases — 经验库

| 字段 | 类型 | 说明 |
|------|------|------|
| memory_id | TEXT PK | 经验唯一标识 |
| task_hash | TEXT | 任务哈希（去重用） |
| task_text | TEXT | 任务描述 |
| task_type | TEXT | unit / process |
| tags_json | TEXT | 标签列表 |
| strategy_text | TEXT | 策略摘要 |
| config_snippet | TEXT | 关键配置 JSON |
| pitfalls_text | TEXT | 避坑经验 |
| failure_reason | TEXT | 失败原因 |
| fix_action | TEXT | 修复动作 |
| lesson | TEXT | 经验教训 |
| reward | REAL | 任务奖励值 |
| tool_call_count | INTEGER | 工具调用次数 |
| features_json | TEXT | 匹配特征 |
| source_rollout_id | TEXT | 来源任务ID |

### memory_usage_events — 经验使用追踪

| 字段 | 类型 | 说明 |
|------|------|------|
| usage_id | TEXT PK | 使用事件ID |
| rollout_id | TEXT | 使用经验的任务 |
| memory_id | TEXT | 被使用的经验 |
| hit_rank | INTEGER | 命中排名 |
| match_score | REAL | 匹配分数 |
| status | TEXT | pending / succeeded / failed |
| reward | REAL | 使用后的任务 reward |

### memory_documents — 经验文档索引

| 字段 | 说明 |
|------|------|
| memory_id | 关联经验ID |
| md_path | Markdown 文件路径 |
| md_sha1 | 文件内容哈希 |
| features_json | 匹配特征 |

### users — 用户表

| 字段 | 说明 |
|------|------|
| user_id | 用户唯一标识 |
| phone | 手机号（唯一） |
| password | 密码哈希 |
| role | user / admin |
| nickname | 昵称 |

### chat_sessions — 会话表

| 字段 | 说明 |
|------|------|
| session_id | 会话唯一标识 |
| user_id | 所属用户 |
| title | 会话标题 |
| messages_json | 消息历史 JSON |

补充说明：当前前端工作台会话主要保存在浏览器 \`sessionStorage\` 中；虽然服务端提供了 \`chat_sessions\` 表与 \`/api/sessions\` 接口，但当前工作台页面还没有接入服务端会话同步。

## 关键数据流

\`\`\`
任务执行:
  persist_rollout_start() → INSERT rollouts
  persist_span() → INSERT spans (每个事件一条)
  persist_rollout_status() → UPDATE rollouts.status

经验写入:
  upsert_memory_case() → INSERT/UPDATE memory_cases
  write_memory_markdown_and_index() → 写 .md 文件 + INSERT memory_documents

经验检索:
  search_memory_cases() → SELECT memory_cases + LEFT JOIN memory_usage_events
  log_memory_usage_events() → INSERT memory_usage_events
  finalize_memory_usage_events() → UPDATE memory_usage_events (任务结束时)

统计查询:
  query_statistics_sqlite() → 聚合 rollouts 表统计
  query_memory_quality_metrics() → 聚合 memory_usage_events 计算经验质量
\`\`\`

## 文件存储

除 SQLite 外，系统还使用文件系统存储：

| 路径 | 内容 |
|------|------|
| \`rl_data/memory_docs/\` | 经验 Markdown 文档 |
| \`rl/outputs/training_runs/\` | 训练产物（候选提示词、报告） |
| \`rl/exports/\` | 导出的训练结果 |
| \`app/prompts/\` | 当前生效的提示词文件 |
`;

const aboutMarkdown = `## 系统架构

| 层级 | 技术栈 | 说明 |
|------|--------|------|
| 前端 | Vue 3 + Vite + TailwindCSS | SPA 单页应用，使用 fetch 流式解析 SSE |
| 后端 | FastAPI + AutoGen AgentChat | 异步 API，Agent 自主循环 |
| Rollout 管理 | AgentLightning | InMemoryLightningStore 管理 rollout 生命周期，emit_message/emit_annotation/emit_reward 事件发射 |
| LLM | OpenAI 兼容接口 | 从配置文件加载模型与参数，运行时创建 Agent 客户端 |
| RL训练 | RGO 算法 | 子进程执行，支持在线多轮迭代 |
| 模拟服务 | Aspen via HTTP API | 远程调用 Aspen Plus 模拟引擎 |
| 数据存储 | SQLite | rollouts/spans/memory/users 等表 |
| 经验系统 | 规则匹配 + 语义相似度 | 自动提取、检索、注入 |

## 核心工作流

\`\`\`
用户输入任务 → 前端 fetch 建立流式请求
  → 经验检索（默认 top-5 相关经验注入 prompt）
  → Agent 自主循环（get_schema → run_simulation → get_result）
  → 失败自动重试（错误分类 + 配置修正）
  → 计算 reward（多维度加权评分）
  → 任务历史页聚合展示指标、错误与产物
  → RL 训练持续优化提示词
\`\`\`

## 版本信息

- 系统名称：Aspen 流程模拟智能体系统
- 当前版本：以前端帮助中心文案为准，代码中未见统一版本号常量
- Agent 框架：AutoGen AgentChat
- 最大工具迭代：100 轮
`;

const _renderMd = (md) => {
  try {
    return DOMPurify.sanitize(marked.parse(md));
  } catch (error) {
    console.error('Failed to parse markdown:', error);
    return '<p>加载失败</p>';
  }
};

const agentHtml = computed(() => _renderMd(agentMarkdown));
const memoryHtml = computed(() => _renderMd(memoryMarkdown));
const trainingHtml = computed(() => _renderMd(trainingMarkdown));
const databaseHtml = computed(() => _renderMd(databaseMarkdown));
const aboutHtml = computed(() => _renderMd(aboutMarkdown));
</script>

<style scoped>
.help-markdown {
  font-size: 14px;
  line-height: 1.7;
  color: #1f2328;
}

.help-markdown :deep(h1) {
  font-size: 24px;
  font-weight: 600;
  margin-top: 24px;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #d1d9e0;
  color: #1f2328;
}

.help-markdown :deep(h1:first-child) {
  margin-top: 0;
}

.help-markdown :deep(h2) {
  font-size: 20px;
  font-weight: 600;
  margin-top: 24px;
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #eaeef2;
  color: #1f2328;
}

.help-markdown :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  margin-top: 20px;
  margin-bottom: 10px;
  color: #1f2328;
}

.help-markdown :deep(h4) {
  font-size: 14px;
  font-weight: 600;
  margin-top: 16px;
  margin-bottom: 8px;
  color: #1f2328;
}

.help-markdown :deep(p) {
  margin-top: 0;
  margin-bottom: 12px;
  color: #1f2328;
}

.help-markdown :deep(ul),
.help-markdown :deep(ol) {
  margin-top: 0;
  margin-bottom: 12px;
  padding-left: 24px;
}

.help-markdown :deep(li) {
  margin-bottom: 6px;
  color: #1f2328;
}

.help-markdown :deep(li > p) {
  margin-bottom: 6px;
}

.help-markdown :deep(code) {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  background: #f6f8fa;
  padding: 2px 6px;
  border-radius: 3px;
  color: #1f2328;
}

.help-markdown :deep(pre) {
  background: #f6f8fa;
  border: 1px solid #d1d9e0;
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  margin-top: 0;
  margin-bottom: 12px;
}

.help-markdown :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 12px;
  line-height: 1.5;
}

.help-markdown :deep(blockquote) {
  margin: 0 0 12px 0;
  padding: 0 16px;
  border-left: 3px solid #d1d9e0;
  color: #656d76;
}

.help-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 12px;
  font-size: 13px;
}

.help-markdown :deep(table th) {
  text-align: left;
  padding: 8px 12px;
  font-weight: 600;
  background: #f6f8fa;
  border: 1px solid #d1d9e0;
  color: #1f2328;
}

.help-markdown :deep(table td) {
  padding: 8px 12px;
  border: 1px solid #d1d9e0;
  color: #1f2328;
}

.help-markdown :deep(a) {
  color: #0969da;
  text-decoration: none;
}

.help-markdown :deep(a:hover) {
  text-decoration: underline;
}

.help-markdown :deep(hr) {
  border: 0;
  border-top: 1px solid #d1d9e0;
  margin: 20px 0;
}

.help-markdown :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 12px 0;
}

.help-markdown :deep(strong) {
  font-weight: 600;
  color: #1f2328;
}

.help-markdown :deep(em) {
  font-style: italic;
}
</style>

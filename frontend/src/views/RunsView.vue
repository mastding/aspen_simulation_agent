<template>
  <SettingsLayout
    title="任务历史"
    :active="activeTab"
    :groups="sidebarGroups"
    :fluid="true"
    @select="activeTab = $event"
  >
    <!-- Error Display -->
    <div v-if="error" class="gh-panel" style="border-color: #d1242f; margin-bottom: 16px;">
      <div class="gh-panel-body">
        <div style="color: #d1242f; font-size: 13px;">{{ error }}</div>
      </div>
    </div>

    <!-- ============ 任务概览 ============ -->
    <section v-show="activeTab === 'overview'">
      <h2 class="gh-heading">任务概览</h2>

      <!-- Action buttons -->
      <div style="display: flex; gap: 8px; margin-bottom: 16px;">
        <button class="gh-btn gh-btn-primary" @click="refreshAll">刷新</button>
      </div>

      <!-- Stat cards (merged from 指标概览 + 任务概览) -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px;">
        <div class="gh-stat-card">
          <div class="gh-stat-label">总任务数</div>
          <div class="gh-stat-value">{{ metrics.total_rollouts || runs.length }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">成功</div>
          <div class="gh-stat-value" style="color: #1a7f37;">{{ metrics.succeeded || runs.filter(r => r.status === 'succeeded').length }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">失败</div>
          <div class="gh-stat-value" style="color: #d1242f;">{{ metrics.failed || runs.filter(r => r.status === 'failed').length }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">运行中</div>
          <div class="gh-stat-value" style="color: #9a6700;">{{ runs.filter(r => r.status === 'running').length }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">平均奖励</div>
          <div class="gh-stat-value">{{ metrics.average_reward?.toFixed(2) || avgReward }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">总工具调用</div>
          <div class="gh-stat-value">{{ metrics.total_tool_calls || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">每任务工具调用</div>
          <div class="gh-stat-value">{{ metrics.average_tool_calls_per_rollout?.toFixed(2) || '0.00' }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">记忆命中率</div>
          <div class="gh-stat-value">{{ memoryHitRate }}</div>
        </div>
      </div>
    </section>

    <!-- ============ 任务列表 ============ -->
    <section v-show="activeTab === 'tasks'">
      <h2 class="gh-heading">任务列表</h2>

      <!-- Action buttons -->
      <div style="display: flex; gap: 8px; margin-bottom: 16px;">
        <button class="gh-btn gh-btn-primary" @click="refreshAll">刷新</button>
        <button class="gh-btn gh-btn-danger" @click="clearAllHistory">清空任务历史</button>
      </div>

      <!-- Filters (inline) -->
      <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center;">
        <select v-model="memorySearchFilter" class="gh-select" style="min-width: 160px;">
          <option value="all">全部</option>
          <option value="memory_hit">记忆命中</option>
          <option value="memory_miss">记忆未命中</option>
        </select>
        <input
          v-model="taskContentFilter"
          class="gh-input"
          placeholder="搜索任务内容..."
          style="min-width: 200px;"
        />
        <span style="font-size: 12px; color: #656d76;">
          显示 {{ filteredRuns.length }} / {{ runs.length }} 条
        </span>
      </div>

      <!-- Task table -->
      <div class="gh-panel">
        <div class="gh-panel-body" style="padding: 0; overflow-x: auto;">
          <table ref="taskTableRef" class="gh-table resizable-table">
            <thead>
              <tr>
                <th style="min-width: 100px;">任务ID</th>
                <th style="min-width: 70px;">状态</th>
                <th style="min-width: 80px;">用户</th>
                <th style="min-width: 140px;">开始时间</th>
                <th style="min-width: 70px;">耗时</th>
                <th style="min-width: 60px;">奖励</th>
                <th style="min-width: 80px;">工具调用</th>
                <th style="min-width: 100px;">记忆命中</th>
                <th style="min-width: 200px;">任务内容</th>
                <th style="min-width: 80px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="filteredRuns.length === 0">
                <td colspan="10" class="gh-empty">暂无任务记录</td>
              </tr>
              <tr v-for="run in filteredRuns" :key="run.rollout_id">
                <td>
                  <span style="font-family: ui-monospace, monospace; font-size: 12px;">
                    {{ run.rollout_id?.slice(0, 8) || '-' }}
                  </span>
                </td>
                <td>
                  <span class="gh-label" :class="statusClass(run.status)">
                    {{ run.status || '-' }}
                  </span>
                </td>
                <td style="font-size: 12px; color: #1f2328;">
                  {{ run.user_display_name || 'admin' }}
                </td>
                <td style="font-size: 12px; color: #656d76;">
                  {{ fmtDateTime(run.start_time) }}
                </td>
                <td style="font-size: 12px;">
                  {{ fmtDurationSec(run.end_time && run.start_time ? run.end_time - run.start_time : null) }}
                </td>
                <td>
                  <span :style="{ fontWeight: 600, color: getReward(run) > 0 ? '#1a7f37' : getReward(run) < 0 ? '#d1242f' : '#1f2328' }">
                    {{ getReward(run) != null ? getReward(run).toFixed(2) : '-' }}
                  </span>
                </td>
                <td>
                  <span style="font-size: 12px; font-weight: 600; color: #656d76;">
                    {{ run.summary?.tool_call_count ?? '-' }}
                  </span>
                </td>
                <td>
                  <template v-if="hasMemoryEnrichment(run)">
                    <span v-if="run.summary?.memory_hit_count > 0" class="gh-label gh-label-success">
                      命中 ({{ run.summary.memory_hit_count }})
                    </span>
                    <span v-else class="gh-label gh-label-warning">
                      未命中
                    </span>
                  </template>
                  <span v-else class="gh-label gh-label-muted">无检索</span>
                </td>
                <td>
                  <span style="font-size: 12px; color: #656d76; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                    {{ extractMessage(run) }}
                  </span>
                </td>
                <td>
                  <div style="display: flex; gap: 4px;">
                    <button class="gh-btn" style="font-size: 12px; padding: 3px 8px;" @click="viewRunDetail(run)">
                      详情
                    </button>
                    <button class="gh-btn gh-btn-danger" style="font-size: 12px; padding: 3px 8px;" @click.stop="deleteRollout(run)">
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ============ 每日趋势 ============ -->
    <section v-show="activeTab === 'daily'">
      <h2 class="gh-heading">每日趋势</h2>
      <div class="gh-panel">
        <div class="gh-panel-body" style="padding: 0;">
          <table class="gh-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>总计</th>
                <th>成功</th>
                <th>失败</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!metrics.daily_trend || metrics.daily_trend.length === 0">
                <td colspan="4" class="gh-empty">暂无数据</td>
              </tr>
              <tr v-for="day in metrics.daily_trend" :key="day.date">
                <td>{{ day.date }}</td>
                <td>{{ day.total }}</td>
                <td><span class="gh-label gh-label-success">{{ day.succeeded }}</span></td>
                <td><span class="gh-label gh-label-danger">{{ day.failed }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ============ 高频错误 ============ -->
    <section v-show="activeTab === 'errors'">
      <h2 class="gh-heading">高频错误</h2>
      <div class="gh-panel">
        <div class="gh-panel-body" style="padding: 0; overflow-x: auto;">
          <table class="gh-table">
            <thead>
              <tr>
                <th style="width: 60px;">次数</th>
                <th style="min-width: 100px;">任务类型</th>
                <th style="min-width: 100px;">错误类型</th>
                <th style="min-width: 150px;">任务ID</th>
                <th style="min-width: 300px;">错误信息</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!metrics.top_errors || metrics.top_errors.length === 0">
                <td colspan="5" class="gh-empty">暂无错误记录</td>
              </tr>
              <tr v-for="(err, idx) in metrics.top_errors" :key="idx">
                <td><span class="gh-label gh-label-danger">{{ err.count }}</span></td>
                <td>
                  <span class="gh-label" :class="err.task_type === 'unit' ? 'gh-label-info' : 'gh-label-purple'">
                    {{ err.task_type === 'unit' ? '单元模拟' : err.task_type === 'process' ? '流程模拟' : '-' }}
                  </span>
                </td>
                <td>
                  <span v-if="err.error_category" class="gh-label gh-label-warning">
                    {{ err.error_category === 'config' ? '配置错误' : err.error_category === 'runtime' ? '运行错误' : err.error_category }}
                  </span>
                  <span v-else style="color: #656d76;">-</span>
                </td>
                <td>
                  <RouterLink v-if="err.rollout_id" :to="`/runs?rollout_id=${err.rollout_id}`" style="color: #0969da; text-decoration: none; font-size: 12px;">
                    {{ err.rollout_id }}
                  </RouterLink>
                  <span v-else style="color: #656d76; font-size: 12px;">-</span>
                </td>
                <td style="font-family: ui-monospace, monospace; font-size: 11px; color: #656d76; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="err.message">
                  {{ err.message }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ============ Run Detail Modal ============ -->
    <div v-if="selectedRun" class="runs-modal-overlay" @click.self="selectedRun = null">
      <div class="gh-panel" style="width: 680px; max-width: 90vw; max-height: 80vh; display: flex; flex-direction: column;">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">
            任务详情 - {{ selectedRun.rollout_id?.slice(0, 8) || '-' }}
          </span>
          <button class="gh-btn" @click="selectedRun = null" style="padding: 3px 8px;">关闭</button>
        </div>
        <div class="gh-panel-body" style="overflow-y: auto;">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
            <div>
              <span style="font-size: 12px; color: #656d76;">状态</span>
              <div><span class="gh-label" :class="statusClass(selectedRun.status)">{{ selectedRun.status }}</span></div>
            </div>
            <div>
              <span style="font-size: 12px; color: #656d76;">奖励</span>
              <div style="font-weight: 600;">{{ getReward(selectedRun) != null ? getReward(selectedRun).toFixed(2) : '-' }}</div>
            </div>
            <div>
              <span style="font-size: 12px; color: #656d76;">开始时间</span>
              <div style="font-size: 13px;">{{ fmtDateTime(selectedRun.start_time) }}</div>
            </div>
            <div>
              <span style="font-size: 12px; color: #656d76;">耗时</span>
              <div style="font-size: 13px;">{{ fmtDurationSec(selectedRun.end_time && selectedRun.start_time ? selectedRun.end_time - selectedRun.start_time : null) }}</div>
            </div>
            <div v-if="selectedRun.summary?.dominant_failure_category">
              <span style="font-size: 12px; color: #656d76;">主失败类型</span>
              <div><span class="gh-label gh-label-danger">{{ selectedRun.summary.dominant_failure_category }}</span></div>
            </div>
          </div>
          <hr class="gh-divider" />
          <div>
            <span style="font-size: 12px; font-weight: 600; color: #1f2328;">任务内容</span>
            <div class="gh-code" style="margin-top: 8px;">{{ extractMessage(selectedRun) }}</div>
          </div>
          <div v-if="selectedRun.error" style="margin-top: 12px;">
            <span style="font-size: 12px; font-weight: 600; color: #d1242f;">错误信息</span>
            <div class="gh-code" style="margin-top: 8px; border-color: #ffcecb; background: #ffebe9;">{{ selectedRun.error }}</div>
          </div>

          <!-- Execution Process -->
          <div v-if="selectedRunSpans.length > 0" style="margin-top: 16px;">
            <hr class="gh-divider" />
            <div style="margin-top: 16px;">
              <span style="font-size: 12px; font-weight: 600; color: #1f2328;">执行过程（{{ selectedRunSpans.length }} 步）</span>
              <div style="margin-top: 8px; max-height: 400px; overflow-y: auto;">
                <div
                  v-for="(span, idx) in selectedRunSpans"
                  :key="span.span_id"
                  style="padding: 8px; border-bottom: 1px solid #eaeef2; font-size: 12px;"
                >
                  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                    <span style="color: #656d76; font-family: monospace;">{{ idx + 1 }}.</span>
                    <span style="font-weight: 600; color: #1f2328;">{{ formatSpanName(span.name) }}</span>
                    <span v-if="span.attributes?.tool" class="gh-label gh-label-info" style="font-size: 10px;">{{ span.attributes.tool }}</span>
                  </div>
                  <div v-if="getSpanSummary(span)" style="color: #656d76; margin-left: 20px; margin-bottom: 4px;">
                    {{ getSpanSummary(span) }}
                  </div>
                  <div v-if="getSpanDetails(span)" class="gh-code" style="margin-left: 20px; font-size: 11px; white-space: pre-wrap;">{{ getSpanDetails(span) }}</div>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="loadingSpans" style="margin-top: 16px; text-align: center; color: #656d76; font-size: 12px;">
            加载执行过程...
          </div>
        </div>
      </div>
    </div>

    <!-- ============ 文件产物 ============ -->
    <section v-show="activeTab === 'files_all'">
      <h2 class="gh-heading">文件产物</h2>
      <div v-if="artifactsLoading" class="gh-panel">
        <div class="gh-panel-body">
          <div style="text-align: center; color: #656d76; font-size: 13px;">加载中...</div>
        </div>
      </div>
      <div v-else-if="artifactsList.length === 0" class="gh-panel">
        <div class="gh-empty">暂无产物数据</div>
      </div>
      <div v-else class="space-y-4">
        <div v-for="artifact in artifactsList" :key="artifact.rollout_id" class="gh-panel">
          <div class="gh-panel-header">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="gh-panel-header-title">{{ artifact.rollout_id }}</span>
                <span class="gh-label" :class="{ 'gh-label-success': artifact.status === 'succeeded', 'gh-label-danger': artifact.status === 'failed', 'gh-label-info': artifact.status === 'running', 'gh-label-muted': !['succeeded','failed','running'].includes(artifact.status) }">{{ artifact.status }}</span>
              </div>
              <div v-if="artifact.message" class="gh-panel-header-sub">{{ artifact.message }}</div>
            </div>
            <button @click="toggleArtifactCollapse(artifact.rollout_id)" class="gh-btn" :aria-expanded="!collapsedArtifacts.has(artifact.rollout_id)">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" style="width: 16px; height: 16px; transition: transform 0.15s;" :style="{ transform: collapsedArtifacts.has(artifact.rollout_id) ? 'rotate(-90deg)' : 'rotate(0deg)' }"><path fill-rule="evenodd" d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" /></svg>
            </button>
          </div>
          <div v-show="!collapsedArtifacts.has(artifact.rollout_id)" class="gh-panel-body">
            <div v-if="!artifact.files || artifact.files.length === 0" class="gh-empty" style="padding: 16px;">暂无文件</div>
            <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px;">
              <div v-for="(file, idx) in artifact.files" :key="idx" class="gh-panel" style="padding: 12px; display: flex; flex-direction: column; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span class="gh-label gh-label-purple" style="font-size: 11px;">{{ fileTypeLabel(file.type) }}</span>
                </div>
                <div style="font-size: 12px; color: #1f2328; word-break: break-all; flex: 1;">{{ file.name || file.path || '未命名文件' }}</div>
                <button @click="downloadArtifact(artifact.rollout_id, file)" class="gh-btn gh-btn-primary" style="width: 100%; justify-content: center;">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" style="width: 14px; height: 14px;"><path d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z" /><path d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z" /></svg>
                  下载
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

  </SettingsLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import SettingsLayout from "../components/SettingsLayout.vue";
import { fetchJson, postJson, deleteJson, fmtDateTime } from "../services/api";
import { getToken } from "../services/auth";
import { useColumnResize } from "../composables/useColumnResize";
import "../assets/github-theme.css";

const route = useRoute();

/* ---- Sidebar ---- */
const activeTab = ref("overview");
const taskTableRef = ref(null);
useColumnResize(taskTableRef);
const _i = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;
const sidebarGroups = [
  {
    label: "",
    items: [
      { id: "overview", label: "任务概览", icon: _i("M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z") },
      { id: "tasks", label: "任务列表", icon: _i("M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01") },
      { id: "daily", label: "每日趋势", icon: _i("M3 3v18h18M7 16l4-4 4 4 5-6") },
      { id: "errors", label: "高频错误", icon: _i("M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z") },
      { id: "files_all", label: "文件产物", icon: _i("M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8") },
    ],
  },
];

/* ---- State ---- */
const runs = ref([]);
const error = ref(null);
const memorySearchFilter = ref("all");
const taskContentFilter = ref("");
const selectedRun = ref(null);
const selectedRunSpans = ref([]);
const loadingSpans = ref(false);
const metrics = ref({
  total_rollouts: 0,
  succeeded: 0,
  failed: 0,
  average_reward: 0,
  total_tool_calls: 0,
  average_tool_calls_per_rollout: 0,
  daily_trend: [],
  top_errors: [],
});

/* ---- Artifacts State ---- */
const artifactsList = ref([]);
const artifactsLoading = ref(false);
const collapsedArtifacts = ref(new Set());

/* ---- Computed ---- */
const filteredRuns = computed(() => {
  let result = runs.value;

  // Filter by memory / enrichment
  if (memorySearchFilter.value === "memory_hit") {
    result = result.filter(r => r.summary?.memory_hit_count > 0);
  } else if (memorySearchFilter.value === "memory_miss") {
    result = result.filter(r => r.summary?.memory_search_used === true && (r.summary?.memory_hit_count || 0) === 0);
  }

  // Filter by task content keyword
  if (taskContentFilter.value.trim()) {
    const kw = taskContentFilter.value.trim().toLowerCase();
    result = result.filter(r => extractMessage(r).toLowerCase().includes(kw));
  }

  return result;
});

const avgReward = computed(() => {
  if (runs.value.length === 0) return "0.00";
  const total = runs.value.reduce((sum, r) => sum + (getReward(r) || 0), 0);
  return (total / runs.value.length).toFixed(2);
});

const memoryHitRate = computed(() => {
  const withMemory = runs.value.filter(r => hasMemoryEnrichment(r));
  if (withMemory.length === 0) return "N/A";
  const hits = withMemory.filter(r => r.summary?.memory_hit_count > 0);
  return ((hits.length / withMemory.length) * 100).toFixed(1) + "%";
});

/* ---- Helpers ---- */
function getReward(run) {
  if (!run) return null;
  const reward = run.summary?.reward;
  if (reward == null) return null;
  return typeof reward === 'string' ? parseFloat(reward) : reward;
}

function hasMemoryEnrichment(run) {
  return run.summary?.memory_search_used === true || (run.summary?.memory_hit_count || 0) > 0;
}

function getEnrichmentBadges(run) {
  const badges = [];
  if (run.summary?.memory_hit_count > 0) {
    badges.push({ text: "记忆命中", cls: "gh-label-success" });
  } else if (run.summary?.memory_search_used === true) {
    badges.push({ text: "记忆未命中", cls: "gh-label-warning" });
  }
  return badges;
}

function fmtDurationSec(sec) {
  if (sec == null || sec === undefined) return "-";
  if (sec < 60) return sec.toFixed(1) + "s";
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(0);
  return `${m}m ${s}s`;
}

function statusClass(status) {
  switch (status) {
    case "success":
    case "succeeded":
      return "gh-label-success";
    case "failed":
      return "gh-label-danger";
    case "running":
      return "gh-label-warning";
    default:
      return "gh-label-muted";
  }
}

function extractMessage(run) {
  if (!run) return "-";
  if (run.metadata?.user_message) return run.metadata.user_message;
  if (run.input?.user_requirement) return run.input.user_requirement;
  if (run.input?.task_id) return run.input.task_id;
  return "-";
}

/* ---- API calls ---- */
async function loadRuns() {
  try {
    error.value = null;
    const data = await fetchJson("/api/rollouts?limit=100&offset=0");
    runs.value = Array.isArray(data) ? data : data.rollouts || [];
  } catch (err) {
    error.value = err.message || "加载任务列表失败";
  }
}

async function loadMetrics() {
  try {
    metrics.value = await fetchJson("/api/metrics/overview");
  } catch (err) {
    console.warn("加载指标数据失败:", err);
  }
}

async function refreshAll() {
  await Promise.all([loadRuns(), loadMetrics()]);
}

async function clearAllHistory() {
  if (!confirm("确定要清空所有任务历史吗？此操作不可撤销。")) return;
  try {
    error.value = null;
    await postJson("/api/rollouts/clear", {});
    runs.value = [];
  } catch (err) {
    error.value = err.message || "清空任务历史失败";
  }
}

async function deleteRollout(run) {
  if (!confirm(`确定要删除任务 ${run.rollout_id?.slice(0, 8)} 吗？`)) return;
  try {
    error.value = null;
    const resp = await deleteJson(`/api/rollouts/${run.rollout_id}`);
    if (resp.deleted) {
      runs.value = runs.value.filter(r => r.rollout_id !== run.rollout_id);
    } else {
      error.value = resp.message || "删除失败";
    }
  } catch (err) {
    error.value = err.message || "删除任务失败";
  }
}

async function viewRunDetail(run) {
  selectedRun.value = run;
  selectedRunSpans.value = [];
  loadingSpans.value = true;

  try {
    const data = await fetchJson(`/api/rollouts/${run.rollout_id}/spans`);
    selectedRunSpans.value = Array.isArray(data.spans) ? data.spans : [];
  } catch (err) {
    console.error("Failed to load spans:", err);
  } finally {
    loadingSpans.value = false;
  }
}

function formatSpanName(name) {
  const nameMap = {
    'task_started': '任务开始',
    'memory_retrieval': '记忆检索',
    'tool_call': '工具调用',
    'tool_call_request': '工具调用请求',
    'tool_execution': '工具执行',
    'tool_result': '工具结果',
    'llm_call': 'LLM调用',
    'task_completed': '任务完成',
    'prompt_assignment': '提示词分配',
    'memory_search': '记忆搜索',
    'memory_hit': '记忆命中',
    'thought': '思考',
    'task_progress': '任务进度',
    'assistant_response': 'AI响应',
    'file_download': '文件下载',
    'reward': '奖励评分',
    'policy_suggestion': '策略建议',
  };
  return nameMap[name] || name;
}

function getSpanSummary(span) {
  const attrs = span.attributes || {};

  if (span.name === 'memory_retrieval' || span.name === 'memory_search') {
    const hitCount = attrs.hit_count || 0;
    if (hitCount > 0) {
      const scores = attrs.scores || [];
      const topMemories = scores.slice(0, 3).map(s => s.memory_id?.slice(0, 8) || '-').join(', ');
      return `命中 ${hitCount} 条记忆: ${topMemories}`;
    }
    return '未命中记忆';
  }

  if (span.name === 'tool_call_request') {
    const toolCalls = attrs.tool_calls || [];
    if (toolCalls.length > 0) {
      return `调用 ${toolCalls.length} 个工具: ${toolCalls.map(tc => tc.function_name).join(', ')}`;
    }
    return '工具调用请求';
  }

  if (span.name === 'tool_execution') {
    const toolResults = attrs.tool_results || [];
    if (toolResults.length > 0) {
      const successCount = toolResults.filter(tr => !tr.is_error).length;
      return `执行 ${toolResults.length} 个工具，成功 ${successCount} 个`;
    }
    return '工具执行';
  }

  if (span.name === 'thought') {
    const content = attrs.content || '';
    return content.length > 100 ? content.slice(0, 100) + '...' : content;
  }

  if (span.name === 'llm_call') {
    const tokens = attrs.total_tokens || attrs.tokens;
    return tokens ? `tokens: ${tokens}` : '';
  }

  if (span.name === 'prompt_assignment') {
    const version = attrs.selected_version_id;
    return version ? `版本: ${version}` : '';
  }

  if (span.name === 'task_progress') {
    const stage = attrs.stage || '';
    const status = attrs.status || '';
    return `${stage} - ${status}`;
  }

  if (span.name === 'reward') {
    const reward = attrs.reward;
    return reward != null ? `奖励: ${reward.toFixed(4)}` : '';
  }

  return '';
}

function getSpanDetails(span) {
  const attrs = span.attributes || {};
  const details = [];

  if (span.name === 'memory_retrieval' || span.name === 'memory_search') {
    const scores = attrs.scores || [];
    if (scores.length > 0) {
      details.push('记忆匹配详情:');
      scores.forEach((s, i) => {
        const memId = s.memory_id || '-';
        const score = s.score != null ? s.score.toFixed(3) : '-';
        const successRate = s.match?.quality?.success_rate != null ? (s.match.quality.success_rate * 100).toFixed(1) + '%' : '-';
        details.push(`  ${i + 1}. ${memId}`);
        details.push(`     分数: ${score} | 成功率: ${successRate}`);
        if (s.match?.semantic_matches) {
          details.push(`     语义匹配: ${JSON.stringify(s.match.semantic_matches, null, 2)}`);
        }
      });
    }
  }

  if (span.name === 'tool_call_request') {
    const toolCalls = attrs.tool_calls || [];
    if (toolCalls.length > 0) {
      details.push('工具调用请求:');
      toolCalls.forEach((tc, i) => {
        details.push(`\n${i + 1}. 工具: ${tc.function_name}`);
        details.push(`   调用ID: ${tc.id}`);
        if (tc.args) {
          details.push('   参数:');
          details.push(tc.args);
        }
      });
    }
  }

  if (span.name === 'tool_execution') {
    const toolResults = attrs.tool_results || [];
    if (toolResults.length > 0) {
      details.push('工具执行结果:');
      toolResults.forEach((tr, i) => {
        details.push(`\n${i + 1}. 工具: ${tr.tool_name || '-'}`);
        details.push(`   调用ID: ${tr.call_id}`);
        details.push(`   状态: ${tr.is_error ? '失败' : '成功'}`);
        if (tr.result) {
          details.push('   结果:');
          const resultStr = typeof tr.result === 'string' ? tr.result : JSON.stringify(tr.result, null, 2);
          details.push(resultStr);
        }
      });
    }
  }

  if (span.name === 'thought') {
    const content = attrs.content || '';
    if (content) {
      details.push('思考内容:');
      details.push(content);
    }
  }

  if (span.name === 'task_progress') {
    details.push(`阶段: ${attrs.stage || '-'}`);
    details.push(`状态: ${attrs.status || '-'}`);
    if (attrs.tool_name) {
      details.push(`工具: ${attrs.tool_name}`);
    }
  }

  if (span.name === 'assistant_response') {
    const content = attrs.content || '';
    if (content) {
      details.push('AI完整响应:');
      details.push(content);
    }
  }

  if (span.name === 'reward') {
    const reward = attrs.reward || 0;
    const rewardVersion = attrs.reward_version || 'v1';
    const baseReward = attrs.base_reward || 0;
    const resultAccuracy = attrs.result_accuracy || 0;
    const timeEfficiency = attrs.time_efficiency || 0;
    const memoryUtilization = attrs.memory_utilization || 0;
    const failurePenalty = attrs.failure_penalty || 0;

    details.push(`最终奖励: ${reward.toFixed(4)}`);
    details.push(`版本: ${rewardVersion}`);
    details.push('');

    if (rewardVersion === 'v2') {
      // 显示基础奖励的计算过程
      const taskCompletion = attrs.task_completion || 0;
      const toolEfficiency = attrs.tool_efficiency || 0;
      const pipelineQuality = attrs.pipeline_quality || 0;
      const taskMode = attrs.task_mode || 'unit';
      const runSimCalls = attrs.run_simulation_calls || 0;
      const runSimSuccess = attrs.run_simulation_success || 0;
      const getResultSuccess = attrs.get_result_success || 0;
      const runFailConfig = attrs.run_simulation_fail_config || 0;
      const runFailRuntime = attrs.run_simulation_fail_runtime || 0;
      const runFailUnknown = attrs.run_simulation_fail_unknown || 0;

      details.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
      details.push('【基础奖励计算】(v1 算法)');
      details.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
      details.push('');
      details.push(`任务模式: ${taskMode === 'unit' ? '单元任务' : '流程任务'}`);
      details.push('');

      if (taskMode === 'unit') {
        details.push('单元任务公式:');
        details.push('  基础奖励 = 任务完成度 × 0.55 + 工具效率 × 0.20 + 恢复能力 × 0.15 + 流程质量 × 0.10 - 失败惩罚');
        details.push('');
        details.push('各项得分:');
        details.push(`  • 任务完成度: ${taskCompletion.toFixed(4)}`);
        if (runSimSuccess >= 1 && getResultSuccess >= 1) {
          details.push(`    (成功运行模拟且获取结果 = 1.0)`);
        } else if (runSimSuccess >= 1) {
          details.push(`    (仅成功运行模拟 = 0.7)`);
        } else {
          details.push(`    (未完成或部分完成)`);
        }
        details.push(`  • 工具效率: ${toolEfficiency.toFixed(4)}`);
        const retryCount = Math.max(0, runSimCalls - 1);
        details.push(`    (重试次数: ${retryCount}, 效率 = exp(-0.35 × ${retryCount}))`);
        details.push(`  • 流程质量: ${pipelineQuality.toFixed(4)}`);
        details.push(`    (get_schema调用 + get_result成功)`);
        const penalty = runFailConfig * 0.10 + runFailRuntime * 0.05 + runFailUnknown * 0.03;
        details.push(`  • 失败惩罚: ${penalty.toFixed(4)}`);
        details.push(`    (配置错误 ${runFailConfig} × 0.10 + 运行时错误 ${runFailRuntime} × 0.05 + 未知错误 ${runFailUnknown} × 0.03)`);
      } else {
        details.push('流程任务公式:');
        details.push('  基础奖励 = 任务完成度 × 0.45 + 进度 × 0.20 + 工具效率 × 0.20 + 恢复能力 × 0.10 + 流程质量 × 0.05 - 失败惩罚');
        details.push('');
        details.push('各项得分:');
        details.push(`  • 任务完成度: ${taskCompletion.toFixed(4)}`);
        details.push(`  • 工具效率: ${toolEfficiency.toFixed(4)}`);
        details.push(`  • 流程质量: ${pipelineQuality.toFixed(4)}`);
      }
      details.push('');
      details.push(`基础奖励 = ${baseReward.toFixed(4)}`);
      details.push('');

      details.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
      details.push('【最终奖励计算】(v2 算法)');
      details.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
      details.push('');
      details.push('计算公式:');
      details.push('  最终奖励 = 基础奖励 × 0.70 + 结果准确度 × 0.15 + 时间效率 × 0.10 + 记忆利用 × 0.05 - 失败惩罚');
      details.push('');
      details.push('各项得分:');
      details.push(`  • 基础奖励: ${baseReward.toFixed(4)} (权重 0.70)`);
      details.push(`  • 结果准确度: ${resultAccuracy.toFixed(4)} (权重 0.15)`);
      details.push(`  • 时间效率: ${timeEfficiency.toFixed(4)} (权重 0.10)`);
      const timeAlpha = taskMode === 'process' ? 0.012 : 0.018;
      const elapsedSec = attrs.elapsed_seconds || 0;
      details.push(`    (exp(-${timeAlpha} × ${elapsedSec.toFixed(2)}秒))`);
      details.push(`  • 记忆利用: ${memoryUtilization.toFixed(4)} (权重 0.05)`);
      details.push(`  • 失败惩罚: ${failurePenalty.toFixed(4)}`);
      details.push('');
      details.push('计算过程:');
      const calc = baseReward * 0.70 + resultAccuracy * 0.15 + timeEfficiency * 0.10 + memoryUtilization * 0.05 - failurePenalty;
      details.push(`  = ${baseReward.toFixed(4)} × 0.70 + ${resultAccuracy.toFixed(4)} × 0.15 + ${timeEfficiency.toFixed(4)} × 0.10 + ${memoryUtilization.toFixed(4)} × 0.05 - ${failurePenalty.toFixed(4)}`);
      details.push(`  = ${(baseReward * 0.70).toFixed(4)} + ${(resultAccuracy * 0.15).toFixed(4)} + ${(timeEfficiency * 0.10).toFixed(4)} + ${(memoryUtilization * 0.05).toFixed(4)} - ${failurePenalty.toFixed(4)}`);
      details.push(`  = ${calc.toFixed(4)}`);
      details.push(`  = ${Math.max(0, Math.min(1, calc)).toFixed(4)} (限制在 [0, 1])`);
    } else {
      const taskCompletion = attrs.task_completion || 0;
      const toolEfficiency = attrs.tool_efficiency || 0;
      const pipelineQuality = attrs.pipeline_quality || 0;
      const taskMode = attrs.task_mode || 'unit';

      details.push('计算公式 (v1):');
      if (taskMode === 'unit') {
        details.push(`  奖励 = 任务完成度 × 0.55 + 工具效率 × 0.20 + 流程质量 × 0.10 - 失败惩罚`);
      } else {
        details.push(`  奖励 = 任务完成度 × 0.45 + 进度 × 0.20 + 工具效率 × 0.20 + 流程质量 × 0.05 - 失败惩罚`);
      }
      details.push('');
      details.push('各项得分:');
      details.push(`  任务完成度: ${taskCompletion.toFixed(4)}`);
      details.push(`  工具效率: ${toolEfficiency.toFixed(4)}`);
      details.push(`  流程质量: ${pipelineQuality.toFixed(4)}`);
    }

    details.push('');
    details.push('其他指标:');
    if (attrs.elapsed_seconds) {
      details.push(`  执行时长: ${attrs.elapsed_seconds.toFixed(2)}秒`);
    }
    if (attrs.run_simulation_calls) {
      details.push(`  模拟调用次数: ${attrs.run_simulation_calls}`);
      details.push(`  模拟成功次数: ${attrs.run_simulation_success || 0}`);
    }
    if (attrs.memory_hit_count) {
      details.push(`  记忆命中数: ${attrs.memory_hit_count}`);
    }
    if (attrs.dominant_failure_category) {
      details.push(`  主要失败类型: ${attrs.dominant_failure_category}`);
    }

    if (attrs.validator_scores) {
      details.push('');
      details.push('验证器评分:');
      details.push(JSON.stringify(attrs.validator_scores, null, 2));
    }
  }

  if (span.name === 'llm_call') {
    if (attrs.prompt) {
      details.push('LLM提示词:');
      details.push(attrs.prompt);
    }
    if (attrs.response) {
      details.push('\nLLM响应:');
      details.push(attrs.response);
    }
  }

  return details.length > 0 ? details.join('\n') : null;
}

/* ---- Artifacts helpers ---- */
function fileTypeLabel(type) {
  const labels = {
    aspen: "Aspen文件", config: "配置文件", result: "结果文件",
    image: "图片", video: "视频", audio: "音频", document: "文档",
    code: "代码", data: "数据", archive: "压缩包", text: "文本",
    binary: "二进制", other: "其他",
  };
  return labels[type] || type || "文件";
}

function toggleArtifactCollapse(rolloutId) {
  if (collapsedArtifacts.value.has(rolloutId)) {
    collapsedArtifacts.value.delete(rolloutId);
  } else {
    collapsedArtifacts.value.add(rolloutId);
  }
  collapsedArtifacts.value = new Set(collapsedArtifacts.value);
}

async function loadArtifacts(statusFilterVal) {
  try {
    artifactsLoading.value = true;
    const url = statusFilterVal
      ? `/api/artifacts?status=${encodeURIComponent(statusFilterVal)}`
      : "/api/artifacts";
    const data = await fetchJson(url);
    artifactsList.value = Array.isArray(data) ? data : (data.items || []);
  } catch (err) {
    console.warn("加载产物数据失败:", err);
    artifactsList.value = [];
  } finally {
    artifactsLoading.value = false;
  }
}

async function downloadArtifact(rolloutId, file) {
  try {
    const filePath = file.path || file.name;
    if (!filePath) { error.value = "文件路径不存在"; return; }
    const dlHeaders = {}; const dlToken = getToken(); if (dlToken) dlHeaders["Authorization"] = `Bearer ${dlToken}`; const response = await fetch(`/download?file_path=${encodeURIComponent(filePath)}`, { headers: dlHeaders });
    if (!response.ok) throw new Error(`下载失败: ${response.statusText}`);
    const blob = await response.blob();
    const cd = response.headers.get("Content-Disposition");
    let filename = null;
    if (cd) {
      const m = cd.match(/filename\*?=["']?(?:UTF-8'')?([^"';]+)["']?/i);
      if (m && m[1]) filename = decodeURIComponent(m[1]);
    }
    if (!filename) filename = file.name || file.path?.split(/[/\\]/).pop() || `artifact_${Date.now()}.bin`;
    const link = document.createElement("a");
    link.href = window.URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(link.href);
  } catch (err) {
    console.error("Download error:", err);
    error.value = `下载失败: ${err.message}`;
  }
}

/* ---- Lifecycle ---- */
onMounted(() => {
  refreshAll().then(() => {
    // Check if there's a rollout_id in query params
    const rolloutId = route.query.rollout_id;
    if (rolloutId && runs.value.length > 0) {
      const targetRun = runs.value.find(r => r.rollout_id === rolloutId);
      if (targetRun) {
        activeTab.value = 'tasks';
        viewRunDetail(targetRun);
      }
    }
  });
});

// Watch for query param changes
watch(() => route.query.rollout_id, (newRolloutId) => {
  if (newRolloutId && runs.value.length > 0) {
    const targetRun = runs.value.find(r => r.rollout_id === newRolloutId);
    if (targetRun) {
      activeTab.value = 'tasks';
      viewRunDetail(targetRun);
    }
  }
});

// Watch activeTab for files_all tab
watch(activeTab, (tab) => {
  if (tab === "files_all") {
    loadArtifacts("");
  }
});
</script>

<style scoped>
.runs-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>

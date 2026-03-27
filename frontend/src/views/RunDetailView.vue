<template>
  <SettingsLayout
    title="运行详情"
    :subtitle="`任务 ID: ${rolloutId}`"
    :active="activeTab"
    :groups="sidebarGroups"
    @select="activeTab = $event"
  >
    <!-- Error Display -->
    <div v-if="error" class="gh-panel mb-4" style="border-color: #d1242f;">
      <div class="gh-panel-body">
        <div style="color: #d1242f; font-size: 13px;">{{ error }}</div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="gh-empty">
      加载中...
    </div>

    <!-- 执行概览 -->
    <section v-show="activeTab === 'overview' && !loading">
      <h2 class="gh-heading">执行概览</h2>

      <!-- Stat Cards -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px;">
        <div class="gh-stat-card">
          <div class="gh-stat-label">执行事件总数</div>
          <div class="gh-stat-value">{{ totalSpans }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">思考事件</div>
          <div class="gh-stat-value">{{ thinkingSpans }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">工具调用</div>
          <div class="gh-stat-value">{{ toolCallSpans }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">阶段事件</div>
          <div class="gh-stat-value">{{ phaseSpans }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">奖励值</div>
          <div class="gh-stat-value" :style="{ color: rewardValue >= 0 ? '#1a7f37' : '#d1242f' }">
            {{ rewardValue.toFixed(2) }}
          </div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">主要失败类型</div>
          <div class="gh-stat-value" style="font-size: 14px;">{{ primaryFailureType || 'N/A' }}</div>
        </div>
      </div>

      <!-- Memory Search Items -->
      <div v-if="memorySearchItems.length > 0" style="margin-bottom: 24px;">
        <h3 style="font-size: 15px; font-weight: 600; color: #1f2328; margin-bottom: 12px;">Memory Search Items</h3>
        <div class="gh-panel">
          <div class="gh-panel-body" style="padding: 0;">
            <table class="gh-table">
              <thead>
                <tr>
                  <th>Query</th>
                  <th>Enriched Query</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in memorySearchItems" :key="idx">
                  <td style="font-family: ui-monospace, monospace; font-size: 12px;">{{ item.query }}</td>
                  <td style="font-family: ui-monospace, monospace; font-size: 12px; color: #0969da;">{{ item.enrichedQuery }}</td>
                  <td style="white-space: nowrap;">{{ fmtDateTime(item.timestamp) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Memory Fetch Items -->
      <div v-if="memoryFetchItems.length > 0">
        <h3 style="font-size: 15px; font-weight: 600; color: #1f2328; margin-bottom: 12px;">Memory Fetch Items</h3>
        <div class="gh-panel">
          <div class="gh-panel-body" style="padding: 0;">
            <table class="gh-table">
              <thead>
                <tr>
                  <th>Memory ID</th>
                  <th>Preview</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, idx) in memoryFetchItems" :key="idx">
                  <td style="font-family: ui-monospace, monospace; font-size: 12px;">{{ item.memoryId }}</td>
                  <td>
                    <div style="max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: #656d76;">
                      {{ item.preview }}
                    </div>
                  </td>
                  <td style="white-space: nowrap;">{{ fmtDateTime(item.timestamp) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- 奖励分解 -->
    <section v-show="activeTab === 'rewards' && !loading">
      <h2 class="gh-heading">奖励分解</h2>

      <!-- Reward Breakdown Grid -->
      <div v-if="rewardItems.length > 0" style="margin-bottom: 24px;">
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px;">
          <div v-for="(item, idx) in rewardItems" :key="idx" class="gh-stat-card">
            <div class="gh-stat-label">{{ item.name }}</div>
            <div class="gh-stat-value" :style="{ color: item.value >= 0 ? '#1a7f37' : '#d1242f' }">
              {{ item.value.toFixed(2) }}
            </div>
          </div>
        </div>
      </div>
      <div v-else class="gh-empty">
        暂无奖励数据
      </div>

      <!-- Validator Profile -->
      <div v-if="validatorProfile" style="margin-bottom: 24px;">
        <h3 style="font-size: 15px; font-weight: 600; color: #1f2328; margin-bottom: 12px;">Validator Profile</h3>
        <div class="gh-panel">
          <div class="gh-panel-body">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
              <div v-for="(value, key) in validatorProfile" :key="key">
                <div style="font-size: 12px; color: #656d76; margin-bottom: 4px;">{{ key }}</div>
                <div style="font-size: 13px; color: #1f2328; font-weight: 500;">{{ value }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Validator Scores -->
      <div v-if="validatorScores && validatorScores.length > 0" style="margin-bottom: 24px;">
        <h3 style="font-size: 15px; font-weight: 600; color: #1f2328; margin-bottom: 12px;">Validator Scores</h3>
        <div class="gh-panel">
          <div class="gh-panel-body" style="padding: 0;">
            <table class="gh-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Score</th>
                  <th>Weight</th>
                  <th>Weighted Score</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(score, idx) in validatorScores" :key="idx">
                  <td>{{ score.metric }}</td>
                  <td>{{ score.score.toFixed(2) }}</td>
                  <td>{{ score.weight.toFixed(2) }}</td>
                  <td :style="{ color: score.weightedScore >= 0 ? '#1a7f37' : '#d1242f' }">
                    {{ score.weightedScore.toFixed(2) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Failure Categories -->
      <div v-if="failureCategories && failureCategories.length > 0">
        <h3 style="font-size: 15px; font-weight: 600; color: #1f2328; margin-bottom: 12px;">Failure Categories</h3>
        <div class="gh-panel">
          <div class="gh-panel-body" style="padding: 0;">
            <table class="gh-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Count</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(cat, idx) in failureCategories" :key="idx">
                  <td>
                    <span class="gh-label gh-label-danger">{{ cat.category }}</span>
                  </td>
                  <td>{{ cat.count }}</td>
                  <td style="font-size: 12px; color: #656d76;">{{ cat.description }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- 阶段时间线 -->
    <section v-show="activeTab === 'progress' && !loading">
      <h2 class="gh-heading">阶段时间线</h2>

      <div v-if="progressSpans.length > 0" class="gh-panel">
        <div class="gh-panel-body" style="padding: 0;">
          <table class="gh-table">
            <thead>
              <tr>
                <th>Phase</th>
                <th>Status</th>
                <th>Start Time</th>
                <th>Duration</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(span, idx) in progressSpans" :key="idx">
                <td>
                  <span class="gh-label gh-label-info">{{ span.name }}</span>
                </td>
                <td>
                  <span class="gh-label" :class="{
                    'gh-label-success': span.status === 'completed',
                    'gh-label-warning': span.status === 'in_progress',
                    'gh-label-danger': span.status === 'failed',
                    'gh-label-muted': span.status === 'pending'
                  }">
                    {{ span.status }}
                  </span>
                </td>
                <td style="white-space: nowrap;">{{ fmtDateTime(span.startTime) }}</td>
                <td style="white-space: nowrap;">{{ fmtDurationSec(span.duration) }}</td>
                <td style="font-size: 12px; color: #656d76;">{{ span.details || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div v-else class="gh-empty">
        暂无阶段数据
      </div>
    </section>

    <!-- 原始 Span -->
    <section v-show="activeTab === 'raw-spans' && !loading">
      <h2 class="gh-heading">原始 Span</h2>

      <div v-if="runData && runData.spans && runData.spans.length > 0" class="gh-panel">
        <div class="gh-panel-body" style="padding: 0;">
          <table class="gh-table">
            <thead>
              <tr>
                <th>Span ID</th>
                <th>Name</th>
                <th>Type</th>
                <th>Start Time</th>
                <th>Duration</th>
                <th>Attributes</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(span, idx) in runData.spans" :key="idx">
                <td style="font-family: ui-monospace, monospace; font-size: 11px; color: #656d76;">
                  {{ span.spanId || span.id }}
                </td>
                <td>
                  <span class="gh-label gh-label-purple">{{ span.name }}</span>
                </td>
                <td>
                  <span class="gh-label gh-label-muted">{{ span.type || 'unknown' }}</span>
                </td>
                <td style="white-space: nowrap;">{{ fmtDateTime(span.startTime) }}</td>
                <td style="white-space: nowrap;">{{ fmtDurationSec(span.duration) }}</td>
                <td>
                  <div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; color: #656d76;">
                    {{ formatAttributes(span.attributes) }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div v-else class="gh-empty">
        暂无 Span 数据
      </div>
    </section>
  </SettingsLayout>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { fetchJson, fmtDateTime } from "../services/api";
import SettingsLayout from "../components/SettingsLayout.vue";
import "../assets/github-theme.css";

function fmtDurationSec(sec) {
  if (sec == null || sec === undefined) return "-";
  if (sec < 60) return sec.toFixed(1) + "s";
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(0);
  return `${m}m ${s}s`;
}

const route = useRoute();
const rolloutId = computed(() => route.params.id || route.query.id || 'unknown');

const activeTab = ref('overview');
const loading = ref(true);
const error = ref(null);
const runData = ref(null);

const sidebarGroups = computed(() => [
  {
    label: "",
    items: [
      { id: "overview", label: "执行概览" },
      { id: "rewards", label: "奖励分解" },
      { id: "progress", label: "阶段时间线" },
      { id: "raw-spans", label: "原始 Span" }
    ]
  }
]);

// Computed: Reward Span
const rewardSpan = computed(() => {
  if (!runData.value || !runData.value.spans) return null;
  return runData.value.spans.find(s => s.type === 'reward' || s.name === 'reward');
});

// Computed: Reward Value
const rewardValue = computed(() => {
  if (!rewardSpan.value) return 0;
  if (rewardSpan.value.attributes && typeof rewardSpan.value.attributes.value === 'number') {
    return rewardSpan.value.attributes.value;
  }
  if (rewardSpan.value.reward !== undefined) return rewardSpan.value.reward;
  return 0;
});

// Computed: Total Spans
const totalSpans = computed(() => {
  if (!runData.value || !runData.value.spans) return 0;
  return runData.value.spans.length;
});

// Computed: Thinking Spans
const thinkingSpans = computed(() => {
  if (!runData.value || !runData.value.spans) return 0;
  return runData.value.spans.filter(s => s.type === 'thinking' || s.name.includes('think')).length;
});

// Computed: Tool Call Spans
const toolCallSpans = computed(() => {
  if (!runData.value || !runData.value.spans) return 0;
  return runData.value.spans.filter(s => s.type === 'tool_call' || s.name.includes('tool')).length;
});

// Computed: Phase Spans
const phaseSpans = computed(() => {
  if (!runData.value || !runData.value.spans) return 0;
  return runData.value.spans.filter(s => s.type === 'phase' || s.name.includes('phase')).length;
});

// Computed: Primary Failure Type
const primaryFailureType = computed(() => {
  if (!runData.value || !runData.value.failureCategories || runData.value.failureCategories.length === 0) {
    return null;
  }
  const sorted = [...runData.value.failureCategories].sort((a, b) => b.count - a.count);
  return sorted[0].category;
});

// Computed: Progress Spans (task_progress spans)
const progressSpans = computed(() => {
  if (!runData.value || !runData.value.spans) return [];
  return runData.value.spans
    .filter(s => s.type === 'task_progress' || s.name.includes('progress'))
    .map(s => ({
      name: s.name,
      status: s.attributes?.status || s.status || 'unknown',
      startTime: s.startTime || s.timestamp,
      duration: s.duration || 0,
      details: s.attributes?.details || s.details || ''
    }));
});

// Computed: Memory Search Items
const memorySearchItems = computed(() => {
  if (!runData.value || !runData.value.spans) return [];
  return runData.value.spans
    .filter(s => s.type === 'memory_search' || s.name === 'memory_search')
    .map(s => ({
      query: s.attributes?.query || s.query || '',
      enrichedQuery: s.attributes?.enriched_query || s.enrichedQuery || '',
      timestamp: s.startTime || s.timestamp
    }));
});

// Computed: Memory Fetch Items
const memoryFetchItems = computed(() => {
  if (!runData.value || !runData.value.spans) return [];
  return runData.value.spans
    .filter(s => s.type === 'memory_fetch' || s.name === 'memory_fetch')
    .map(s => ({
      memoryId: s.attributes?.memory_id || s.memoryId || '',
      preview: s.attributes?.preview || s.preview || s.attributes?.content?.substring(0, 100) || '',
      timestamp: s.startTime || s.timestamp
    }));
});

// Computed: Reward Items (reward breakdown)
const rewardItems = computed(() => {
  if (!runData.value || !runData.value.rewardBreakdown) return [];
  return runData.value.rewardBreakdown.map(item => ({
    name: item.name || item.metric,
    value: item.value || item.score || 0
  }));
});

// Computed: Validator Profile
const validatorProfile = computed(() => {
  if (!runData.value || !runData.value.validatorProfile) return null;
  return runData.value.validatorProfile;
});

// Computed: Validator Scores
const validatorScores = computed(() => {
  if (!runData.value || !runData.value.validatorScores) return [];
  return runData.value.validatorScores.map(score => ({
    metric: score.metric || score.name,
    score: score.score || 0,
    weight: score.weight || 1,
    weightedScore: (score.score || 0) * (score.weight || 1)
  }));
});

// Computed: Failure Categories
const failureCategories = computed(() => {
  if (!runData.value || !runData.value.failureCategories) return [];
  return runData.value.failureCategories;
});

// Helper: Format Attributes
function formatAttributes(attrs) {
  if (!attrs) return '';
  if (typeof attrs === 'string') return attrs;
  return JSON.stringify(attrs);
}

// Load Run Data
async function loadRunData() {
  try {
    loading.value = true;
    error.value = null;
    const data = await fetchJson(`/api/rollouts/${encodeURIComponent(rolloutId.value)}/spans`);
    runData.value = data;
  } catch (err) {
    error.value = err.message || "加载运行数据失败";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadRunData();
});
</script>

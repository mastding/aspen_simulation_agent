<template>
  <SettingsLayout
    title="历史经验"
    :active="activeTab"
    :groups="sidebarGroups"
    :fluid="true"
    @select="activeTab = $event"
  >
    <!-- Error Display -->
    <div v-if="error" class="gh-panel mb-4" style="border-color: #d1242f;">
      <div class="gh-panel-body">
        <div style="color: #d1242f; font-size: 13px;">{{ error }}</div>
      </div>
    </div>

    <!-- 质量概览 -->
    <section v-show="activeTab === 'quality'">
      <h2 class="gh-heading">质量概览</h2>

      <!-- Quality Stat Cards -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px;">
        <div class="gh-stat-card">
          <div class="gh-stat-label">命中任务数</div>
          <div class="gh-stat-value">{{ qualityStats.memory_hit_rollouts || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">命中后成功率</div>
          <div class="gh-stat-value" style="color: #1a7f37;">{{ (qualityStats.memory_hit_success_rate || 0).toFixed(1) }}%</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">命中平均步数</div>
          <div class="gh-stat-value">{{ (qualityStats.memory_hit_avg_steps || 0).toFixed(1) }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">未命中平均步数</div>
          <div class="gh-stat-value">{{ (qualityStats.memory_non_hit_avg_steps || 0).toFixed(1) }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">平均步数下降</div>
          <div class="gh-stat-value" style="color: #1a7f37;">{{ (qualityStats.memory_avg_step_reduction || 0).toFixed(1) }}</div>
        </div>
      </div>

      <!-- Usage Stats -->
      <div class="gh-panel">
        <div class="gh-panel-header">
          <div class="gh-panel-header-title">使用统计</div>
        </div>
        <div class="gh-panel-body">
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
            <div>
              <div style="font-size: 12px; color: #656d76; margin-bottom: 4px;">检索次数</div>
              <div style="font-size: 18px; font-weight: 600; color: #1f2328;">{{ usageStats.memory_usage_stats_retrieved_total || 0 }}</div>
            </div>
            <div>
              <div style="font-size: 12px; color: #656d76; margin-bottom: 4px;">应用次数</div>
              <div style="font-size: 18px; font-weight: 600; color: #1f2328;">{{ usageStats.memory_usage_stats_applied_total || 0 }}</div>
            </div>
            <div>
              <div style="font-size: 12px; color: #656d76; margin-bottom: 4px;">使用后平均奖励</div>
              <div style="font-size: 18px; font-weight: 600; color: #1a7f37;">{{ (usageStats.memory_usage_stats_avg_reward_after_use || 0).toFixed(2) }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 经验清单 -->
    <section v-show="activeTab === 'experience'">
      <h2 class="gh-heading">经验清单</h2>

      <!-- Action buttons -->
      <div style="display: flex; gap: 8px; margin-bottom: 16px;">
        <button class="gh-btn gh-btn-danger" @click="clearAllMemories">清空历史经验</button>
      </div>

      <!-- Filter Bar -->
      <div class="gh-panel" style="margin-bottom: 16px;">
        <div class="gh-panel-body">
          <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <input
              v-model="queryText"
              type="text"
              placeholder="搜索任务描述关键词..."
              class="gh-input"
              style="flex: 1; min-width: 200px;"
              @input="loadExperiences"
            />
            <select v-model="taskType" class="gh-select" @change="loadExperiences">
              <option value="">所有任务类型</option>
              <option value="unit">单元模拟</option>
              <option value="process">流程模拟</option>
            </select>
            <button class="gh-btn" @click="loadExperiences">
              <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.5 4.5 0 1 0-8.997.002A4.5 4.5 0 0 0 11.5 7Z"></path>
              </svg>
              搜索
            </button>
          </div>
        </div>
      </div>

      <!-- Experience Table -->
      <div class="gh-panel">
        <div class="gh-panel-body" style="padding: 0; overflow-x: auto;">
          <table ref="memoryTableRef" class="gh-table resizable-table">
            <thead>
              <tr>
                <th>Memory ID</th>
                <th>任务ID</th>
                <th>任务描述</th>
                <th>调用</th>
                <th>成功率</th>
                <th>更新时间</th>
                <th>最近调用</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!experiences || experiences.length === 0">
                <td colspan="8" class="gh-empty">暂无经验数据</td>
              </tr>
              <tr
                v-for="exp in experiences"
                :key="exp.memory_id"
                @click="selectExperience(exp)"
                style="cursor: pointer;"
                :style="selectedExperience?.memory_id === exp.memory_id ? 'background: #f6f8fa;' : ''"
              >
                <td><code style="font-size: 11px; color: #0969da;">{{ exp.memory_id.substring(0, 8) }}</code></td>
                <td>
                  <router-link
                    v-if="exp.source_rollout_id"
                    :to="{ path: '/runs', query: { rollout_id: exp.source_rollout_id } }"
                    class="gh-link"
                    style="font-size: 11px;"
                    @click.stop
                  >
                    {{ exp.source_rollout_id.substring(0, 8) }}
                  </router-link>
                  <span v-else style="color: #656d76; font-size: 11px;">-</span>
                </td>
                <td style="font-size: 12px; color: #1f2328; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="exp.task_text">
                  {{ exp.task_text || '-' }}
                </td>
                <td>{{ exp.use_count || 0 }}</td>
                <td>
                  <span class="gh-label" :class="exp.hit_success_rate >= 0.8 ? 'gh-label-success' : exp.hit_success_rate >= 0.5 ? 'gh-label-warning' : 'gh-label-danger'">
                    {{ ((exp.hit_success_rate || 0) * 100).toFixed(0) }}%
                  </span>
                </td>
                <td style="font-size: 12px; color: #656d76;">{{ fmtDateTime(exp.updated_at) }}</td>
                <td style="font-size: 12px; color: #656d76;">{{ fmtDateTime(exp.last_used_at) }}</td>
                <td>
                  <div style="display: flex; gap: 4px;">
                    <button class="gh-btn" style="font-size: 11px; padding: 2px 8px;" @click.stop="selectExperience(exp)">
                      详情
                    </button>
                    <button class="gh-btn gh-btn-danger" style="font-size: 11px; padding: 2px 8px;" @click.stop="deleteMemory(exp)">
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

    <!-- 经验详情 -->
    <section v-show="activeTab === 'detail'">
      <h2 class="gh-heading">经验详情</h2>
      <div class="gh-panel">
        <div class="gh-panel-body">
          <div v-if="!selectedExperience" class="gh-empty">
            请先在「经验清单」中选择一条经验
          </div>
          <div v-else>
            <!-- 基本信息 -->
            <div style="margin-bottom: 20px;">
              <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 8px;">基本信息</div>
              <div style="font-size: 12px; color: #656d76; line-height: 1.6;">
                <div><strong>Memory ID:</strong> {{ selectedExperience.memory_id }}</div>
                <div v-if="selectedExperience.source_rollout_id">
                  <strong>来源任务:</strong>
                  <router-link
                    :to="{ path: '/runs', query: { rollout_id: selectedExperience.source_rollout_id } }"
                    class="gh-link"
                    style="margin-left: 4px;"
                  >
                    {{ selectedExperience.source_rollout_id }}
                  </router-link>
                </div>
                <div><strong>任务类型:</strong> {{ selectedExperience.task_type || '-' }}</div>
                <div><strong>使用次数:</strong> {{ selectedExperience.use_count || 0 }}</div>
                <div><strong>成功次数:</strong> {{ selectedExperience.hit_success_count || 0 }}</div>
                <div><strong>成功率:</strong> {{ ((selectedExperience.hit_success_rate || 0) * 100).toFixed(1) }}%</div>
                <div><strong>平均匹配分:</strong> {{ (selectedExperience.avg_match_score || 0).toFixed(2) }}</div>
              </div>
            </div>

            <!-- 任务描述 -->
            <div v-if="selectedExperience.task_text" style="margin-bottom: 20px;">
              <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 8px;">任务描述</div>
              <div class="gh-code" style="max-height: 150px; overflow-y: auto;">{{ selectedExperience.task_text }}</div>
            </div>

            <!-- 配置信息 -->
            <div v-if="selectedExperience.config_snippet" style="margin-bottom: 20px;">
              <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 8px;">关键配置</div>
              <div class="gh-code" style="max-height: 200px; overflow-y: auto;">{{ selectedExperience.config_snippet }}</div>
            </div>

            <!-- 策略文本 -->
            <div v-if="selectedExperience.strategy_text" style="margin-bottom: 20px;">
              <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 8px;">执行策略</div>
              <div class="gh-code" style="max-height: 200px; overflow-y: auto;">{{ selectedExperience.strategy_text }}</div>
            </div>

            <!-- 避坑经验 -->
            <div v-if="selectedExperience.pitfalls_text" style="margin-bottom: 20px;">
              <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 8px;">避坑经验</div>
              <div class="gh-code">{{ selectedExperience.pitfalls_text }}</div>
            </div>

            <!-- 经验教训 -->
            <div v-if="selectedExperience.lesson">
              <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 8px;">经验教训</div>
              <div class="gh-code">{{ selectedExperience.lesson }}</div>
            </div>

            <!-- 返回清单 -->
            <div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid #d0d7de;">
              <button class="gh-btn" @click="activeTab = 'experience'">← 返回经验清单</button>
            </div>
          </div>
        </div>
      </div>
    </section>

  </SettingsLayout>
</template>

<script setup>
import { onMounted, ref } from "vue";
import SettingsLayout from "../components/SettingsLayout.vue";
import { fetchJson, postJson, deleteJson, fmtDateTime } from "../services/api";
import { useColumnResize } from "../composables/useColumnResize";
import "../assets/github-theme.css";

const activeTab = ref("quality");
const error = ref(null);
const memoryTableRef = ref(null);
useColumnResize(memoryTableRef);

// Quality Stats
const qualityStats = ref({
  memory_hit_rollouts: 0,
  memory_hit_success_rate: 0,
  memory_hit_avg_steps: 0,
  memory_non_hit_avg_steps: 0,
  memory_avg_step_reduction: 0
});

const usageStats = ref({
  memory_usage_stats_retrieved_total: 0,
  memory_usage_stats_applied_total: 0,
  memory_usage_stats_avg_reward_after_use: 0
});

// Experience List
const queryText = ref("");
const taskType = ref("");
const experiences = ref([]);
const selectedExperience = ref(null);

const _i = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;
const sidebarGroups = [
  {
    label: "",
    items: [
      { id: "quality", label: "质量概览", icon: _i("M12 20V10M18 20V4M6 20v-4") },
      { id: "experience", label: "经验清单", icon: _i("M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 3H20v18H6.5A2.5 2.5 0 0 1 4 18.5V5.5A2.5 2.5 0 0 1 6.5 3Z") },
      { id: "detail", label: "经验详情", icon: _i("M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2zM22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z") },
    ]
  }
];

async function loadQualityStats() {
  try {
    error.value = null;
    const data = await fetchJson("/api/memory/quality");
    qualityStats.value = data;
    usageStats.value = data;
  } catch (err) {
    error.value = err.message || "加载质量统计失败";
  }
}

async function loadExperiences() {
  try {
    error.value = null;
    const params = new URLSearchParams();
    if (queryText.value) params.append("query", queryText.value);
    if (taskType.value) params.append("type", taskType.value);

    const data = await fetchJson(`/api/memory/usages?${params.toString()}`);
    experiences.value = data.items || [];
  } catch (err) {
    error.value = err.message || "加载经验清单失败";
  }
}

async function clearAllMemories() {
  if (!confirm("确定要清空所有历史经验吗？此操作不可撤销。")) return;
  try {
    error.value = null;
    await postJson("/api/memory/clear", {});
    experiences.value = [];
    selectedExperience.value = null;
    await loadQualityStats();
  } catch (err) {
    error.value = err.message || "清空历史经验失败";
  }
}

async function deleteMemory(exp) {
  if (!confirm(`确定要删除经验 ${exp.memory_id.substring(0, 8)} 吗？`)) return;
  try {
    error.value = null;
    const resp = await deleteJson(`/api/memory/${exp.memory_id}`);
    if (resp.deleted) {
      experiences.value = experiences.value.filter(e => e.memory_id !== exp.memory_id);
      if (selectedExperience.value?.memory_id === exp.memory_id) {
        selectedExperience.value = null;
      }
    } else {
      error.value = resp.message || "删除失败";
    }
  } catch (err) {
    error.value = err.message || "删除经验失败";
  }
}

function selectExperience(exp) {
  selectedExperience.value = exp;
  activeTab.value = 'detail';
}

onMounted(() => {
  loadQualityStats();
  loadExperiences();
});
</script>

<style scoped>
.gh-link {
  color: #0969da;
  text-decoration: none;
  font-family: ui-monospace, monospace;
}

.gh-link:hover {
  text-decoration: underline;
}
</style>

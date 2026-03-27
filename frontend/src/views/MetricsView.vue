<template>
  <SettingsLayout
    title="运行指标看板"
    subtitle="用于运营分析与问题定位。"
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

    <!-- 指标概览 -->
    <section v-show="activeTab === 'overview'">
      <h2 class="gh-heading">指标概览</h2>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;">
        <div class="gh-stat-card">
          <div class="gh-stat-label">总任务</div>
          <div class="gh-stat-value">{{ metrics.total_rollouts || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">成功</div>
          <div class="gh-stat-value" style="color: #1a7f37;">{{ metrics.succeeded || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">失败</div>
          <div class="gh-stat-value" style="color: #d1242f;">{{ metrics.failed || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">平均奖励</div>
          <div class="gh-stat-value">{{ metrics.average_reward?.toFixed(2) || '0.00' }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">总工具调用</div>
          <div class="gh-stat-value">{{ metrics.total_tool_calls || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">每任务工具调用</div>
          <div class="gh-stat-value">{{ metrics.average_tool_calls_per_rollout?.toFixed(2) || '0.00' }}</div>
        </div>
      </div>
    </section>

    <!-- 每日趋势 -->
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

    <!-- 高频错误 -->
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
  </SettingsLayout>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import SettingsLayout from "../components/SettingsLayout.vue";
import { fetchJson } from "../services/api";
import "../assets/github-theme.css";

const activeTab = ref("overview");
const error = ref(null);
const metrics = ref({
  total_rollouts: 0,
  succeeded: 0,
  failed: 0,
  average_reward: 0,
  total_tool_calls: 0,
  average_tool_calls_per_rollout: 0,
  daily_trend: [],
  top_errors: []
});

const sidebarGroups = [
  {
    label: "",
    items: [
      { id: "overview", label: "指标概览" },
      { id: "daily", label: "每日趋势" },
      { id: "errors", label: "高频错误" }
    ]
  }
];

async function loadMetrics() {
  try {
    error.value = null;
    metrics.value = await fetchJson("/api/metrics/overview");
  } catch (err) {
    error.value = err.message || "加载指标数据失败";
  }
}

onMounted(() => {
  loadMetrics();
});
</script>

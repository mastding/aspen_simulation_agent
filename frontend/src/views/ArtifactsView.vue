<template>
  <SettingsLayout
    title="文件产物中心"
    subtitle="按任务聚合产物，支持定位与下载。"
    :active="activeTab"
    :groups="sidebarGroups"
    @select="handleTabSelect"
  >
    <!-- Error Display -->
    <div v-if="error" class="gh-panel mb-4" style="border-color: #d1242f;">
      <div class="gh-panel-body">
        <div style="color: #d1242f; font-size: 13px;">{{ error }}</div>
      </div>
    </div>

    <!-- 文件概览 -->
    <section v-show="activeTab === 'overview'">
      <h2 class="gh-heading">文件概览</h2>

      <!-- Statistics Cards -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px;">
        <div class="gh-stat-card">
          <div class="gh-stat-label">总任务数</div>
          <div class="gh-stat-value">{{ fileStats.total_tasks || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">总文件数</div>
          <div class="gh-stat-value">{{ fileStats.total_files || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">Aspen文件</div>
          <div class="gh-stat-value" style="color: #8250df;">{{ fileStats.aspen_files || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">配置文件</div>
          <div class="gh-stat-value" style="color: #0969da;">{{ fileStats.config_files || 0 }}</div>
        </div>
        <div class="gh-stat-card">
          <div class="gh-stat-label">结果文件</div>
          <div class="gh-stat-value" style="color: #1a7f37;">{{ fileStats.result_files || 0 }}</div>
        </div>
      </div>

      <!-- File Type Distribution -->
      <div class="gh-panel">
        <div class="gh-panel-header">
          <div class="gh-panel-header-title">文件类型分布</div>
        </div>
        <div class="gh-panel-body">
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
            <div v-for="(count, type) in fileStats.file_type_distribution" :key="type">
              <div style="font-size: 12px; color: #656d76; margin-bottom: 4px;">{{ typeLabel(type) }}</div>
              <div style="font-size: 18px; font-weight: 600; color: #1f2328;">{{ count }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Loading State -->
    <div v-if="loading && activeTab !== 'overview'" class="gh-panel">
      <div class="gh-panel-body">
        <div style="text-align: center; color: #656d76; font-size: 13px;">加载中...</div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!loading && artifacts.length === 0 && activeTab !== 'overview'" class="gh-panel">
      <div class="gh-empty">暂无产物数据</div>
    </div>

    <!-- Artifacts List -->
    <div v-if="activeTab !== 'overview'" class="space-y-4">
      <div v-for="artifact in artifacts" :key="artifact.rollout_id" class="gh-panel">
        <!-- Artifact Header (Collapsible) -->
        <div class="gh-panel-header">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="gh-panel-header-title">{{ artifact.rollout_id }}</span>
              <span
                class="gh-label"
                :class="{
                  'gh-label-success': artifact.status === 'succeeded',
                  'gh-label-danger': artifact.status === 'failed',
                  'gh-label-info': artifact.status === 'running',
                  'gh-label-muted': !['succeeded', 'failed', 'running'].includes(artifact.status)
                }"
              >
                {{ artifact.status }}
              </span>
            </div>
            <div v-if="artifact.message" class="gh-panel-header-sub">{{ artifact.message }}</div>
          </div>
          <button
            @click="toggleCollapse(artifact.rollout_id)"
            class="gh-btn"
            :aria-expanded="!collapsedItems.has(artifact.rollout_id)"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="currentColor"
              style="width: 16px; height: 16px; transition: transform 0.15s;"
              :style="{ transform: collapsedItems.has(artifact.rollout_id) ? 'rotate(-90deg)' : 'rotate(0deg)' }"
            >
              <path fill-rule="evenodd" d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>

        <!-- Artifact Body (Files Grid) -->
        <div v-show="!collapsedItems.has(artifact.rollout_id)" class="gh-panel-body">
          <div v-if="!artifact.files || artifact.files.length === 0" class="gh-empty" style="padding: 16px;">
            暂无文件
          </div>
          <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px;">
            <div
              v-for="(file, idx) in artifact.files"
              :key="idx"
              class="gh-panel"
              style="padding: 12px; display: flex; flex-direction: column; gap: 8px;"
            >
              <div style="display: flex; align-items: center; gap: 6px;">
                <span class="gh-label gh-label-purple" style="font-size: 11px;">{{ typeLabel(file.type) }}</span>
              </div>
              <div style="font-size: 12px; color: #1f2328; word-break: break-all; flex: 1;">
                {{ file.name || file.path || '未命名文件' }}
              </div>
              <button
                @click="downloadArtifact(artifact.rollout_id, file)"
                class="gh-btn gh-btn-primary"
                style="width: 100%; justify-content: center;"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" style="width: 14px; height: 14px;">
                  <path d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z" />
                  <path d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z" />
                </svg>
                下载
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </SettingsLayout>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import SettingsLayout from "../components/SettingsLayout.vue";
import { fetchJson } from "../services/api";
import "../assets/github-theme.css";

const activeTab = ref("overview");
const statusFilter = ref("");
const loading = ref(false);
const error = ref(null);
const artifacts = ref([]);
const collapsedItems = ref(new Set());
const fileStats = ref({
  total_tasks: 0,
  total_files: 0,
  aspen_files: 0,
  config_files: 0,
  result_files: 0,
  file_type_distribution: {}
});

const sidebarGroups = [
  {
    label: "",
    items: [
      { id: "overview", label: "文件概览" },
      { id: "all", label: "全部产物" },
      { id: "succeeded", label: "成功" },
      { id: "failed", label: "失败" },
      { id: "running", label: "运行中" }
    ]
  }
];

// Map tab to status filter value
const tabToStatus = {
  overview: "",
  all: "",
  succeeded: "succeeded",
  failed: "failed",
  running: "running"
};

function handleTabSelect(tabId) {
  activeTab.value = tabId;
  if (tabId === 'overview') {
    loadFileStats();
  } else {
    statusFilter.value = tabToStatus[tabId] || "";
    loadArtifacts();
  }
}

function toggleCollapse(rolloutId) {
  if (collapsedItems.value.has(rolloutId)) {
    collapsedItems.value.delete(rolloutId);
  } else {
    collapsedItems.value.add(rolloutId);
  }
  // Trigger reactivity
  collapsedItems.value = new Set(collapsedItems.value);
}

async function loadArtifacts() {
  try {
    loading.value = true;
    error.value = null;

    const url = statusFilter.value
      ? `/api/artifacts?status=${encodeURIComponent(statusFilter.value)}`
      : "/api/artifacts";

    const data = await fetchJson(url);
    artifacts.value = Array.isArray(data) ? data : (data.items || []);
  } catch (err) {
    error.value = err.message || "加载产物数据失败";
    artifacts.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadFileStats() {
  try {
    loading.value = true;
    error.value = null;

    const data = await fetchJson("/api/artifacts");
    const items = Array.isArray(data) ? data : (data.items || []);

    // Calculate statistics
    let totalFiles = 0;
    let aspenFiles = 0;
    let configFiles = 0;
    let resultFiles = 0;
    const typeDistribution = {};

    items.forEach(item => {
      if (item.files && Array.isArray(item.files)) {
        totalFiles += item.files.length;
        item.files.forEach(file => {
          const type = file.type || 'other';
          typeDistribution[type] = (typeDistribution[type] || 0) + 1;

          if (type === 'aspen') aspenFiles++;
          else if (type === 'config') configFiles++;
          else if (type === 'result') resultFiles++;
        });
      }
    });

    fileStats.value = {
      total_tasks: items.length,
      total_files: totalFiles,
      aspen_files: aspenFiles,
      config_files: configFiles,
      result_files: resultFiles,
      file_type_distribution: typeDistribution
    };
  } catch (err) {
    error.value = err.message || "加载文件统计失败";
  } finally {
    loading.value = false;
  }
}

function typeLabel(type) {
  const labels = {
    aspen: "Aspen文件",
    config: "配置文件",
    result: "结果文件",
    image: "图片",
    video: "视频",
    audio: "音频",
    document: "文档",
    code: "代码",
    data: "数据",
    archive: "压缩包",
    text: "文本",
    binary: "二进制",
    other: "其他"
  };
  return labels[type] || type || "文件";
}

function parseContentDispositionFileName(contentDisposition) {
  if (!contentDisposition) return null;

  // Try to extract filename from Content-Disposition header
  // Format: attachment; filename="example.txt" or filename*=UTF-8''example.txt
  const filenameMatch = contentDisposition.match(/filename\*?=["']?(?:UTF-8'')?([^"';]+)["']?/i);
  if (filenameMatch && filenameMatch[1]) {
    return decodeURIComponent(filenameMatch[1]);
  }

  return null;
}

function inferFileName(file, contentType) {
  // Try to infer filename from file object
  if (file.name) return file.name;
  if (file.path) {
    const parts = file.path.split(/[/\\]/);
    return parts[parts.length - 1];
  }

  // Fallback: generate filename based on content type
  const ext = contentType ? contentType.split('/')[1] : 'bin';
  return `artifact_${Date.now()}.${ext}`;
}

async function downloadArtifact(rolloutId, file) {
  try {
    // Use the /download endpoint with file_path query parameter
    const filePath = file.path || file.name;
    if (!filePath) {
      error.value = '文件路径不存在';
      return;
    }

    const url = `/download?file_path=${encodeURIComponent(filePath)}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`下载失败: ${response.statusText}`);
    }

    const blob = await response.blob();
    const contentDisposition = response.headers.get('Content-Disposition');
    const contentType = response.headers.get('Content-Type');

    // Determine filename
    let filename = parseContentDispositionFileName(contentDisposition);
    if (!filename) {
      filename = inferFileName(file, contentType);
    }

    // Create download link
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  } catch (err) {
    console.error('Download error:', err);
    error.value = `下载失败: ${err.message}`;
  }
}

onMounted(() => {
  loadFileStats();
});
</script>

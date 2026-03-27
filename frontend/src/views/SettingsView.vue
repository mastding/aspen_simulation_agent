<template>
  <SettingsLayout
    title="系统设置"
    :active="activeTab"
    :groups="sidebarGroups"
    @select="activeTab = $event"
  >
    <!-- 模型配置 -->
    <section v-show="activeTab === 'model'">
      <h2 class="gh-heading">模型配置</h2>

      <div class="gh-panel">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">LLM模型设置</span>
        </div>
        <div class="gh-panel-body" style="display: grid; gap: 16px;">
          <!-- 模型选择 -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">模型名称</span>
            <input
              v-model="modelConfig.model_name"
              type="text"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
              placeholder="例如：qwen3-max"
            />
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              使用的LLM模型名称
            </div>
          </label>

          <!-- API端点 -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">API端点</span>
            <input
              v-model="modelConfig.api_base"
              type="text"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
              placeholder="例如：https://api.example.com/v1"
            />
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              OpenAI兼容的API端点地址
            </div>
          </label>

          <!-- API Key -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">API Key</span>
            <div style="position: relative; margin-top: 4px;">
              <input
                v-model="modelConfig.api_key"
                :type="showApiKey ? 'text' : 'password'"
                class="gh-input"
                style="width: 100%; padding-right: 36px;"
                placeholder="sk-..."
              />
              <button
                type="button"
                @click="showApiKey = !showApiKey"
                style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 2px; color: #656d76;"
                :title="showApiKey ? '隐藏' : '显示'"
              >
                <svg v-if="!showApiKey" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              LLM服务的API密钥
            </div>
          </label>

          <!-- Temperature -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">Temperature</span>
            <input
              v-model.number="modelConfig.temperature"
              type="number"
              min="0"
              max="2"
              step="0.1"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
            />
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              控制输出随机性，范围0-2，当前值：{{ modelConfig.temperature }}
            </div>
          </label>

          <!-- Top P -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">Top P</span>
            <input
              v-model.number="modelConfig.top_p"
              type="number"
              min="0"
              max="1"
              step="0.05"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
            />
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              核采样参数，范围0-1，当前值：{{ modelConfig.top_p }}
            </div>
          </label>

          <!-- Max Tokens -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">最大Token数</span>
            <input
              v-model.number="modelConfig.max_tokens"
              type="number"
              min="100"
              max="32000"
              step="100"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
            />
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              单次生成的最大token数量
            </div>
          </label>

          <!-- Timeout -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">请求超时（秒）</span>
            <input
              v-model.number="modelConfig.timeout"
              type="number"
              min="10"
              max="600"
              step="10"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
            />
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              API请求超时时间
            </div>
          </label>

          <!-- Retry Strategy -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">重试次数</span>
            <input
              v-model.number="modelConfig.max_retries"
              type="number"
              min="0"
              max="10"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
            />
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              请求失败时的最大重试次数
            </div>
          </label>

          <!-- Save Button -->
          <div style="display: flex; gap: 12px;">
            <button class="gh-btn gh-btn-primary" @click="saveModelConfig" :disabled="saving">
              {{ saving ? '保存中...' : '保存配置' }}
            </button>
            <button class="gh-btn" @click="testModelConfig" :disabled="testingModel || saving">
              {{ testingModel ? '测试中...' : '测试模型连接' }}
            </button>
            <button class="gh-btn" @click="loadModelConfig">重置</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 系统配置 -->
    <section v-show="activeTab === 'system'">
      <h2 class="gh-heading">系统配置</h2>

      <div class="gh-panel" style="margin-bottom: 16px;">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">服务管理</span>
        </div>
        <div class="gh-panel-body">
          <div style="margin-bottom: 16px;">
            <div style="font-size: 13px; color: #656d76; margin-bottom: 12px;">
              重启后端服务以应用配置更改。注意：重启会中断正在执行的任务。
            </div>
            <button
              class="gh-btn gh-btn-danger"
              @click="restartService"
              :disabled="restarting"
            >
              {{ restarting ? '重启中...' : '重启服务' }}
            </button>
          </div>
        </div>
      </div>

      <div class="gh-panel">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">系统参数</span>
        </div>
        <div class="gh-panel-body" style="display: grid; gap: 16px;">
          <!-- Aspen服务地址 -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">Aspen服务地址</span>
            <input
              v-model="systemConfig.aspen_service_url"
              type="text"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
              placeholder="例如：https://119.3.160.243:7777"
            />
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              外部Aspen模拟服务的HTTP地址
            </div>
          </label>

          <!-- Save Button -->
          <div style="display: flex; gap: 12px;">
            <button class="gh-btn gh-btn-primary" @click="saveSystemConfig" :disabled="saving">
              {{ saving ? '保存中...' : '保存配置' }}
            </button>
            <button class="gh-btn" @click="testSystemConfig" :disabled="testingAspen || saving">
              {{ testingAspen ? '测试中...' : '测试连接' }}
            </button>
            <button class="gh-btn" @click="loadSystemConfig">重置</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 用户管理 -->
    <section v-show="activeTab === 'users'">
      <h2 class="gh-heading">用户管理</h2>

      <div class="gh-panel" style="margin-bottom: 16px;">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">用户列表</span>
          <button class="gh-btn" @click="loadUsers" style="font-size: 12px;">刷新</button>
        </div>
        <div class="gh-panel-body" style="padding: 0;">
          <div v-if="loadingUsers" class="gh-empty">加载中...</div>
          <table v-else class="gh-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>角色</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="users.length === 0">
                <td colspan="4" class="gh-empty">暂无用户</td>
              </tr>
              <tr v-for="u in users" :key="u.user_id">
                <td style="font-size: 13px;">{{ u.phone }}</td>
                <td>
                  <span class="gh-label" :class="u.role === 'admin' ? 'gh-label-info' : 'gh-label-muted'">
                    {{ u.role === 'admin' ? '管理员' : '普通用户' }}
                  </span>
                </td>
                <td style="font-size: 12px; color: #656d76;">{{ fmtTs(u.created_at) }}</td>
                <td>
                  <div style="display: flex; gap: 6px;">
                    <button class="gh-btn" style="font-size: 11px; padding: 2px 8px;" @click="resetUserPassword(u)">重置密码</button>
                    <button v-if="u.role !== 'admin'" class="gh-btn gh-btn-danger" style="font-size: 11px; padding: 2px 8px;" @click="deleteUser(u)">删除</button>
                  </div>
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
import SettingsLayout from "../components/SettingsLayout.vue";
import { fetchJson, postJson } from "../services/api";
import { toastError, toastSuccess } from "../services/toast";
import "../assets/github-theme.css";

const activeTab = ref("model");
const saving = ref(false);
const restarting = ref(false);
const testingModel = ref(false);
const testingAspen = ref(false);
const showApiKey = ref(false);

function fmtTs(ts) {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
}

const _i = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;
const sidebarGroups = [
  {
    label: "",
    items: [
      { id: "model", label: "模型配置", icon: _i("M12 2a3 3 0 0 0-3 3v1a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3zM19 9a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3zM5 9a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3zM12 18a3 3 0 0 0-3 3 3 3 0 0 0 6 0 3 3 0 0 0-3-3z") },
      { id: "system", label: "系统配置", icon: _i("M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z") },
      { id: "users", label: "用户管理", icon: _i("M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75") },
    ]
  }
];

// Model Configuration
const modelConfig = ref({
  model_name: "qwen3-max",
  api_base: "",
  api_key: "",
  temperature: 0.7,
  top_p: 0.9,
  max_tokens: 4096,
  timeout: 120,
  max_retries: 3
});

// System Configuration
const systemConfig = ref({
  aspen_service_url: "https://119.3.160.243:7777",
});

function showSuccess(message) {
  toastSuccess(message);
}

function showError(message) {
  toastError(message);
}

async function loadModelConfig() {
  try {
    const data = await fetchJson("/api/settings/model");
    if (data) {
      modelConfig.value = { ...modelConfig.value, ...data };
    }
  } catch (err) {
    console.warn("Failed to load model config:", err);
  }
}

async function saveModelConfig() {
  try {
    saving.value = true;
    await postJson("/api/settings/model", modelConfig.value);
    showSuccess("模型配置已保存");
  } catch (err) {
    showError(err.message || "保存模型配置失败");
  } finally {
    saving.value = false;
  }
}

async function testModelConfig() {
  try {
    testingModel.value = true;
    const result = await postJson("/api/settings/model/test", modelConfig.value);
    const latency = result?.latency_ms ? `，耗时 ${result.latency_ms} ms` : "";
    const preview = result?.reply_preview ? `，返回：${result.reply_preview}` : "";
    showSuccess(`模型连接测试成功${latency}${preview}`);
  } catch (err) {
    showError(err.message || "模型连接测试失败");
  } finally {
    testingModel.value = false;
  }
}

async function loadSystemConfig() {
  try {
    const data = await fetchJson("/api/settings/system");
    if (data) {
      systemConfig.value = { ...systemConfig.value, ...data };
    }
  } catch (err) {
    console.warn("Failed to load system config:", err);
  }
}

async function saveSystemConfig() {
  try {
    saving.value = true;
    await postJson("/api/settings/system", systemConfig.value);
    showSuccess("系统配置已保存");
  } catch (err) {
    showError(err.message || "保存系统配置失败");
  } finally {
    saving.value = false;
  }
}

async function testSystemConfig() {
  try {
    testingAspen.value = true;
    const result = await postJson("/api/settings/system/test", systemConfig.value);
    const latency = result?.latency_ms ? `，耗时 ${result.latency_ms} ms` : "";
    const statusCode = result?.status_code ? `，HTTP ${result.status_code}` : "";
    const endpoint = result?.endpoint ? `，目标：${result.endpoint}` : "";
    showSuccess(`Aspen服务连接测试成功${latency}${statusCode}${endpoint}`);
  } catch (err) {
    showError(err.message || "Aspen服务连接测试失败");
  } finally {
    testingAspen.value = false;
  }
}

async function restartService() {
  if (!confirm("确定要重启服务吗？这将中断所有正在执行的任务。")) {
    return;
  }

  try {
    restarting.value = true;
    await postJson("/api/settings/restart", {});
    showSuccess("服务重启请求已发送，请等待约10秒后刷新页面");
  } catch (err) {
    showError(err.message || "重启服务失败");
  } finally {
    restarting.value = false;
  }
}

onMounted(() => {
  loadModelConfig();
  loadSystemConfig();
  loadUsers();
});

// User management
const users = ref([]);
const loadingUsers = ref(false);

async function loadUsers() {
  loadingUsers.value = true;
  try {
    const data = await fetchJson("/api/admin/users");
    users.value = data.users || [];
  } catch (err) {
    console.warn("Failed to load users:", err);
  } finally {
    loadingUsers.value = false;
  }
}

async function resetUserPassword(user) {
  const newPwd = prompt(`重置用户 ${user.phone} 的密码为：`, "123456");
  if (!newPwd) return;
  try {
    await postJson(`/api/admin/users/${user.user_id}/reset-password`, { new_password: newPwd });
    showSuccess(`用户 ${user.phone} 密码已重置`);
  } catch (err) {
    showError(err.message || "重置密码失败");
  }
}

async function deleteUser(user) {
  if (!confirm(`确定删除用户 ${user.phone} 吗？此操作不可撤销。`)) return;
  try {
    await postJson(`/api/admin/users/${user.user_id}/delete`, {});
    showSuccess(`用户 ${user.phone} 已删除`);
    await loadUsers();
  } catch (err) {
    showError(err.message || "删除用户失败");
  }
}
</script>

<style scoped>
.mb-4 {
  margin-bottom: 16px;
}
</style>

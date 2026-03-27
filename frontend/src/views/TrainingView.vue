<template>
  <SettingsLayout
    title="训练评审与发布"
    :active="tab"
    :groups="sidebarGroups"
    @select="tab = $event"
  >
    <!-- Global error banner -->
    <div v-if="errorText" class="gh-panel" style="border-color: #d1242f; margin-bottom: 16px;">
      <div class="gh-panel-body" style="display: flex; align-items: center; justify-content: space-between;">
        <span style="color: #d1242f; font-size: 13px;">{{ errorText }}</span>
        <button class="gh-btn gh-btn-danger" style="font-size: 12px;" @click="errorText = ''">关闭</button>
      </div>
    </div>

    <!-- ===================== TAB: 发布操作 ===================== -->
    <section v-show="tab === 'publish'">
      <h2 class="gh-heading">发布操作</h2>

      <!-- Run selector -->
      <div class="gh-panel" style="margin-bottom: 16px;">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">选择训练运行</span>
          <div style="display: flex; gap: 8px; align-items: center;">
            <span class="gh-label gh-label-muted">{{ runs.length }} 个运行</span>
            <button class="gh-btn" @click="loadRuns" style="font-size: 12px;">刷新</button>
          </div>
        </div>
        <div class="gh-panel-body" style="padding: 8px 12px;">
          <div v-if="runs.length === 0" class="gh-empty">暂无训练运行数据</div>
          <div v-else style="display: flex; flex-wrap: wrap; gap: 6px;">
            <button
              v-for="run in runs"
              :key="run.run_id"
              class="gh-btn"
              :style="{
                background: selectedRun?.run_id === run.run_id ? '#0969da' : undefined,
                color: selectedRun?.run_id === run.run_id ? '#fff' : undefined,
                borderColor: selectedRun?.run_id === run.run_id ? '#0969da' : undefined,
              }"
              @click="selectRun(run)"
            >
              {{ run.run_id }}
              <span v-if="run.has_training_report" class="gh-label gh-label-info" style="margin-left: 4px; font-size: 10px;">report</span>
            </button>
          </div>
        </div>
      </div>

      <div v-if="!selectedRun" class="gh-panel">
        <div class="gh-empty">请先选择一个训练运行</div>
      </div>

      <template v-else>
        <!-- File Review Section -->
        <div class="gh-panel" style="margin-bottom: 16px;">
          <div class="gh-panel-header">
            <span class="gh-panel-header-title">训练产物文件</span>
            <span class="gh-label gh-label-muted">{{ runFiles.length }} 个文件</span>
          </div>
          <div class="gh-panel-body" style="padding: 8px 12px;">
            <div v-if="runFiles.length === 0" class="gh-empty">暂无候选文件</div>
            <div v-else style="display: flex; flex-wrap: wrap; gap: 6px;">
              <button
                v-for="f in runFiles"
                :key="f"
                class="gh-btn"
                :style="{
                  background: selectedFileName === f ? '#0969da' : undefined,
                  color: selectedFileName === f ? '#fff' : undefined,
                  borderColor: selectedFileName === f ? '#0969da' : undefined,
                }"
                @click="loadFile(f)"
              >
                {{ f }}
              </button>
            </div>
          </div>
        </div>

        <!-- File content viewer -->
        <div v-if="selectedFileName" class="gh-panel" style="margin-bottom: 16px;">
          <div class="gh-panel-header">
            <span class="gh-panel-header-title">{{ selectedFileName }}</span>
          </div>
          <div class="gh-panel-body" style="padding: 0;">
            <pre class="gh-code" style="margin: 0; border: none; border-radius: 0; max-height: 400px; overflow: auto;">{{ fileContent }}</pre>
          </div>
        </div>

        <hr class="gh-divider" />

        <!-- Prompt targets -->
        <div class="gh-panel" style="margin-bottom: 16px;">
          <div class="gh-panel-header">
            <span class="gh-panel-header-title">本次可发布的提示词增量</span>
          </div>
          <div class="gh-panel-body">
            <div v-if="selectedPromptCandidates.length === 0" class="gh-empty">当前运行无可发布的提示词增量文件</div>
            <div v-else style="display: flex; flex-direction: column; gap: 8px;">
              <label
                v-for="item in selectedPromptCandidates"
                :key="item.base_name"
                style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;"
              >
                <input type="checkbox" :value="item.base_name" v-model="publishOptions.prompt_targets" style="accent-color: #0969da;" />
                <span style="font-weight: 600; color: #1f2328;">{{ item.label }}</span>
                <span style="font-size: 12px; color: #656d76;">{{ item.file }}</span>
              </label>
            </div>
          </div>
        </div>

        <!-- Publish button -->
        <div class="gh-panel" style="margin-bottom: 16px;">
          <div class="gh-panel-header">
            <span class="gh-panel-header-title">执行发布</span>
          </div>
          <div class="gh-panel-body">
            <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
              <button
                class="gh-btn gh-btn-primary"
                :disabled="publishing || !publishOptions.prompt_targets.length"
                @click="publish"
              >
                {{ publishing ? '发布中...' : '执行发布' }}
              </button>
              <span v-if="!publishOptions.prompt_targets.length" style="font-size: 12px; color: #656d76;">
                请选择至少一个发布目标
              </span>
            </div>
          </div>
        </div>

        <!-- Publish result with link to prompts -->
        <div v-if="publishResult" class="gh-panel" style="margin-bottom: 16px; border-color: #1a7f37;">
          <div class="gh-panel-header" style="border-bottom-color: #1a7f37;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" style="width: 16px; height: 16px; color: #1a7f37;">
                <path fill-rule="evenodd" d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.75.75 0 0 1 1.06-1.06L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z" clip-rule="evenodd" />
              </svg>
              <span class="gh-panel-header-title" style="color: #1a7f37;">发布成功</span>
            </div>
            <div style="display: flex; gap: 8px;">
              <button class="gh-btn gh-btn-primary" @click="tab = 'prompts'" style="font-size: 12px;">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" style="width: 14px; height: 14px; margin-right: 4px;">
                  <path fill-rule="evenodd" d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06l-3.25 3.25a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" />
                </svg>
                查看提示词
              </button>
              <button class="gh-btn" @click="publishResult = ''; publishPreviews = []" style="font-size: 12px;">关闭</button>
            </div>
          </div>
          <div class="gh-panel-body">
            <div style="padding: 12px; background: #dafbe1; border-radius: 6px; margin-bottom: 12px;">
              <div style="font-size: 13px; font-weight: 600; color: #1a7f37; margin-bottom: 4px;">✓ 提示词已成功发布到生产环境</div>
              <div style="font-size: 12px; color: #1f2328;">
                已更新 {{ publishOptions.prompt_targets.length }} 个提示词文件。
                <button @click="tab = 'prompts'" style="color: #0969da; text-decoration: underline; background: none; border: none; padding: 0; cursor: pointer; font-size: 12px;">
                  点击这里查看最新的提示词内容 →
                </button>
              </div>
            </div>
            <details style="cursor: pointer;">
              <summary style="font-size: 12px; color: #656d76; padding: 8px 0;">查看详细发布日志</summary>
              <pre class="gh-code" style="margin: 8px 0 0 0; border: none; border-radius: 0; max-height: 350px; overflow: auto;">{{ publishResult }}</pre>
            </details>
          </div>
        </div>

        <!-- Publish previews -->
        <div v-if="publishPreviews.length > 0" class="gh-panel" style="margin-bottom: 16px;">
          <div class="gh-panel-header">
            <span class="gh-panel-header-title">发布后完整提示词内容</span>
          </div>
          <div class="gh-panel-body" style="padding: 0;">
            <div v-for="pv in publishPreviews" :key="pv.base_name" style="border-bottom: 1px solid #eaeef2;">
              <div style="padding: 8px 14px; background: #f6f8fa; font-size: 13px; display: flex; justify-content: space-between;">
                <span style="font-weight: 600; color: #1f2328;">{{ pv.label }}</span>
                <span style="font-size: 12px; color: #656d76;">{{ pv.target_path }}</span>
              </div>
              <pre class="gh-code" style="margin: 0; border: none; border-radius: 0; max-height: 400px; overflow: auto;">{{ pv.content_after }}</pre>
            </div>
          </div>
        </div>

        <hr class="gh-divider" />

        <!-- Clear all artifacts -->
        <div class="gh-panel" style="border-color: #ffcecb;">
          <div class="gh-panel-header" style="border-bottom-color: #ffcecb;">
            <span class="gh-panel-header-title" style="color: #d1242f;">危险操作</span>
          </div>
          <div class="gh-panel-body" style="display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-size: 13px; font-weight: 600; color: #1f2328;">清除所有产物</div>
              <div style="font-size: 12px; color: #656d76; margin-top: 2px;">删除所有训练产物，此操作不可撤销。</div>
            </div>
            <button
              class="gh-btn gh-btn-danger"
              :disabled="clearingArtifacts || !runs.length"
              @click="clearAllArtifacts"
            >
              {{ clearingArtifacts ? '清除中...' : '清除所有产物' }}
            </button>
          </div>
        </div>
      </template>
    </section>

    <!-- ===================== TAB: 提示词管理 ===================== -->
    <section v-show="tab === 'prompts'">
      <h2 class="gh-heading">提示词管理</h2>

      <!-- Prompt Editors -->
      <div class="gh-panel" style="margin-bottom: 16px;">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">提示词编辑</span>
          <div style="display: flex; gap: 8px;">
            <button class="gh-btn" @click="loadCurrentPrompts" style="font-size: 12px;">加载当前提示词</button>
            <button class="gh-btn gh-btn-primary" @click="savePrompts" :disabled="savingPrompts" style="font-size: 12px;">
              {{ savingPrompts ? '保存中...' : '保存提示词' }}
            </button>
          </div>
        </div>
        <div class="gh-panel-body" style="padding: 0;">
          <div v-for="(prompt, idx) in editablePrompts" :key="prompt.name" :style="{ borderBottom: idx < editablePrompts.length - 1 ? '1px solid #eaeef2' : 'none' }">
            <div style="padding: 12px 16px; background: #f6f8fa; display: flex; justify-content: space-between; align-items: center;">
              <div>
                <span style="font-weight: 600; font-size: 13px; color: #1f2328;">{{ prompt.label }}</span>
                <span style="font-size: 12px; color: #656d76; margin-left: 8px;">{{ prompt.file }}</span>
              </div>
              <button class="gh-btn" @click="togglePromptExpand(prompt.name)" style="font-size: 11px; padding: 2px 8px;">
                {{ prompt.expanded ? '收起' : '展开' }}
              </button>
            </div>
            <div v-show="prompt.expanded" style="padding: 12px;">
              <textarea
                v-model="prompt.content"
                class="gh-input"
                style="width: 100%; min-height: 300px; font-family: ui-monospace, monospace; font-size: 12px; resize: vertical;"
                :placeholder="`输入${prompt.label}内容...`"
              ></textarea>
              <div style="margin-top: 8px; font-size: 12px; color: #656d76;">
                字符数: {{ prompt.content.length }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Save Result -->
      <div v-if="promptSaveResult" class="gh-panel" style="margin-bottom: 16px;">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">保存结果</span>
          <button class="gh-btn" @click="promptSaveResult = ''" style="font-size: 12px;">关闭</button>
        </div>
        <div class="gh-panel-body" style="padding: 0;">
          <pre class="gh-code" style="margin: 0; border: none; border-radius: 0; max-height: 300px; overflow: auto;">{{ promptSaveResult }}</pre>
        </div>
      </div>
    </section>

    <!-- ===================== TAB: Schema文件管理 ===================== -->
    <section v-show="tab === 'schemas'">
      <h2 class="gh-heading">Schema文件管理</h2>

      <!-- Error Display -->
      <div v-if="schemaError" class="gh-panel" style="border-color: #d1242f; margin-bottom: 16px;">
        <div class="gh-panel-body" style="display: flex; align-items: center; justify-content: space-between;">
          <span style="color: #d1242f; font-size: 13px;">{{ schemaError }}</span>
          <button class="gh-btn gh-btn-danger" style="font-size: 12px;" @click="schemaError = ''">关闭</button>
        </div>
      </div>

      <!-- Success Display -->
      <div v-if="schemaSaveResult" class="gh-panel" style="border-color: #1a7f37; margin-bottom: 16px;">
        <div class="gh-panel-body" style="display: flex; align-items: center; justify-content: space-between;">
          <span style="color: #1a7f37; font-size: 13px;">{{ schemaSaveResult }}</span>
          <button class="gh-btn" style="font-size: 12px;" @click="schemaSaveResult = ''">关闭</button>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 300px 1fr; gap: 16px;">
        <!-- File List -->
        <div class="gh-panel">
          <div class="gh-panel-header">
            <span class="gh-panel-header-title">Schema文件列表</span>
            <button class="gh-btn" @click="loadSchemaFiles" style="font-size: 12px;">刷新</button>
          </div>
          <div class="gh-panel-body" style="padding: 0;">
            <div v-if="loadingSchemas" class="gh-empty">加载中...</div>
            <div v-else-if="schemaFiles.length === 0" class="gh-empty">暂无文件</div>
            <div v-else style="max-height: 600px; overflow-y: auto;">
              <div
                v-for="file in schemaFiles"
                :key="file.name"
                @click="loadSchemaFile(file.name)"
                style="padding: 12px 16px; border-bottom: 1px solid #eaeef2; cursor: pointer; transition: background 0.1s;"
                :style="{
                  background: selectedSchemaFile === file.name ? '#f6f8fa' : 'transparent',
                  borderLeft: selectedSchemaFile === file.name ? '3px solid #0969da' : '3px solid transparent'
                }"
                @mouseover="$event.currentTarget.style.background = '#f6f8fa'"
                @mouseleave="$event.currentTarget.style.background = selectedSchemaFile === file.name ? '#f6f8fa' : 'transparent'"
              >
                <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 4px;">{{ file.name }}</div>
                <div style="font-size: 11px; color: #656d76;">
                  {{ formatFileSize(file.size) }} · {{ formatDate(file.modified) }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- File Editor -->
        <div class="gh-panel">
          <div class="gh-panel-header">
            <span class="gh-panel-header-title">{{ selectedSchemaFile || '请选择文件' }}</span>
            <button
              v-if="selectedSchemaFile"
              class="gh-btn gh-btn-primary"
              @click="saveSchemaFile"
              :disabled="savingSchema"
              style="font-size: 12px;"
            >
              {{ savingSchema ? '保存中...' : '保存文件' }}
            </button>
          </div>
          <div class="gh-panel-body">
            <div v-if="!selectedSchemaFile" class="gh-empty">请从左侧选择一个Schema文件进行编辑</div>
            <div v-else>
              <textarea
                v-model="schemaFileContent"
                class="gh-input"
                style="width: 100%; min-height: 500px; font-family: ui-monospace, monospace; font-size: 12px; resize: vertical;"
                placeholder="Schema文件内容..."
              ></textarea>
              <div style="margin-top: 8px; font-size: 12px; color: #656d76;">
                字符数: {{ schemaFileContent.length }}
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
import { useRoute } from "vue-router";
import { fetchJson, postJson } from "../services/api";
import SettingsLayout from "../components/SettingsLayout.vue";
import "../assets/github-theme.css";

const route = useRoute();

/* ---- sidebar / tab state ---- */
const tab = ref("publish");

const _i = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;
const sidebarGroups = [
  {
    label: "",
    items: [
      { id: "publish", label: "发布操作", icon: _i("M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M16 6l-4-4-4 4M12 2v13") },
      { id: "prompts", label: "提示词管理", icon: _i("M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z") },
      { id: "schemas", label: "Schema文件管理", icon: _i("M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M12 18v-6M9 15l3 3 3-3") },
    ],
  },
];

/* ---- state ---- */
const runs = ref([]);
const selectedRun = ref(null);
const selectedFileName = ref("");
const fileContent = ref("");
const publishing = ref(false);
const clearingArtifacts = ref(false);
const publishResult = ref("");
const errorText = ref("");
const publishPreviews = ref([]);

const publishOptions = ref({
  prompt_targets: [],
});

// Prompt management state
const loadingPrompts = ref(false);
const savingPrompts = ref(false);
const promptSaveResult = ref("");
const editablePrompts = ref([
  { name: 'system_prompt', label: '系统提示词', file: 'llm_prompt.py', content: '', expanded: false },
  { name: 'schema_check_prompt', label: 'Schema检查提示词', file: 'schema_check.py', content: '', expanded: false },
  { name: 'thought_process_prompt', label: '思维链提示词', file: 'thought_process.py', content: '', expanded: false },
  { name: 'schema_get_prompt', label: 'Schema获取提示词', file: 'schema_get.py', content: '', expanded: false },
  { name: 'result_get_prompt', label: '结果获取提示词', file: 'result_get.py', content: '', expanded: false },
]);

// Schema management state
const schemaFiles = ref([]);
const selectedSchemaFile = ref(null);
const schemaFileContent = ref("");
const loadingSchemas = ref(false);
const savingSchema = ref(false);
const schemaError = ref("");
const schemaSaveResult = ref("");

/* ---- computed ---- */
const runFiles = computed(() => {
  const files = selectedRun.value?.files;
  if (!Array.isArray(files)) return [];
  // 只显示提示词候选 .txt 文件
  return files.filter(f => typeof f === 'string' && f.endsWith('.txt') && f.includes('prompt_candidate'));
});

function detectPromptCandidates(run) {
  const files = Array.isArray(run?.files) ? run.files : [];
  const defs = [
    { base_name: "system_prompt_candidate", label: "系统提示词", prefix: "system_prompt_candidate" },
    { base_name: "schema_check_prompt_candidate", label: "Schema检查提示词", prefix: "schema_check_prompt_candidate" },
    { base_name: "thought_process_prompt_candidate", label: "思维链提示词", prefix: "thought_process_prompt_candidate" },
  ];
  return defs
    .map((d) => {
      const f = files.find((x) => {
        const n = String(x || "");
        return n.startsWith(d.prefix) && n.endsWith(".txt");
      });
      return f ? { ...d, file: f } : null;
    })
    .filter(Boolean);
}

const selectedPromptCandidates = computed(() => detectPromptCandidates(selectedRun.value));

/* ---- API functions ---- */
async function loadRuns() {
  errorText.value = "";
  try {
    const data = await fetchJson("/api/training/runs?limit=40");
    runs.value = data.runs || [];
    const queryRunId = String(route.query.run_id || "").trim();
    if (queryRunId) {
      const target = runs.value.find((x) => x.run_id === queryRunId);
      if (target) selectRun(target);
    }
    if (selectedRun.value) {
      const matched = runs.value.find((x) => x.run_id === selectedRun.value.run_id);
      selectedRun.value = matched || null;
    }
  } catch (err) {
    errorText.value = String(err?.message || err);
  }
}

function selectRun(run) {
  selectedRun.value = run;
  selectedFileName.value = "";
  fileContent.value = "";
  publishResult.value = "";
  publishPreviews.value = [];
  publishOptions.value.prompt_targets = detectPromptCandidates(run).map((x) => x.base_name);
}

async function loadFile(fileName) {
  if (!selectedRun.value) return;
  selectedFileName.value = fileName;
  fileContent.value = "加载中...";
  try {
    const data = await fetchJson(`/api/training/runs/${encodeURIComponent(selectedRun.value.run_id)}/files/${encodeURIComponent(fileName)}`);
    if (data.json !== null && data.json !== undefined) {
      fileContent.value = JSON.stringify(data.json, null, 2);
    } else {
      fileContent.value = String(data.content || "");
    }
  } catch (err) {
    fileContent.value = `加载失败: ${String(err?.message || err)}`;
  }
}

async function publish() {
  if (!selectedRun.value || !publishOptions.value.prompt_targets.length) return;
  publishing.value = true;
  errorText.value = "";
  publishResult.value = "";
  publishPreviews.value = [];
  try {
    const data = await postJson("/api/training/publish", {
      run_id: selectedRun.value.run_id,
      apply_prompts: true,
      apply_schema: false,
      dry_run: false,
      prompt_targets: publishOptions.value.prompt_targets,
      register_prompt_version: false,
    });
    publishResult.value = JSON.stringify(data, null, 2);

    const promptStep = Array.isArray(data?.results)
      ? data.results.find((x) => x?.step === "apply_prompts")
      : null;
    const details = Array.isArray(promptStep?.parsed?.details) ? promptStep.parsed.details : [];
    const labelMap = {
      system_prompt_candidate: "系统提示词",
      schema_check_prompt_candidate: "Schema检查提示词",
      thought_process_prompt_candidate: "思维链提示词",
    };
    publishPreviews.value = details
      .filter((d) => publishOptions.value.prompt_targets.includes(d.base_name))
      .map((d) => ({
        base_name: d.base_name,
        label: labelMap[d.base_name] || d.base_name,
        target_path: d.target_path,
        content_after: String(d.content_after || ""),
      }));
  } catch (err) {
    errorText.value = String(err?.message || err);
  } finally {
    publishing.value = false;
  }
}

async function clearAllArtifacts() {
  if (!runs.value.length) return;
  const ok = window.confirm("确认清空所有训练产物吗？此操作不可恢复。");
  if (!ok) return;

  clearingArtifacts.value = true;
  errorText.value = "";
  publishResult.value = "";
  publishPreviews.value = [];
  fileContent.value = "";
  selectedFileName.value = "";

  try {
    const data = await postJson("/api/training/runs/clear", {});
    publishResult.value = JSON.stringify(data, null, 2);
    selectedRun.value = null;
    await loadRuns();
  } catch (err) {
    errorText.value = String(err?.message || err);
  } finally {
    clearingArtifacts.value = false;
  }
}

async function loadCurrentPrompts() {
  loadingPrompts.value = true;
  try {
    const response = await fetchJson("/api/prompt/current");
    if (response.prompts) {
      editablePrompts.value.forEach(prompt => {
        if (response.prompts[prompt.name]) {
          prompt.content = response.prompts[prompt.name];
        }
      });
    }
  } catch (err) {
    errorText.value = `加载提示词失败: ${String(err?.message || err)}`;
  } finally {
    loadingPrompts.value = false;
  }
}

async function savePrompts() {
  savingPrompts.value = true;
  promptSaveResult.value = "";
  try {
    const prompts = {};
    editablePrompts.value.forEach(prompt => {
      if (prompt.content.trim()) {
        prompts[prompt.name] = prompt.content;
      }
    });

    const data = await postJson("/api/prompt/update", { prompts });
    promptSaveResult.value = JSON.stringify(data, null, 2);
  } catch (err) {
    errorText.value = `保存失败: ${String(err?.message || err)}`;
  } finally {
    savingPrompts.value = false;
  }
}

function togglePromptExpand(name) {
  const prompt = editablePrompts.value.find(p => p.name === name);
  if (prompt) {
    prompt.expanded = !prompt.expanded;
  }
}

// Schema management functions
async function loadSchemaFiles() {
  loadingSchemas.value = true;
  schemaError.value = "";
  try {
    const data = await fetchJson("/api/schema/files");
    if (data.ok) {
      schemaFiles.value = data.files || [];
    } else {
      schemaError.value = data.error || "加载Schema文件列表失败";
    }
  } catch (err) {
    schemaError.value = `加载失败: ${String(err?.message || err)}`;
  } finally {
    loadingSchemas.value = false;
  }
}

async function loadSchemaFile(filename) {
  loadingSchemas.value = true;
  schemaError.value = "";
  try {
    const data = await fetchJson(`/api/schema/file?filename=${encodeURIComponent(filename)}`);
    if (data.ok) {
      schemaFileContent.value = data.content || "";
      selectedSchemaFile.value = filename;
    } else {
      schemaError.value = data.error || "加载Schema文件内容失败";
    }
  } catch (err) {
    schemaError.value = `加载失败: ${String(err?.message || err)}`;
  } finally {
    loadingSchemas.value = false;
  }
}

async function saveSchemaFile() {
  if (!selectedSchemaFile.value) {
    schemaError.value = "请先选择一个文件";
    return;
  }

  savingSchema.value = true;
  schemaSaveResult.value = "";
  schemaError.value = "";
  try {
    const data = await postJson("/api/schema/file", {
      filename: selectedSchemaFile.value,
      content: schemaFileContent.value
    });

    if (data.ok) {
      schemaSaveResult.value = data.message || "保存成功";
      // Reload file list to update modification time
      await loadSchemaFiles();
    } else {
      schemaError.value = data.error || "保存失败";
    }
  } catch (err) {
    schemaError.value = `保存失败: ${String(err?.message || err)}`;
  } finally {
    savingSchema.value = false;
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(timestamp) {
  return new Date(timestamp * 1000).toLocaleString('zh-CN');
}


/* ---- route watcher ---- */
watch(
  () => route.query.run_id,
  () => {
    const queryRunId = String(route.query.run_id || "").trim();
    if (!queryRunId || !runs.value.length) return;
    const target = runs.value.find((x) => x.run_id === queryRunId);
    if (target) selectRun(target);
  }
);

/* ---- init ---- */
onMounted(() => {
  loadRuns();
  loadSchemaFiles();
});
</script>

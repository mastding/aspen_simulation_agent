<template>
  <SettingsLayout
    title="训练工作台"
    :active="tab"
    :groups="sidebarGroups"
    @select="tab = $event"
  >
    <!-- ===================== TAB: 采样配置 ===================== -->
    <section v-show="tab === 'sampling'">
      <h2 class="gh-heading">训练任务</h2>

      <div class="gh-panel">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">任务配置</span>
        </div>
        <div class="gh-panel-body" style="display: grid; gap: 16px;">
          <!-- 1. 任务名称 -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">任务名称</span>
            <input
              v-model="taskName"
              type="text"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
              placeholder="例如：乙苯脱氢小样本训练"
            />
          </label>

          <!-- 3. 训练模式 -->
          <label style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">训练模式</span>
            <select v-model="trainingMode" class="gh-select" style="width: 100%; margin-top: 4px;">
              <option value="offline">离线训练（仅生成提示词）</option>
              <option value="online">在线训练（迭代训练+自动发布）</option>
            </select>
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              {{ trainingMode === 'offline' ? '单次训练，生成提示词候选' : '多轮迭代：执行任务→训练→自动发布提示词→下一轮' }}
            </div>
          </label>

          <!-- 3.5. 在线训练迭代次数 -->
          <label v-if="trainingMode === 'online'" style="display: block;">
            <span style="font-size: 13px; font-weight: 600; color: #1f2328;">迭代次数</span>
            <input
              v-model.number="onlineIterations"
              type="number"
              min="1"
              max="10"
              class="gh-input"
              style="width: 100%; margin-top: 4px;"
            />
            <div style="font-size: 12px; color: #656d76; margin-top: 4px;">
              每轮迭代会执行任务、训练并自动发布提示词，建议2-5轮
            </div>
          </label>

          <!-- 4. 采样任务（JSON） -->
          <div>
            <label style="display: block; font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 6px;">采样任务（JSON）</label>
            <textarea
              v-model="tasksText"
              class="gh-input"
              style="width: 100%; min-height: 200px; font-family: ui-monospace, monospace; font-size: 12px; resize: vertical;"
              placeholder='示例：{"tasks":[{"msg":"【设备清单】使用设备：混合器 Mixer\n【进料条件】..."}]}'
            />
            <div style="margin-top: 8px; font-size: 12px; color: #656d76;">当前任务数：{{ parsedTasks.length }}</div>
            <div v-if="taskInputError" style="margin-top: 6px; font-size: 12px; color: #d1242f;">{{ taskInputError }}</div>
          </div>

          <!-- 5. 启动/停止按钮 -->
          <div style="display: flex; align-items: center; gap: 12px; padding-top: 4px;">
            <button
              class="gh-btn gh-btn-primary"
              :disabled="starting || parsedTasks.length === 0 || isRunning"
              @click="startJob"
            >
              启动任务
            </button>
            <button
              class="gh-btn gh-btn-danger"
              :disabled="!currentJobId || !isRunning || stopping"
              @click="stopJob"
            >
              停止任务
            </button>
          </div>
          <!-- 启动成功/停止提示 -->
          <div v-if="startSuccessNotice" style="padding: 8px 12px; background: #dafbe1; border: 1px solid #aceebb; border-radius: 6px;">
            <div style="font-size: 12px; color: #1a7f37; display: flex; align-items: center; gap: 6px;">
              <svg style="width: 14px; height: 14px; flex-shrink: 0;" viewBox="0 0 16 16" fill="#1a7f37">
                <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"></path>
              </svg>
              {{ startSuccessNotice }}
            </div>
          </div>
          <div v-if="stopNotice" style="padding: 8px 12px; background: #fff8c5; border: 1px solid #d4a72c; border-radius: 6px;">
            <div style="font-size: 12px;" :style="{ color: stopNoticeType === 'error' ? '#d1242f' : '#9a6700' }">
              {{ stopNotice }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===================== TAB: 运行结果 ===================== -->
    <section v-show="tab === 'control'">
      <h2 class="gh-heading">运行结果</h2>

      <div class="gh-panel" style="margin-bottom: 16px;">
        <div class="gh-panel-header">
          <div style="flex: 1;">
            <span class="gh-panel-header-title">运行状态</span>
          </div>
          <button class="gh-btn" style="font-size: 12px;" @click="refreshJobs">刷新</button>
        </div>
        <div class="gh-panel-body">
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
            <div class="gh-stat-card">
              <div class="gh-stat-label">当前任务 ID</div>
              <div class="gh-stat-value" style="font-size: 14px; font-family: monospace; word-break: break-all;">{{ currentJobId || "-" }}</div>
            </div>
            <div class="gh-stat-card">
              <div class="gh-stat-label">任务名称</div>
              <div class="gh-stat-value" style="font-size: 14px;">{{ jobTaskName }}</div>
            </div>
            <div class="gh-stat-card">
              <div class="gh-stat-label">状态</div>
              <div class="gh-stat-value" style="font-size: 14px;">{{ jobDetail?.status || "-" }}</div>
            </div>
            <div class="gh-stat-card">
              <div class="gh-stat-label">阶段</div>
              <div class="gh-stat-value" style="font-size: 14px;">{{ jobDetail?.stage || "-" }}</div>
            </div>
            <div class="gh-stat-card">
              <div class="gh-stat-label">训练模式</div>
              <div class="gh-stat-value" style="font-size: 14px;">{{ jobDetail?.config?.training_mode === 'online' ? '在线训练' : '离线训练' }}</div>
            </div>
          </div>

          <div style="margin-bottom: 12px;">
            <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 6px;">任务统计</div>
            <div style="font-size: 13px; color: #656d76;">{{ summaryText }}</div>
          </div>

          <div style="margin-bottom: 12px;">
            <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 6px;">训练产物 Run</div>
            <div style="font-size: 13px; font-family: monospace; color: #1f2328; word-break: break-all;">{{ trainingRunId }}</div>
            <button
              class="gh-btn"
              style="margin-top: 8px; font-size: 12px;"
              :disabled="!trainingRunIdRaw"
              @click="jumpToTrainingRun"
            >
              一键跳转到训练发布详情
            </button>
          </div>

          <div style="font-size: 12px; color: #656d76; margin-bottom: 8px;">{{ trainingSummaryText }}</div>
          <div v-if="trainingOverview?.need_publish" style="font-size: 12px; color: #0969da;">
            {{ trainingOverview.publish_hint }}
          </div>
          <div style="font-size: 12px; color: #0969da;">
            可进入 <router-link to="/training" class="gh-link">训练发布</router-link> 页面进行评审与发布。
          </div>
        </div>
      </div>

      <!-- 对比报告 -->
      <div v-if="comparisonReport" class="gh-panel" style="margin-bottom: 16px;">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">在线对比报告</span>
          <span class="gh-label gh-label-success">新提示词验证完成</span>
        </div>
        <div class="gh-panel-body">
          <!-- Memory disabled notice -->
          <div v-if="comparisonReport.memory_disabled" style="padding: 8px 12px; background: #fff8c5; border: 1px solid #d4a72c; border-radius: 6px; margin-bottom: 12px;">
            <div style="display: flex; align-items: start; gap: 8px;">
              <svg style="width: 16px; height: 16px; flex-shrink: 0; margin-top: 2px;" viewBox="0 0 16 16" fill="#9a6700">
                <path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"></path>
              </svg>
              <div style="flex: 1;">
                <div style="font-size: 12px; font-weight: 600; color: #9a6700; margin-bottom: 2px;">对比测试说明</div>
                <div style="font-size: 12px; color: #6f5f00;">
                  {{ comparisonReport.comparison_note || '对比测试时已禁用经验系统，纯粹测试新提示词效果' }}
                </div>
              </div>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
            <div class="gh-stat-card">
              <div class="gh-stat-label">测试任务数</div>
              <div class="gh-stat-value" style="font-size: 14px;">{{ comparisonReport.tasks_tested || 0 }}</div>
            </div>
            <div class="gh-stat-card">
              <div class="gh-stat-label">成功率对比</div>
              <div class="gh-stat-value" style="font-size: 14px;">
                <span :style="{ color: comparisonDelta.success_rate >= 0 ? '#1a7f37' : '#d1242f' }">
                  {{ formatPercent(comparisonReport.comparison?.success_rate?.old) }} →
                  {{ formatPercent(comparisonReport.comparison?.success_rate?.new) }}
                  ({{ comparisonDelta.success_rate >= 0 ? '+' : '' }}{{ formatPercent(comparisonDelta.success_rate) }})
                </span>
              </div>
            </div>
            <div class="gh-stat-card">
              <div class="gh-stat-label">平均工具调用</div>
              <div class="gh-stat-value" style="font-size: 14px;">
                <span :style="{ color: comparisonDelta.avg_tool_calls <= 0 ? '#1a7f37' : '#d1242f' }">
                  {{ formatNumber(comparisonReport.comparison?.avg_tool_calls?.old) }} →
                  {{ formatNumber(comparisonReport.comparison?.avg_tool_calls?.new) }}
                  ({{ comparisonDelta.avg_tool_calls <= 0 ? '' : '+' }}{{ formatNumber(comparisonDelta.avg_tool_calls) }})
                </span>
              </div>
            </div>
            <div class="gh-stat-card">
              <div class="gh-stat-label">改进任务数</div>
              <div class="gh-stat-value" style="font-size: 14px; color: #1a7f37;">
                {{ comparisonImprovedCount }}
              </div>
            </div>
          </div>

          <div style="margin-bottom: 12px;">
            <div style="font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 6px;">错误类型对比</div>
            <div style="display: grid; gap: 6px;">
              <div
                v-for="(newCount, errorType) in comparisonReport.comparison?.error_distribution"
                :key="errorType"
                style="display: flex; justify-content: space-between; font-size: 12px; padding: 4px 8px; background: #f6f8fa; border-radius: 4px;"
              >
                <span style="color: #1f2328;">{{ errorType }}</span>
                <span>
                  <span style="color: #656d76;">旧: {{ newCount.old || 0 }}</span>
                  <span style="margin: 0 8px;">→</span>
                  <span :style="{ color: newCount.new < newCount.old ? '#1a7f37' : '#656d76' }">
                    新: {{ newCount.new || 0 }}
                  </span>
                </span>
              </div>
              <div v-if="!comparisonReport.comparison?.error_distribution || Object.keys(comparisonReport.comparison.error_distribution).length === 0" class="gh-empty" style="padding: 8px;">
                无错误类型数据
              </div>
            </div>
          </div>

          <details style="cursor: pointer;">
            <summary style="font-size: 13px; font-weight: 600; color: #1f2328; padding: 8px 0;">任务详情（{{ comparisonReport.task_details?.length || 0 }} 个）</summary>
            <div style="max-height: 300px; overflow: auto; margin-top: 8px;">
              <table class="gh-table">
                <thead>
                  <tr>
                    <th style="width: 50px;">#</th>
                    <th style="min-width: 200px;">任务</th>
                    <th style="width: 100px;">旧状态</th>
                    <th style="width: 100px;">新状态</th>
                    <th style="width: 80px;">改进</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(task, idx) in comparisonReport.task_details" :key="idx">
                    <td>{{ idx + 1 }}</td>
                    <td style="font-size: 12px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="task.task_msg">
                      {{ task.task_msg }}
                    </td>
                    <td>
                      <span class="gh-label" :class="task.old_status === 'succeeded' ? 'gh-label-success' : 'gh-label-danger'">
                        {{ task.old_status }}
                      </span>
                    </td>
                    <td>
                      <span class="gh-label" :class="task.new_status === 'succeeded' ? 'gh-label-success' : 'gh-label-danger'">
                        {{ task.new_status }}
                      </span>
                    </td>
                    <td>
                      <span v-if="task.improvement" style="color: #1a7f37; font-size: 16px;">✓</span>
                      <span v-else-if="task.old_status === 'succeeded' && task.new_status === 'failed'" style="color: #d1242f; font-size: 16px;">✗</span>
                      <span v-else style="color: #656d76;">-</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </div>
      </div>

      <div class="gh-panel">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">任务结果</span>
        </div>
        <div class="gh-panel-body" style="padding: 0;">
          <div style="max-height: 300px; overflow: auto;">
            <table class="gh-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>状态</th>
                  <th>任务名称</th>
                  <th>用户</th>
                  <th>任务ID</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in (jobDetail?.task_results || [])" :key="`${row.index}-${row.rollout_id}`">
                  <td>{{ row.index }}</td>
                  <td>{{ row.status }}</td>
                  <td style="max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="row.message || ''">{{ row.message || "-" }}</td>
                  <td style="font-family: monospace;">{{ row.rollout_id || "-" }}</td>
                </tr>
                <tr v-if="!(jobDetail?.task_results || []).length">
                  <td colspan="4" class="gh-empty">暂无任务明细</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- ===================== TAB: 运行日志 ===================== -->
    <section v-show="tab === 'logs'">
      <h2 class="gh-heading">执行日志</h2>

      <div class="gh-panel">
        <div class="gh-panel-header">
          <span class="gh-panel-header-title">日志输出</span>
          <span class="gh-panel-header-sub">总日志：{{ jobDetail?.log_total ?? 0 }}</span>
        </div>
        <div class="gh-panel-body" style="padding: 0;">
          <pre class="gh-code" style="min-height: 400px; max-height: 600px; overflow: auto; margin: 0; white-space: pre-wrap; background: #0d1117; color: #c9d1d9; border: none; border-radius: 0;">{{ logsText }}</pre>
        </div>
      </div>
    </section>

    <!-- ===================== TAB: 历史任务 ===================== -->
    <section v-show="tab === 'history'">
      <h2 class="gh-heading">历史 Job</h2>

      <div class="gh-panel">
        <div class="gh-panel-body" style="padding: 0;">
          <div style="overflow: auto;">
            <table class="gh-table">
              <thead>
                <tr>
                  <th>job_id</th>
                  <th>状态</th>
                  <th>阶段</th>
                  <th>任务名称</th>
                  <th>用户</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in jobs" :key="job.job_id">
                  <td style="font-family: monospace;">{{ job.job_id }}</td>
                  <td>{{ job.status }}</td>
                  <td>{{ job.stage }}</td>
                  <td>{{ job.label || "-" }}</td>
                  <td>{{ job.username || "-" }}</td>
                  <td>
                    <button class="gh-link" style="cursor: pointer; border: none; background: none; padding: 0;" @click="selectJob(job.job_id)">查看</button>
                  </td>
                </tr>
                <tr v-if="!jobs.length">
                  <td colspan="6" class="gh-empty">暂无历史任务</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  </SettingsLayout>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { fetchJson, postJson } from "../services/api";
import SettingsLayout from "../components/SettingsLayout.vue";

const router = useRouter();
const tab = ref("sampling");

const _i = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;
const sidebarGroups = computed(() => [
  {
    label: "",
    items: [
      { id: "sampling", label: "训练任务", icon: _i("M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z") },
      { id: "control", label: "运行结果", icon: _i("M22 12h-4l-3 9L9 3l-3 9H2") },
      { id: "logs", label: "运行日志", icon: _i("M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 3H20v14H6.5A2.5 2.5 0 0 1 4 14.5V5.5A2.5 2.5 0 0 1 6.5 3Z") },
      { id: "history", label: "历史任务", icon: _i("M12 8v5l3 2M12 3a9 9 0 1 0 9 9") },
    ],
  },
]);

const tasksText = ref(`{
  "tasks": [
    { "msg": "【设备清单】使用以下设备：换热器 Heater、反应器 RStoic、精馏塔 RadFrac\\n【流程连接】进料 → 换热器 → 反应器 → 精馏塔 → 产品\\n【进料1条件】温度：25℃，压力：0.1MPa，组分：纯乙苯:4815kg/h\\n【进料2条件】温度：25℃，压力：0.1MPa，组分：纯水:327kg/h\\n【操作参数】换热器：将乙苯加热至反应温度；反应器：乙苯催化脱氢反应，转化率按工业数据；精馏塔：分离苯乙烯与未反应乙苯\\n【物性方法】PENG-ROB\\n【期望结果】产品苯乙烯纯度≥0.972" },
    { "msg": "【设备清单】使用以下设备：分离器 Sep2（DIST1）、分离器 Sep2（DIST2）、分离器 Sep（DECANT分相器）\\n【流程连接】进料FEED1+FEED2 → 精馏塔DIST1 → 分相器DECANT → 精馏塔DIST2 → 产品（塔底高纯乙醇）\\n【进料1条件】压力：0.1MPa，饱和液体，组分：乙醇:10kmol/h，水:225kmol/h\\n【进料2条件】压力：0.1MPa，饱和液体，组分：纯环己烷:0.005kmol/h\\n【操作参数】DIST1：共沸精馏塔，塔顶共沸物送分相器；DECANT：液液分相，有机相回流DIST1，水相送DIST2；DIST2：回收塔，塔底得高纯乙醇\\n【物性方法】NRTL\\n【期望结果】塔底乙醇纯度≥99.5mol%" },
    { "msg": "【设备清单】使用以下设备：精馏塔 RadFrac（T1轻端切割塔）、精馏塔 RadFrac（T2中轻端切割塔）、精馏塔 RadFrac（T3重端精分塔）\\n【流程连接】进料 → T1精馏塔 → T2精馏塔 → T3精馏塔 → 产品（四个纯组分）\\n【进料条件】温度：100℃，压力：1.2bar，液相进料，总流量：100kmol/h，组分：n-己烷(nC6):0.25摩尔分数，n-辛烷(nC8):0.25摩尔分数，n-癸烷(nC10):0.25摩尔分数，n-十二烷(nC12):0.25摩尔分数\\n【操作参数】T1：塔顶分出nC6，塔底为nC8+nC10+nC12送入T2；T2：塔顶分出nC8，塔底为nC10+nC12送入T3；T3：塔顶分出nC10，塔底得到nC12\\n【物性方法】PENG-ROB\\n【期望结果】四个塔顶/塔底产品分别得到高纯nC6、nC8、nC10、nC12" },
    { "msg": "【设备清单】使用以下设备：反应器 RStoic（REACTOR）、换热器 Heater（COOLER冷凝器）、分离器 Sep（SEP）\\n【流程连接】进料 → 反应器 → 冷凝器 → 分离器 → 产品（底部），分离器顶部物流循环回反应器\\n【进料条件】组分：苯(BENZENE)和丙烯(PROPENE)的混合物流\\n【操作参数】反应器：苯与丙烯反应生成异丙苯(PRO-BEN)；冷凝器：冷凝反应后混合物；分离器：顶部未反应物料(RECYCLE)循环回反应器，底部为产品(PRODUCT)\\n【物性方法】RK-SOAVE\\n【期望结果】求产品(PRODUCT)中异丙苯的摩尔流量" }
  ]
}`);
const historyStatus = ref("");
const historyQuery = ref("");
const historyTasks = ref([]);
const selectedHistoryTaskIds = ref([]);
const resetDb = ref(false);
const runTraining = ref(true);
const trainingMode = ref("offline");
const onlineIterations = ref(3);
const collectionBackend = ref("internal");
const maxTasks = ref(3);
const taskName = ref("");

const jobs = ref([]);
const currentJobId = ref("");
const jobDetail = ref(null);
const comparisonReport = ref(null);
const logOffset = ref(0);
const logs = ref([]);
const starting = ref(false);
const stopping = ref(false);
const stopNotice = ref("");
const stopNoticeType = ref("info");
const startSuccessNotice = ref("");
let pollTimer = null;

function extractTasksFromJson(input) {
  const raw = String(input || "").trim();
  if (!raw) {
    return { tasks: [], error: "任务输入不能为空" };
  }

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    return { tasks: [], error: `JSON格式错误: ${err.message || err}` };
  }

  const tasks = [];
  const appendTask = (item) => {
    if (typeof item === "string" && item.trim()) {
      tasks.push(item.trim());
      return;
    }
    if (item && typeof item === "object") {
      const msg = String(item.msg || item.message || "").trim();
      if (msg) tasks.push(msg);
    }
  };

  if (Array.isArray(parsed)) {
    parsed.forEach(appendTask);
  } else if (parsed && typeof parsed === "object") {
    if (Array.isArray(parsed.tasks)) {
      parsed.tasks.forEach(appendTask);
    } else if (parsed.msg || parsed.message) {
      appendTask(parsed);
    } else {
      Object.values(parsed).forEach(appendTask);
    }
  }

  if (!tasks.length) {
    return { tasks: [], error: "未解析到有效任务，请使用 tasks/msg 格式" };
  }
  return { tasks, error: "" };
}

const taskParseResult = computed(() => extractTasksFromJson(tasksText.value));
const parsedTasks = computed(() => taskParseResult.value.tasks);
const taskInputError = computed(() => taskParseResult.value.error);

const effectiveTasks = computed(() => {
  return parsedTasks.value;
});

const isRunning = computed(() => {
  const status = String(jobDetail.value?.status || "");
  return status === "queued" || status === "running" || status === "stopping";
});

const summaryText = computed(() => {
  const summary = jobDetail.value?.summary;
  if (!summary) return "-";
  return `总计 ${summary.task_total ?? 0}，成功 ${summary.succeeded ?? 0}，失败 ${summary.failed ?? 0}`;
});

const trainingRunId = computed(() => {
  return (
    jobDetail.value?.summary?.training_run_id ||
    jobDetail.value?.training_result?.run_id ||
    "-"
  );
});

const trainingRunIdRaw = computed(() => {
  const value =
    jobDetail.value?.summary?.training_run_id ||
    jobDetail.value?.training_result?.run_id ||
    "";
  return String(value || "").trim();
});

const trainingOverview = computed(
  () => jobDetail.value?.summary?.training_overview || null
);

const trainingSummaryText = computed(() => {
  const text = String(trainingOverview.value?.summary || "").trim();
  return text || "本次训练结果说明暂不可用。";
});

const logsText = computed(() =>
  logs.value.map((item) => `[${item.ts}] [${item.level}] ${item.message}`).join("\n")
);

const comparisonDelta = computed(() => {
  const comp = comparisonReport.value?.comparison;
  if (!comp) return { success_rate: 0, avg_tool_calls: 0 };
  return {
    success_rate: (comp.success_rate?.new || 0) - (comp.success_rate?.old || 0),
    avg_tool_calls: (comp.avg_tool_calls?.new || 0) - (comp.avg_tool_calls?.old || 0),
  };
});

const comparisonImprovedCount = computed(() => {
  const details = comparisonReport.value?.task_details;
  if (!Array.isArray(details)) return 0;
  return details.filter(t => t.improvement).length;
});

function formatPercent(val) {
  if (val == null) return "-";
  return (val * 100).toFixed(1) + "%";
}

function formatNumber(val) {
  if (val == null) return "-";
  return Number(val).toFixed(2);
}

const RL_LAB_STATE_KEY = "aspen_rl_lab_state_v1";

function persistRlLabState() {
  try {
    const payload = {
      tasksText: tasksText.value,
      historyStatus: historyStatus.value,
      historyQuery: historyQuery.value,
      selectedHistoryTaskIds: selectedHistoryTaskIds.value,
      resetDb: resetDb.value,
      runTraining: runTraining.value,
      trainingMode: trainingMode.value,
      onlineIterations: onlineIterations.value,
      collectionBackend: collectionBackend.value,
      maxTasks: maxTasks.value,
      taskName: taskName.value,
      jobs: jobs.value,
      currentJobId: currentJobId.value,
      jobDetail: jobDetail.value,
      logOffset: logOffset.value,
      logs: logs.value,
      historyTasks: historyTasks.value,
    };
    sessionStorage.setItem(RL_LAB_STATE_KEY, JSON.stringify(payload));
  } catch (err) {
    console.warn("persist rl lab state failed", err);
  }
}

function restoreRlLabState() {
  try {
    const raw = sessionStorage.getItem(RL_LAB_STATE_KEY);
    if (!raw) return false;
    const data = JSON.parse(raw);
    tasksText.value = data.tasksText ?? tasksText.value;
    historyStatus.value = data.historyStatus ?? historyStatus.value;
    historyQuery.value = data.historyQuery ?? historyQuery.value;
    selectedHistoryTaskIds.value = Array.isArray(data.selectedHistoryTaskIds) ? data.selectedHistoryTaskIds : [];
    resetDb.value = Boolean(data.resetDb);
    runTraining.value = data.runTraining !== false;
    trainingMode.value = data.trainingMode ?? trainingMode.value;
    onlineIterations.value = Number(data.onlineIterations ?? onlineIterations.value);
    collectionBackend.value = data.collectionBackend || collectionBackend.value;
    maxTasks.value = Number(data.maxTasks ?? maxTasks.value);
    taskName.value = data.taskName ?? "";
    jobs.value = Array.isArray(data.jobs) ? data.jobs : jobs.value;
    currentJobId.value = data.currentJobId || "";
    jobDetail.value = data.jobDetail ?? null;
    logOffset.value = Number(data.logOffset ?? 0);
    logs.value = Array.isArray(data.logs) ? data.logs : [];
    historyTasks.value = Array.isArray(data.historyTasks) ? data.historyTasks : [];
    return true;
  } catch (err) {
    console.warn("restore rl lab state failed", err);
    return false;
  }
}

function deriveTaskNameFromTasks(tasks) {
  const first = String((tasks || [])[0] || "").replace(/\s+/g, " ").trim();
  if (!first) return "";
  return first.slice(0, 24);
}

const jobTaskName = computed(() => {
  return String(
    jobDetail.value?.label ||
    jobDetail.value?.config?.label ||
    taskName.value ||
    "-"
  );
});

async function refreshJobs() {
  const data = await fetchJson("/api/rl/jobs?limit=30");
  jobs.value = data.jobs || [];
}

async function refreshTaskHistory() {
  const params = new URLSearchParams();
  params.set("limit", "500");
  if (historyStatus.value) params.set("status", historyStatus.value);
  if (historyQuery.value) params.set("q", historyQuery.value);
  const data = await fetchJson(`/api/rl/task-history?${params.toString()}`);
  historyTasks.value = Array.isArray(data.items) ? data.items : [];
  const valid = new Set(historyTasks.value.map((x) => x.task_id));
  selectedHistoryTaskIds.value = selectedHistoryTaskIds.value.filter((id) => valid.has(id));
}

async function fetchJobDetail(jobId) {
  try {
    const data = await fetchJson(`/api/rl/jobs/${jobId}?log_offset=${logOffset.value}`);
    jobDetail.value = data;
    currentJobId.value = jobId;
    if (Array.isArray(data.logs) && data.logs.length) {
      logs.value = logs.value.concat(data.logs);
    }
    logOffset.value = Number(data.next_log_offset || logOffset.value);

    // Load comparison report if available
    const compReport = data.summary?.training_overview?.comparison_report;
    if (compReport) {
      comparisonReport.value = compReport;
    }
  } catch (err) {
    if (String(err.message || "").includes("404")) {
      // Job no longer exists, clear stale state
      currentJobId.value = "";
      jobDetail.value = null;
      logs.value = [];
      logOffset.value = 0;
    }
  }
}

function resetCurrentView(jobId) {
  currentJobId.value = jobId;
  jobDetail.value = null;
  comparisonReport.value = null;
  logs.value = [];
  logOffset.value = 0;
}

async function startJob() {
  if (taskInputError.value) {
    alert(taskInputError.value);
    return;
  }
  if (!effectiveTasks.value.length) return;
  const resolvedTaskName = String(taskName.value || "").trim() || deriveTaskNameFromTasks(effectiveTasks.value);
  taskName.value = resolvedTaskName;
  stopNotice.value = "";
  stopNoticeType.value = "info";
  startSuccessNotice.value = "";
  starting.value = true;
  try {
    const data = await postJson("/api/rl/jobs/start", {
      tasks: effectiveTasks.value,
      max_tasks: maxTasks.value,
      reset_db: false,
      run_training: true,
      training_mode: trainingMode.value,
      online_iterations: onlineIterations.value,
      train_algo: "rgo",
      collection_backend: collectionBackend.value,
      label: resolvedTaskName,
    });
    resetCurrentView(data.job_id);
    await fetchJobDetail(data.job_id);
    await refreshJobs();
    startSuccessNotice.value = `任务启动成功！Job ID: ${data.job_id}`;
    setTimeout(() => { startSuccessNotice.value = ""; }, 8000);
  } catch (err) {
    alert(`启动失败: ${err.message || err}`);
  } finally {
    starting.value = false;
  }
}

async function stopJob() {
  if (!currentJobId.value) return;
  stopping.value = true;
  stopNotice.value = "正在发送停止请求...";
  stopNoticeType.value = "info";
  try {
    const res = await postJson(`/api/rl/jobs/${currentJobId.value}/stop`, {});
    if (res?.status === "stopping") {
      if (jobDetail.value) {
        jobDetail.value = {
          ...jobDetail.value,
          status: "stopping",
          stage: "stopping",
        };
      }
      stopNotice.value = "已提交停止请求，正在停止采样/训练任务...";
      await fetchJobDetail(currentJobId.value);
      await refreshJobs();
    } else {
      stopNotice.value = "停止请求已发送，等待任务状态刷新";
    }
  } catch (err) {
    if (String(err.message || "").includes("404")) {
      // Job no longer exists, clear stale state
      stopNotice.value = "任务已结束（不存在），已清除状态";
      stopNoticeType.value = "info";
      currentJobId.value = "";
      jobDetail.value = null;
      logs.value = [];
      logOffset.value = 0;
      await refreshJobs();
    } else {
      stopNotice.value = `停止失败: ${err.message || err}`;
      stopNoticeType.value = "error";
    }
  } finally {
    stopping.value = false;
  }
}

function jumpToTrainingRun() {
  if (!trainingRunIdRaw.value) return;
  router.push({
    path: "/training",
    query: { run_id: trainingRunIdRaw.value },
  });
}

async function selectJob(jobId) {
  resetCurrentView(jobId);
  await fetchJobDetail(jobId);
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    try {
      await refreshJobs();
      if (currentJobId.value) {
        await fetchJobDetail(currentJobId.value);
      }
    } catch (err) {
      console.error(err);
    }
  }, 2000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

watch(
  [
    tasksText,
    historyStatus,
    historyQuery,
    selectedHistoryTaskIds,
    resetDb,
    runTraining,
    trainingMode,
    collectionBackend,
    maxTasks,
    taskName,
    jobs,
    currentJobId,
    jobDetail,
    logOffset,
    logs,
    historyTasks,
  ],
  () => persistRlLabState(),
  { deep: true }
);

watch(
  () => jobDetail.value?.status,
  (status) => {
    const s = String(status || "").toLowerCase();
    if (!s) return;
    if (s === "stopping") {
      stopNotice.value = "停止中：正在安全终止采样/训练流程...";
      stopNoticeType.value = "info";
      return;
    }
    if (s === "stopped") {
      stopNotice.value = "任务已停止";
      stopNoticeType.value = "info";
      return;
    }
    if (s === "failed") {
      if (stopNotice.value) {
        stopNotice.value = "任务已结束（失败）";
        stopNoticeType.value = "error";
      }
      return;
    }
    if (s === "completed") {
      if (stopNotice.value) {
        stopNotice.value = "任务已完成";
        stopNoticeType.value = "info";
      }
    }
  }
);

onMounted(async () => {
  restoreRlLabState();
  await refreshJobs();
  await refreshTaskHistory();
  if (currentJobId.value) {
    await fetchJobDetail(currentJobId.value);
  } else if (jobs.value.length > 0) {
    const firstId = jobs.value[0].job_id;
    await selectJob(firstId);
  }
  startPolling();
  persistRlLabState();
});

onBeforeUnmount(() => {
  persistRlLabState();
  stopPolling();
});
</script>


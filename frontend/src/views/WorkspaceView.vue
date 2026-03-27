<template>
  <div class="flex h-full bg-[radial-gradient(circle_at_top,#f8fafc_0%,#eef3ff_45%,#f1f5f9_100%)] text-gray-800 font-sans overflow-hidden">
    <!-- 左侧菜单栏 - 可拖拽调整宽度 -->
    <SessionSidebar
      :chat-sessions="chatSessions"
      :active-session-id="activeSessionId"
      :is-collapsed="isSidebarCollapsed"
      :sidebar-width="sidebarWidth"
      @create-session="createNewSession"
      @switch-session="switchSession"
      @delete-session="deleteSession"
      @toggle-sidebar="toggleSidebar"
      @update:sidebar-width="(v) => (sidebarWidth = v)"
    />

    <!-- 右侧主区域 -->
    <main class="flex-1 flex flex-col min-w-0 h-full">
      <div class="flex-1 flex flex-col p-4 overflow-hidden">
        <section ref="chatBox" class="flex-1 overflow-y-auto custom-scrollbar px-4 py-3 rounded-2xl">
          <MessageFeed
            :messages="messages"
            :loading="loading"
            :render-markdown="renderMarkdown"
            @toggle-collapse="toggleCollapse"
            @download-file="downloadFile"
          />
        </section>

        <PromptComposer
          v-model="userInput"
          :loading="loading"
          :placeholder="getPlaceholder()"
          :messages-length="messages.length"
          :active-menu="activeMenu"
          :selected-category="selectedCategory"
          :selected-equipment="selectedEquipment"
          :selected-process-example="selectedProcessExample"
          :category-names="categoryNames"
          :process-example-names="processExampleNames"
          :equipment-options="currentEquipmentOptions()"
          @select-menu="selectMenu"
          @category-change="onCategoryChange"
          @update:selected-category="(v) => (selectedCategory = v)"
          @update:selected-equipment="(v) => (selectedEquipment = v)"
          @update:selected-process-example="(v) => (selectedProcessExample = v)"
          @send="sendMessage"
          @stop="stopMessage"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onUnmounted, onActivated, onDeactivated, watch } from 'vue';
import { useRouter } from 'vue-router';
import SessionSidebar from '../components/workspace/SessionSidebar.vue';
import MessageFeed from '../components/workspace/MessageFeed.vue';
import PromptComposer from '../components/workspace/PromptComposer.vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { getUser, getToken } from '../services/auth';
import { fetchJson, postJson, deleteJson } from '../services/api';
defineOptions({ name: "WorkspaceView" });
const router = useRouter();

// --- 静态数据 (设备配置) ---
const categoryNames = {
  simple: '常规单元',
  heat: '热交换',
  transport: '流体输送',
  tower: '塔设备',
  reactor: '反应器'
};

// 获取类别图标
// 获取流程示例图标
const equipmentData = {
  simple: [
    { id: 'mixer', name: '混合器 Mixer' },
    { id: 'sep', name: '分离器 Sep' },
    { id: 'sep2', name: '分离器 Sep2' },
    { id: 'flash', name: '闪蒸罐 Flash' },
    { id: 'flash3', name: '三相闪蒸 Flash3' },
    { id: 'decanter', name: '倾析器 Decanter' },
    { id: 'fsplit', name: '分流器 FSplit' },
    { id: 'valve', name: '阀门 Valve' }
  ],
  heat: [
    { id: 'heater', name: '换热器 Heater' },
    { id: 'heatx', name: '换热器 HeatX' }
  ],
  transport: [
    { id: 'pump', name: '离心泵 Pump' },
    { id: 'compr', name: '压缩机 Compr' },
    { id: 'mcompr', name: '多级压缩机 MCompr' }
  ],
  tower: [
    { id: 'radfrac', name: '精馏塔 RadFrac' },
    { id: 'distl', name: '精馏塔 Distl' },
    { id: 'dstwu', name: '精馏塔设计 DSTWU' },
    { id: 'dupl', name: '塔器 Dupl' },
    { id: 'extract', name: '萃取塔 Extract' }
  ],
  reactor: [
    { id: 'rstoic', name: '反应器 RStoic' },
    { id: 'rplug', name: '反应器 RPlug' },
    { id: 'rcstr', name: '反应器 RCSTR' }
  ]
};

const equipmentPrompts = {
  'mixer': `【设备清单】使用设备：混合器 Mixer
【进料1条件】温度：100℃，压力：2MPa，组分（kmol/h）：丙烷(C3):10，正丁烷(NC4):15，正戊烷(NC5):15，正己烷(NC6):10
【进料2条件】温度：120℃，压力：2.5MPa，组分（kmol/h）：丙烷(C3):15，正丁烷(NC4):15，正戊烷(NC5):10，正己烷(NC6):10
【进料3条件】温度：100℃，气相分数：0.5，组分（kmol/h）：丙烷(C3):25，正丁烷(NC4):0，正戊烷(NC5):15，正己烷(NC6):10
【物性方法】CHAO-SEA
【期望结果】计算混合后产品物流的温度、压力及各组分流量`,

  'sep': `【设备清单】使用设备：分离器 Sep
【进料条件】温度：70℃，压力：0.1MPa，组分（kmol/h）：甲醇:50，水:100，乙醇:150
【操作参数】分离器：顶部产品流量50kmol/h，甲醇摩尔分数0.95，乙醇摩尔分数0.04
【物性方法】UNIQUAC
【期望结果】计算分离器底部产品的流量与组成`,

  'flash': `【设备清单】使用设备：闪蒸罐 Flash（2台串联）
【流程连接】进料 → 闪蒸罐1 → 闪蒸罐2（液相进入） → 产品
【进料条件】温度：100℃，压力：3.8MPa，组分（kmol/h）：氢气:185，甲烷:45，苯:45，甲苯:5
【操作参数】闪蒸罐1：温度100℃，压降0；闪蒸罐2：绝热闪蒸，压力0.1MPa
【物性方法】PENG-ROB
【期望结果】计算第二个闪蒸器的温度`,

  'flash3': `【设备清单】使用设备：三相闪蒸罐 Flash3
【进料条件】温度、压力、流量、组成（请填写具体数值）
【操作参数】闪蒸操作条件（温度、压力或热负荷）
【物性方法】NRTL
【期望结果】计算汽相、第一液相和第二液相三相产物的流量与组成`,

  'heater': `【设备清单】使用设备：换热器 Heater
【进料条件】温度：25℃，压力：0.4MPa，流量：5000kg/h，组分：纯软水
【操作参数】换热器：出口压力0.45MPa，加热至饱和蒸汽
【物性方法】IAPWS-95
【期望结果】求锅炉所需供热量及蒸汽温度`,

  'compr': `【设备清单】使用设备：压缩机 Compr
【进料条件】温度：100℃，压力：690kPa，组分（kmol/h）：甲烷:0.05，乙烷:0.45，丙烷:4.55，正丁烷:8.60，异丁烷:9.00，1,3-丁二烯:9.00
【操作参数】压缩机：多变压缩至3450kPa，多变效率80%，驱动机机械效率95%
【物性方法】PENG-ROB
【期望结果】计算产品物流温度和体积流量，压缩机指示功率、轴功率及损失功率`,

  'mcompr': `【设备清单】使用设备：多级压缩机 MCompr
【进料条件】温度、压力、流量、组成（请填写具体数值）
【操作参数】压缩级数、各级压缩比/出口压力、效率
【物性方法】PENG-ROB
【期望结果】计算各级出口物流的温度、压力与功率`,

  'pump': `【设备清单】使用设备：离心泵 Pump
【进料条件】温度：-10℃，压力：170kPa，组分（kmol/h）：甲烷:0.05，乙烷:0.45，丙烷:4.55，正丁烷:8.60，异丁烷:9.00，1,3-丁二烯:9.00
【操作参数】泵：升压至690kPa，泵效率80%，驱动机效率95%
【物性方法】PENG-ROB
【期望结果】计算泵的有效功率、轴功率及驱动机消耗电功率`,

  'rstoic': `【设备清单】使用设备：反应器 RStoic
【进料条件】温度：180℃，压力：0.18MPa，组分：甲醇(CH3OH):8000kg/h，水蒸气(H2O):3000kg/h
【操作参数】反应器：温度475℃，压力0.15MPa，反应及转化率如下：
R1：2CH₃OH → C₂H₄ + 2H₂O，转化率0.25
R2：3CH₃OH → C₃H₆ + 3H₂O，转化率0.20
R3：4CH₃OH → C₄H₈ + 4H₂O，转化率0.08
R4：CH₃OH → CO + 2H₂，转化率0.02
R5：CH₃OH → C + H₂O + H₂，转化率0.005
【物性方法】RK-SOAVE
【期望结果】计算主要产物乙烯、丙烯(别名C3H6-2)等对甲醇的选择性`,

  'rcstr': `【设备清单】使用设备：反应器 RCSTR
【进料条件】温度：100℃，压力：0.5MPa，组分（kmol/h）：甲醇(CH3OH):100，水(H2O):50
【操作参数】反应器：温度150℃，压力0.5MPa，体积2m³，反应：CH₃OH + H₂O → CO₂ + 3H₂，使用动力学反应模型
【物性方法】NRTL
【期望结果】计算反应器出口物流的组成和流量`,

  'radfrac': `【设备清单】使用设备：精馏塔 RadFrac
【进料条件】流量：12500kg/h，温度：45℃，压力：101.325kPa，组分（质量分数）：乙苯(CAS:100-41-4,name:C8H10-4):0.5843，苯乙烯(CAS:100-42-5):0.415，焦油(CAS:629-78-7,name:C17H36):0.0007
【操作参数】精馏塔：塔顶全凝器压力6kPa，再沸器压力14kPa，回流比为最小回流比的1.2倍，塔顶乙苯摩尔回收率99.91%，塔底苯乙烯摩尔回收率98.58%
【物性方法】PENG-ROB
【期望结果】塔顶乙苯纯度≥0.99，塔底苯乙烯纯度≥0.997
【补充说明】使用精馏塔进行严格计算`,

  'distl': `【设备清单】使用设备：精馏塔 Distl
【进料条件】温度、压力、总流量及组成（请填写具体数值）
【操作参数】精馏塔：塔板数、回流比/馏出与进料比
【物性方法】NRTL
【期望结果】计算塔顶与塔底产品的流量与组成`,

  'dupl': `【设备清单】使用设备：塔器 Dupl
【进料条件】温度、压力、流量与组成（请填写具体数值）
【操作参数】塔板数、回流/再沸等关键操作参数
【物性方法】NRTL
【期望结果】计算塔器产品的流量与组成`,

  'extract': `【设备清单】使用设备：萃取塔 Extract
【进料条件】进料/溶剂各股物流的温度、压力、总流量与组成（请填写具体数值）
【操作参数】萃取塔：塔板数、操作方式（温度/负荷规范）
【物性方法】NRTL
【期望结果】计算萃取产品的流量与组成`,

  'fsplit': `【设备清单】使用设备：分流器 FSplit
【进料条件】温度、压力、流量、组成（请填写具体数值）
【操作参数】分流器：各出口分流分率或分流方式
【物性方法】NRTL
【期望结果】计算各出口物流的流量与组成`,

  'valve': `【设备清单】使用设备：阀门 Valve
【进料条件】温度、压力、流量、组成（请填写具体数值）
【操作参数】阀门：出口压力或压降
【物性方法】PENG-ROB
【期望结果】计算出口物流的温度、压力与流量`,

  'decanter': `【设备清单】使用设备：倾析器 Decanter
【进料条件】温度、压力、流量、组成（请填写具体数值）
【操作参数】倾析器：操作温度或压力
【物性方法】NRTL
【期望结果】计算两相产物的流量与组成`,

  'sep2': `【设备清单】使用设备：分离器 Sep2
【进料条件】温度、压力、流量、组成（请填写具体数值）
【操作参数】分离器：各产品的分离要求（流量、组成等）
【物性方法】NRTL
【期望结果】计算各出口产品的流量与组成`,

  'heatx': `【设备清单】使用设备：换热器 HeatX
【进料1条件】热物流：温度、压力、流量、组成（请填写具体数值）
【进料2条件】冷物流：温度、压力、流量、组成（请填写具体数值）
【操作参数】换热器：热物流出口温度、冷物流出口温度或换热负荷
【物性方法】PENG-ROB
【期望结果】计算两股出口物流的温度、压力与流量`,

  'dstwu': `【设备清单】使用设备：精馏塔设计 DSTWU
【进料条件】温度、压力、流量、组成（请填写具体数值）
【操作参数】精馏塔设计：轻关键组分和重关键组分的回收率
【物性方法】NRTL
【期望结果】计算所需理论板数、最小回流比和进料板位置`,

  'rplug': `【设备清单】使用设备：反应器 RPlug
【进料条件】温度：100℃，压力：0.5MPa，组分（kmol/h）：甲醇(CH3OH):100，水(H2O):50
【操作参数】反应器：温度150℃，压力0.5MPa，体积2m³，反应：CH₃OH + H₂O → CO₂ + 3H₂，使用动力学反应模型
【物性方法】NRTL
【期望结果】计算反应器出口物流的组成和流量`
};

// 流程模拟示例（结构化格式）
const processExamples = {
  'ethylbenzene_styrene': `【设备清单】使用以下设备：换热器 Heater、反应器 RStoic、精馏塔 RadFrac
【流程连接】进料 → 换热器 → 反应器 → 精馏塔 → 产品
【进料1条件】温度：25℃，压力：0.1MPa，组分：纯乙苯:4815kg/h
【进料2条件】温度：25℃，压力：0.1MPa，组分：纯水:327kg/h
【操作参数】换热器：将进料预热至反应温度；反应器：乙苯催化脱氢反应，生成苯乙烯和氢气；精馏塔：分离苯乙烯与未反应乙苯
【物性方法】PENG-ROB
【期望结果】产品苯乙烯纯度≥0.972
【补充说明】优先使用RStoic反应器`,

  'azeotropic_ethanol_water': `【设备清单】使用以下设备：分离器 Sep2（DIST1）、分离器 Sep2（DIST2）、分离器 Sep（DECANT分相器）
【流程连接】进料FEED1+FEED2 → 精馏塔DIST1 → 分相器DECANT → 精馏塔DIST2 → 产品（塔底高纯乙醇）
【进料1条件】压力：0.1MPa，饱和液体，组分：乙醇:10kmol/h，水:225kmol/h
【进料2条件】压力：0.1MPa，饱和液体，组分：纯环己烷:0.005kmol/h
【操作参数】DIST1：各组分进入塔底分数 → 乙醇:0.01、水:0.97、环己烷:0.09；DIST2：各组分进入塔底分数 → 乙醇:0.97、水:0.0001、环己烷:0.0001；DECANT：各组分进入ORG物流分数 → 乙醇:0.98、水:0.01、环己烷:0.99
【物性方法】NRTL
【期望结果】计算精馏塔DIST2塔底物流中乙醇的纯度
【补充说明】以环己烷作共沸剂，塔和分相器操作压力均为0.1MPa，压降忽略，只做物料衡算`,

  'azeotropic_distillation': `【设备清单】使用以下设备：精馏塔 RadFrac（T1轻端切割塔）、精馏塔 RadFrac（T2中轻端切割塔）、精馏塔 RadFrac（T3重端精分塔）
【流程连接】进料 → T1精馏塔 → T2精馏塔 → T3精馏塔 → 产品（四个纯组分）
【进料条件】温度：100℃，压力：1.2bar，液相进料，总流量：100kmol/h，组分：n-己烷(nC6):0.25摩尔分数，n-辛烷(nC8):0.25摩尔分数，n-癸烷(nC10):0.25摩尔分数，n-十二烷(nC12):0.25摩尔分数
【操作参数】T1：塔顶分出nC6，塔底为nC8+nC10+nC12送入T2；T2：塔顶分出nC8，塔底为nC10+nC12送入T3；T3：塔顶分出nC10，塔底得到nC12
【物性方法】PENG-ROB
【期望结果】四个塔顶/塔底产品分别得到高纯nC6、nC8、nC10、nC12`,

  'benzene_ethylene': `【设备清单】使用以下设备：反应器 RStoic（REACTOR）、换热器 Heater（COOLER冷凝器）、分离器 Sep（SEP）
【流程连接】进料 → 反应器 → 冷凝器 → 分离器 → 产品（底部），分离器顶部物流循环回反应器
【进料条件】组分：苯(BENZENE)和丙烯(PROPENE)的混合物流
【操作参数】反应器：苯与丙烯反应生成异丙苯(PRO-BEN)；冷凝器：冷凝反应后混合物；分离器：顶部未反应物料(RECYCLE)循环回反应器，底部为产品(PRODUCT)
【物性方法】RK-SOAVE
【期望结果】求产品(PRODUCT)中异丙苯的摩尔流量`
};

const processExampleNames = {
  'ethylbenzene_styrene': '乙苯催化脱氢制苯乙烯',
  'azeotropic_ethanol_water': '共沸精馏分离乙醇-水',
  'azeotropic_distillation': '共沸精馏 - 分离精馏',
  'benzene_ethylene': '苯和乙烯反应生成异丙苯'
};

// --- 状态变量 ---
const userInput = ref('');
const messages = ref([]);
const loading = ref(false);
const wsConnected = ref(false);
const chatBox = ref(null);
const activeMenu = ref(''); // '', 'unit' 或 'process'
const selectedCategory = ref(null);
const selectedEquipment = ref(null);
const selectedProcessExample = ref(null);
const currentRolloutId = ref(null);
const isSidebarCollapsed = ref(false);

const createLocalSession = (overrides = {}) => ({
  id: `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
  title: '新对话',
  updatedAt: Date.now(),
  serverUpdatedAt: null,
  messages: [],
  ...overrides,
});

const chatSessions = ref([]);
const activeSessionId = ref('');
const workspaceInitialized = ref(false);

// 拖拽相关变量
const sidebarWidth = ref(256); // 初始宽度为256px (w-64)


const DEFAULT_SIDEBAR_WIDTH = 256;
const AUTH_EVENT_NAME = 'aspen:auth-changed';

const _getUserId = () => getUser()?.user_id || 'anonymous';
const _stateKeyForUser = (userId) => `aspen.workspace.state.v1.${userId || 'anonymous'}`;
const _layoutKeyForUser = (userId) => `aspen.workspace.layout.v1.${userId || 'anonymous'}`;
const _stateKey = () => _stateKeyForUser(_getUserId());
const _layoutKey = () => _layoutKeyForUser(_getUserId());
const currentWorkspaceUserId = ref(_getUserId());

const _toPlain = (v) => JSON.parse(JSON.stringify(v));
const _normalizeMessages = (messagesLike) => Array.isArray(messagesLike) ? _toPlain(messagesLike) : [];
const _sessionTitleFromMessages = (messagesLike) => {
  const firstUser = _normalizeMessages(messagesLike).find((m) => m.type === 'user');
  return firstUser?.content ? String(firstUser.content).slice(0, 24) : '新对话';
};
const _sessionApiBase = () => `${resolveApiBase()}/api/sessions`;
const _secondsFromMs = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  return numeric > 1e12 ? numeric / 1000 : numeric;
};
const _msFromSeconds = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return Date.now();
  return numeric > 1e12 ? numeric : numeric * 1000;
};

const buildSessionSnapshot = (session) => {
  const messagesSnapshot = _normalizeMessages(session?.messages);
  const updatedAt = Number(session?.updatedAt || Date.now());
  const rawServerUpdatedAt = session?.serverUpdatedAt;
  const serverUpdatedAt = rawServerUpdatedAt === null || rawServerUpdatedAt === undefined || rawServerUpdatedAt === ''
    ? null
    : Number(rawServerUpdatedAt);
  return {
    id: String(session?.id || '').trim(),
    title: String(session?.title || _sessionTitleFromMessages(messagesSnapshot) || '新对话'),
    updatedAt,
    serverUpdatedAt: Number.isFinite(serverUpdatedAt) && serverUpdatedAt > 0 ? serverUpdatedAt : null,
    messages: messagesSnapshot,
  };
};

const clearWorkspaceCacheForUser = (userId) => {
  if (!userId) return;
  try {
    sessionStorage.removeItem(_stateKeyForUser(userId));
    sessionStorage.removeItem(_layoutKeyForUser(userId));
  } catch (error) {
    console.warn('clear workspace cache failed:', error);
  }
};

const stopActiveStream = () => {
  if (sseAbortController) {
    try {
      sseAbortController.abort();
    } catch (error) {
      console.warn('abort active stream failed:', error);
    }
  }
  sseAbortController = null;
  loading.value = false;
  currentRolloutId.value = null;
};

const resetWorkspaceState = ({ clearCurrentCache = false } = {}) => {
  if (clearCurrentCache) {
    clearWorkspaceCacheForUser(currentWorkspaceUserId.value);
  }
  stopActiveStream();
  userInput.value = '';
  messages.value = [];
  chatSessions.value = [];
  activeSessionId.value = '';
  activeMenu.value = '';
  selectedCategory.value = null;
  selectedEquipment.value = null;
  selectedProcessExample.value = null;
  isSidebarCollapsed.value = false;
  sidebarWidth.value = DEFAULT_SIDEBAR_WIDTH;
  workspaceInitialized.value = false;
};

const adoptRemoteSession = (sessionId, sessionData, { replaceMessages = false } = {}) => {
  if (!sessionData || !sessionId) return null;
  const remoteMessages = _normalizeMessages(sessionData.messages);
  const updatedSession = upsertLocalSession({
    id: sessionId,
    title: sessionData.title || _sessionTitleFromMessages(remoteMessages) || '新对话',
    updatedAt: _msFromSeconds(sessionData.updated_at),
    serverUpdatedAt: _msFromSeconds(sessionData.updated_at),
    messages: remoteMessages,
  });
  if (replaceMessages && activeSessionId.value === sessionId) {
    messages.value = remoteMessages;
  }
  persistWorkspaceState();
  return updatedSession;
};

const ensureUserWorkspaceContext = async () => {
  const nextUserId = _getUserId();
  if (currentWorkspaceUserId.value === nextUserId && workspaceInitialized.value) {
    return false;
  }
  const previousUserId = currentWorkspaceUserId.value;
  if (previousUserId !== nextUserId) {
    clearWorkspaceCacheForUser(previousUserId);
  }
  currentWorkspaceUserId.value = nextUserId;
  resetWorkspaceState();
  return true;
};

const ensureFallbackSession = () => {
  if (chatSessions.value.length > 0) return;
  const session = createLocalSession();
  chatSessions.value = [session];
  activeSessionId.value = session.id;
  messages.value = [];
};

const persistWorkspaceState = () => {
  try {
    const payload = {
      version: 1,
      ts: Date.now(),
      userInput: userInput.value,
      messages: _toPlain(messages.value),
      loading: loading.value,
      activeMenu: activeMenu.value,
      selectedCategory: selectedCategory.value,
      selectedEquipment: selectedEquipment.value,
      selectedProcessExample: selectedProcessExample.value,
      currentRolloutId: currentRolloutId.value,
      isSidebarCollapsed: isSidebarCollapsed.value,
      sidebarWidth: sidebarWidth.value,
      chatSessions: _toPlain(chatSessions.value),
      activeSessionId: activeSessionId.value,
    };
    sessionStorage.setItem(_stateKey(), JSON.stringify(payload));
  } catch (e) {
    console.warn('persist workspace state failed:', e);
  }
};

const restoreWorkspaceState = () => {
  try {
    const raw = sessionStorage.getItem(_stateKey());
    if (!raw) return false;
    const st = JSON.parse(raw);
    if (!st || typeof st !== 'object') return false;

    if (Array.isArray(st.chatSessions) && st.chatSessions.length) {
      chatSessions.value = st.chatSessions.map((session) => buildSessionSnapshot(session));
    }
    if (typeof st.activeSessionId === 'string' && st.activeSessionId) {
      activeSessionId.value = st.activeSessionId;
    }
    if (Array.isArray(st.messages)) {
      messages.value = st.messages;
    }
    if (typeof st.userInput === 'string') userInput.value = st.userInput;
    if (typeof st.loading === 'boolean') loading.value = st.loading;
    if (typeof st.activeMenu === 'string') activeMenu.value = st.activeMenu;
    selectedCategory.value = st.selectedCategory ?? null;
    selectedEquipment.value = st.selectedEquipment ?? null;
    selectedProcessExample.value = st.selectedProcessExample ?? null;
    currentRolloutId.value = st.currentRolloutId ?? null;
    if (typeof st.isSidebarCollapsed === 'boolean') isSidebarCollapsed.value = st.isSidebarCollapsed;
    if (Number.isFinite(Number(st.sidebarWidth))) sidebarWidth.value = Number(st.sidebarWidth);
    return true;
  } catch (e) {
    console.warn('restore workspace state failed:', e);
    return false;
  }
};

const findSessionIndex = (sessionId) => chatSessions.value.findIndex((s) => s.id === sessionId);

const upsertLocalSession = (sessionLike) => {
  const session = buildSessionSnapshot(sessionLike);
  if (!session.id) return session;
  const idx = findSessionIndex(session.id);
  if (idx >= 0) {
    chatSessions.value[idx] = { ...chatSessions.value[idx], ...session };
  } else {
    chatSessions.value.unshift(session);
  }
  return session;
};

const saveSessionSnapshot = async (sessionId, payload) => {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${_sessionApiBase()}/${encodeURIComponent(sessionId)}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 409) {
    const conflict = new Error('SESSION_CONFLICT');
    conflict.code = 'SESSION_CONFLICT';
    conflict.session = data?.session || null;
    throw conflict;
  }
  if (!response.ok) {
    throw new Error(data?.detail || `HTTP ${response.status}`);
  }
  return data;
};

const handleSessionConflict = async (sessionId, conflictSession) => {
  const shouldOverwrite = window.confirm('当前会话已在另一台设备更新。点击“确定”用当前页面内容覆盖远端，点击“取消”加载远端最新内容。');
  if (shouldOverwrite) {
    return { shouldForce: true };
  }
  adoptRemoteSession(sessionId, conflictSession, { replaceMessages: true });
  return { aborted: true };
};

const persistSessionToServer = async (sessionId, { force = false } = {}) => {
  const idx = findSessionIndex(sessionId);
  if (idx < 0) return null;
  const session = buildSessionSnapshot(chatSessions.value[idx]);
  try {
    const data = await saveSessionSnapshot(sessionId, {
      title: session.title,
      messages: session.messages,
      base_updated_at: _secondsFromMs(session.serverUpdatedAt),
      force,
    });
    if (data?.session) {
      upsertLocalSession({
        ...session,
        title: data.session.title || session.title,
        updatedAt: _msFromSeconds(data.session.updated_at),
        serverUpdatedAt: _msFromSeconds(data.session.updated_at),
      });
      persistWorkspaceState();
    }
    return data;
  } catch (error) {
    if (error?.code === 'SESSION_CONFLICT') {
      const resolution = await handleSessionConflict(sessionId, error.session);
      if (resolution?.shouldForce) {
        return persistSessionToServer(sessionId, { force: true });
      }
      return { aborted: true, conflict: true };
    }
    throw error;
  }
};

const persistActiveSession = () => {
  const idx = findSessionIndex(activeSessionId.value);
  if (idx < 0) return null;
  const snapshot = _normalizeMessages(messages.value);
  const title = _sessionTitleFromMessages(snapshot);
  const updated = {
    ...chatSessions.value[idx],
    title,
    updatedAt: Date.now(),
    serverUpdatedAt: chatSessions.value[idx]?.serverUpdatedAt ?? null,
    messages: snapshot,
  };
  chatSessions.value[idx] = updated;
  persistWorkspaceState();
  return updated;
};

const seedRemoteSessionsFromLocalCache = async () => {
  const localSessions = _normalizeMessages(chatSessions.value)
    .filter((session) => Array.isArray(session.messages) && session.messages.length > 0)
    .map((session) => buildSessionSnapshot(session));
  for (const session of localSessions) {
    await postJson(`${_sessionApiBase()}/${encodeURIComponent(session.id)}`, {
      title: session.title,
      messages: session.messages,
    });
  }
};

const loadSessionMessages = async (sessionId, { preferLocal = true } = {}) => {
  const idx = findSessionIndex(sessionId);
  if (idx < 0) return;
  const localMessages = _normalizeMessages(chatSessions.value[idx].messages);
  if (preferLocal && localMessages.length > 0) {
    messages.value = localMessages;
  } else {
    messages.value = [];
  }
  try {
    const data = await fetchJson(`${_sessionApiBase()}/${encodeURIComponent(sessionId)}/messages`);
    const remoteMessages = _normalizeMessages(data?.messages);
    chatSessions.value[idx] = {
      ...chatSessions.value[idx],
      messages: remoteMessages,
      title: data?.title || _sessionTitleFromMessages(remoteMessages) || chatSessions.value[idx].title,
      updatedAt: _msFromSeconds(data?.updated_at),
      serverUpdatedAt: _msFromSeconds(data?.updated_at),
    };
    messages.value = remoteMessages;
  } catch (error) {
    console.warn('load session messages failed:', error);
    if (!preferLocal) {
      messages.value = localMessages;
    }
  }
};

const syncSessionsFromServer = async ({ restoreLocalIfEmpty = false } = {}) => {
  const localSessions = _normalizeMessages(chatSessions.value).map((session) => buildSessionSnapshot(session));
  const localById = new Map(localSessions.map((session) => [session.id, session]));

  let remoteRows = [];
  try {
    const data = await fetchJson(_sessionApiBase());
    remoteRows = Array.isArray(data?.sessions) ? data.sessions : [];
  } catch (error) {
    console.warn('load session list failed:', error);
    if (localSessions.length > 0) {
      chatSessions.value = localSessions;
      if (!activeSessionId.value) activeSessionId.value = localSessions[0].id;
      return;
    }
    ensureFallbackSession();
    return;
  }

  if (remoteRows.length === 0 && restoreLocalIfEmpty && localSessions.some((session) => session.messages.length > 0)) {
    await seedRemoteSessionsFromLocalCache();
    const seeded = await fetchJson(_sessionApiBase());
    remoteRows = Array.isArray(seeded?.sessions) ? seeded.sessions : [];
  }

  if (remoteRows.length === 0) {
    ensureFallbackSession();
    return;
  }

  chatSessions.value = remoteRows.map((row) => {
    const id = String(row.session_id || '').trim();
    const local = localById.get(id);
    return buildSessionSnapshot({
      id,
      title: row.title || local?.title || '新对话',
      updatedAt: Number(row.updated_at) ? Number(row.updated_at) * 1000 : (local?.updatedAt || Date.now()),
      serverUpdatedAt: Number(row.updated_at) ? Number(row.updated_at) * 1000 : (local?.serverUpdatedAt ?? null),
      messages: local?.messages || [],
    });
  });

  if (!activeSessionId.value || !chatSessions.value.some((session) => session.id === activeSessionId.value)) {
    activeSessionId.value = chatSessions.value[0]?.id || '';
  }

  if (activeSessionId.value) {
    await loadSessionMessages(activeSessionId.value, { preferLocal: true });
  } else {
    messages.value = [];
  }
};

const createNewSession = async () => {
  const session = createLocalSession();
  chatSessions.value.unshift(session);
  activeSessionId.value = session.id;
  messages.value = [];
  userInput.value = '';
  persistWorkspaceState();
  try {
    await persistSessionToServer(session.id);
  } catch (error) {
    console.warn('create session failed:', error);
  }
};

const switchSession = async (sessionId) => {
  const idx = findSessionIndex(sessionId);
  if (idx < 0) return;
  activeSessionId.value = sessionId;
  const snapshot = _normalizeMessages(chatSessions.value[idx].messages);
  messages.value = snapshot;
  await loadSessionMessages(sessionId, { preferLocal: true });
  nextTick(scrollToBottom);
  persistWorkspaceState();
};

const deleteSession = async (sessionId) => {
  const idx = findSessionIndex(sessionId);
  if (idx < 0) return;

  let nextSessionId = '';
  if (activeSessionId.value === sessionId) {
    const nextIdx = idx < chatSessions.value.length - 1 ? idx + 1 : idx - 1;
    if (nextIdx >= 0 && chatSessions.value[nextIdx]) {
      nextSessionId = chatSessions.value[nextIdx].id;
    }
  }

  chatSessions.value.splice(idx, 1);
  try {
    await deleteJson(`${_sessionApiBase()}/${encodeURIComponent(sessionId)}`);
  } catch (error) {
    console.warn('delete session failed:', error);
  }

  if (chatSessions.value.length === 0) {
    await createNewSession();
  } else {
    activeSessionId.value = nextSessionId || chatSessions.value[0].id;
    await loadSessionMessages(activeSessionId.value, { preferLocal: true });
  }

  persistWorkspaceState();
  nextTick(scrollToBottom);
};

const emitWorkspaceLayout = () => {
  try {
    const payload = {
      collapsed: Boolean(isSidebarCollapsed.value),
      width: Number(sidebarWidth.value || 256),
      ts: Date.now(),
    };
    sessionStorage.setItem(_layoutKey(), JSON.stringify(payload));
    window.dispatchEvent(new CustomEvent('aspen:workspace-layout', { detail: payload }));
  } catch (e) {
    console.warn('emit workspace layout failed:', e);
  }
};

const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
  emitWorkspaceLayout();
};

const onCategoryChange = () => {
  selectedEquipment.value = null;
};

const currentEquipmentOptions = () => {
  if (!selectedCategory.value || !equipmentData[selectedCategory.value]) return [];
  return equipmentData[selectedCategory.value];
};

// --- 消息ID计数器 ---
let messageIdCounter = 0;

// 创建不同消息类型的函数
const createUserMessage = (content) => {
  return {
    id: `msg_${Date.now()}_${messageIdCounter++}`,
    type: 'user',
    content: content,
    collapsed: false
  };
};

const createThoughtMessage = (thought) => {
  return {
    id: `msg_${Date.now()}_${messageIdCounter++}`,
    type: 'thought',
    content: thought,
    collapsed: false
  };
};

const createToolRequestMessage = (toolCall) => {
  return {
    id: `msg_${Date.now()}_${messageIdCounter++}`,
    type: 'tool_request',
    call_id: toolCall.id,
    function_name: toolCall.function_name,
    args: toolCall.args,
    result: '',
    file_paths: [], // 添加文件路径数组
    is_error: false,
    collapsed: false
  };
};

const createAssistantMessage = (content) => {
  return {
    id: `msg_${Date.now()}_${messageIdCounter++}`,
    type: 'assistant',
    content: content,
    collapsed: false
  };
};

// 折叠/展开切换
const toggleCollapse = (msgId) => {
  const msg = messages.value.find(m => m.id === msgId);
  if (msg) {
    msg.collapsed = !msg.collapsed;
  }
};

// 文件处理辅助函数
const getFileName = (filePath) => {
  // 提取文件名（去除路径）
  const parts = filePath.split(/[\\/]/);
  return parts[parts.length - 1];
};

const downloadFile = async (filePath) => {
  try {
    const encodedPath = encodeURIComponent(filePath);
    const apiUrl = resolveApiBase() || import.meta.env.VITE_API_URL || window.location.origin;
    const downloadUrl = `${apiUrl}/download?file_path=${encodedPath}`;
    console.log('Download URL:', downloadUrl);

    const dlHeaders = {};
    const dlToken = getToken();
    if (dlToken) dlHeaders['Authorization'] = `Bearer ${dlToken}`;
    const response = await fetch(downloadUrl, { method: 'GET', headers: dlHeaders });
    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errText || 'Download failed'}`);
    }

    const blob = await response.blob();
    if (!blob || blob.size <= 0) {
      throw new Error('Downloaded file is empty');
    }
    const objectUrl = window.URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = getFileName(filePath);
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    window.URL.revokeObjectURL(objectUrl);
  } catch (error) {
    console.error('File download failed:', error);
    alert(`File download failed: ${error.message}`);
  }
};

// --- 逻辑处理 ---
const selectMenu = (menu) => {
  activeMenu.value = menu;
  selectedCategory.value = null;
  selectedEquipment.value = null;
  selectedProcessExample.value = null;
  persistWorkspaceState();
};

// 获取输入框placeholder
const getPlaceholder = () => {
  if (!activeMenu.value) {
    return '请选择“单元模拟”或“流程模拟”，再输入任务（Ctrl+Enter 发送）';
  } else if (activeMenu.value === 'process') {
    return '请选择流程示例，或直接输入流程任务（Ctrl+Enter 发送）';
  } else if (selectedEquipment.value) {
    return '已自动填入设备示例任务，可继续编辑（Ctrl+Enter 发送）';
  } else if (selectedCategory.value) {
    return `请选择“${categoryNames[selectedCategory.value]}”下的设备（Ctrl+Enter 发送）`;
  } else {
    return '请选择单元模拟或流程模拟，再输入任务（Ctrl+Enter 发送）';
  }
};

const formatBackendError = (data) => {
  if (!data) return '';

  // 优先使用 error 字段（包含完整错误信息）
  const errorText = String(data.error || '').trim();
  const errorMessage = String(data.error_message || '').trim();
  
  // 如果 error_message 是乱码（只有问号），使用 error 字段
  if (errorMessage && !/^[?\s]+$/.test(errorMessage)) {
    return errorMessage;
  }
  
  if (errorText) {
    const raw = errorText.toLowerCase();
    // 检查是否是阿里云欠费错误
    if (raw.includes('arrearage') || raw.includes('overdue-payment')) {
      return '模型服务账户欠费，请充值后继续使用';
    }
    if (raw.includes('insufficient balance') || raw.includes('error code: 402')) {
      return '模型余额/配额不足 (402)';
    }
    if (raw.includes('timeout') || raw.includes('timed out')) {
      return '后端请求超时';
    }
    return errorText;
  }
  
  return '未知错误';
};
const isMeaningfulError = (msg) => {
  const text = (msg || '').trim();
  if (!text) return false;
  // 现在总是返回 true，因为 formatBackendError 已经处理了乱码
  return true;
};

const resolveApiBase = () => {
  const envBase = (import.meta.env.VITE_API_BASE || '').trim();
  if (envBase) return envBase.replace(/\/$/, '');
  if (window.location.hostname.includes('dicp.sixseven.ltd')) {
    return 'http://aspenback.dicp.sixseven.ltd:5924';
  }
  return '';
};

const sseSessionId = `sse_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
let sseAbortController = null;

const handleIncomingPayload = (data) => {
  if (data.type === 'rollout_started' && data.rollout_id) {
    currentRolloutId.value = data.rollout_id;
  }



  if (data.type === 'resume_context') {
    const text = `Resume from ${data.source_rollout_id || '-'} | reward=${data.reward ?? '-'} | tools=${data.tool_call_count ?? '-'}`;
    messages.value.push(createAssistantMessage(text));
    scrollToBottom();
    return;
  }


  if (data.type === 'stopped' || data.type === 'stop_ack') {
    loading.value = false;
    currentRolloutId.value = null;
  }

  if (data.type === 'done') {
    loading.value = false;
    currentRolloutId.value = null;
    scrollToBottom();
    return;
  }

  if (data.type === 'error') {
    loading.value = false;
    currentRolloutId.value = null;
    const prettyError = formatBackendError(data);
    if (isMeaningfulError(prettyError)) {
      const errorMsg = createAssistantMessage(`Error: ${prettyError}`);
      messages.value.push(errorMsg);
      scrollToBottom();
    } else {
      console.warn('Skip placeholder backend error message', data);
    }
    return;
  }

  if (data.type === 'file_download' && data.file_paths) {
    const fileMsg = {
      id: `file_${Date.now()}_${messageIdCounter++}`,
      type: 'file_download',
      file_paths: data.file_paths
    };
    messages.value.push(fileMsg);
    scrollToBottom();
    return;
  }

  if (data.thought && data.thought.trim()) {
    const thoughtMsg = createThoughtMessage(data.thought);
    messages.value.push(thoughtMsg);
  }

  if (data.status === 'tool_calling' && data.tool_calls && data.tool_calls.length > 0) {
    data.tool_calls.forEach(toolCall => {
      const toolMsg = createToolRequestMessage(toolCall);
      messages.value.push(toolMsg);
    });
  }

  if (data.status === 'tool_executed' && data.tool_results && data.tool_results.length > 0) {
    data.tool_results.forEach(toolResult => {
      const toolMsg = messages.value.find(m =>
        m.type === 'tool_request' && m.call_id === toolResult.call_id
      );
      if (toolMsg) {
        toolMsg.result = toolResult.result;
        toolMsg.is_error = toolResult.is_error || false;
        if (toolResult.file_paths && Array.isArray(toolResult.file_paths)) {
          toolMsg.file_paths = toolResult.file_paths;
        }
      }
    });
  }

  const assistantContent = String(data.content || '').trim();
  if (assistantContent && !/^[?\s.!]+$/.test(assistantContent)) {
    const assistantMsg = createAssistantMessage(assistantContent);
    messages.value.push(assistantMsg);
  } else if (assistantContent) {
    console.warn('Skip placeholder assistant content', assistantContent);
  }

  scrollToBottom();
};

const initBackendStatus = async () => {
  try {
    const response = await fetch(`${resolveApiBase()}/health`);
    wsConnected.value = response.ok;
  } catch (error) {
    wsConnected.value = false;
    console.warn('后端健康检查失败:', error);
  }
};

const sendMessageViaSse = async ({ endpoint, body }) => {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(`${resolveApiBase()}${endpoint}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: sseAbortController.signal
  });

  if (!response.ok) {
    const raw = await response.text();
    throw new Error(raw || `HTTP ${response.status}`);
  }
  if (!response.body) {
    throw new Error('SSE response has no body');
  }

  wsConnected.value = true;
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    let splitIndex = buffer.indexOf('\n\n');

    while (splitIndex >= 0) {
      const rawEvent = buffer.slice(0, splitIndex);
      buffer = buffer.slice(splitIndex + 2);

      const dataLine = rawEvent
        .split('\n')
        .find((line) => line.startsWith('data:'));
      if (dataLine) {
        const dataText = dataLine.slice(5).trim();
        if (dataText) {
          try {
            const data = JSON.parse(dataText);
            if (data.type !== 'stream_end') {
              handleIncomingPayload(data);
            }
          } catch (error) {
            console.error('解析SSE消息失败:', error, dataText);
          }
        }
      }

      splitIndex = buffer.indexOf('\n\n');
    }
  }
  } catch (streamError) {
    if (streamError.name === 'AbortError' || String(streamError).includes('aborted')) {
      console.log('SSE stream aborted (page switch or user stop)');
      loading.value = false;
      currentRolloutId.value = null;
      return;
    }
    throw streamError;
  }
};

const stopMessage = async () => {
  if (!loading.value) return;

  if (sseAbortController) {
    try {
      const stopHeaders = { 'Content-Type': 'application/json' };
      const stopToken = getToken();
      if (stopToken) stopHeaders['Authorization'] = `Bearer ${stopToken}`;
      await fetch(`${resolveApiBase()}/api/chat/stop`, {
        method: 'POST',
        headers: stopHeaders,
        body: JSON.stringify({
          session_id: sseSessionId,
          rollout_id: currentRolloutId.value || undefined
        })
      });
    } catch (error) {
      console.warn('SSE stop request failed:', error);
    }
    return;
  }
};

const sendMessage = async () => {
  if (!userInput.value || loading.value) return;

  const content = userInput.value;
  const userMsg = createUserMessage(content);
  messages.value.push(userMsg);

  userInput.value = '';
  loading.value = true;
  currentRolloutId.value = null;
  persistActiveSession();
  try {
    const saveResult = await persistSessionToServer(activeSessionId.value);
    if (saveResult?.aborted) {
      userInput.value = content;
      loading.value = false;
      currentRolloutId.value = null;
      return;
    }
  } catch (error) {
    console.warn('persist session before stream failed:', error);
  }
  scrollToBottom();

  sseAbortController = new AbortController();
  try {
    const taskType = activeMenu.value === 'unit' ? 'unit' : (activeMenu.value === 'process' ? 'process' : '');
    const equipmentType = taskType === 'unit'
      ? (selectedEquipment.value || '')
      : (taskType === 'process' ? (selectedProcessExample.value || '') : '');
    const equipmentCategory = taskType === 'unit' ? (selectedCategory.value || '') : '';
    const processExample = taskType === 'process' ? (selectedProcessExample.value || '') : '';

    await sendMessageViaSse({
      endpoint: '/api/chat/stream',
      body: {
        message: content,
        session_id: sseSessionId,
        task_type: taskType,
        equipment_type: equipmentType,
        equipment_category: equipmentCategory,
        process_example: processExample,
      }
    });
  } catch (error) {
    if (error.name === 'AbortError' || String(error).includes('aborted')) {
      console.log('SSE stream interrupted, resetting state');
      loading.value = false;
      currentRolloutId.value = null;
      return;
    }
    console.warn('SSE 请求失败:', error);
    loading.value = false;
    currentRolloutId.value = null;
    const errorMsg = createAssistantMessage(`Error: ${String(error?.message || error)}`);
    messages.value.push(errorMsg);
    scrollToBottom();
  } finally {
    sseAbortController = null;
    const session = persistActiveSession();
    if (session?.id) {
      try {
        const saveResult = await persistSessionToServer(session.id);
        if (saveResult?.aborted) {
          loading.value = false;
          currentRolloutId.value = null;
        }
      } catch (error) {
        console.warn('persist session after stream failed:', error);
      }
    }
  }
};



const renderMarkdown = (text) => {
  try {
    return DOMPurify.sanitize(marked.parse(text));
  } catch (error) {
    console.error('Markdown解析失败:', error);
    return text;
  }
};

const scrollToBottom = async () => {
  await nextTick();
  if (chatBox.value) {
    chatBox.value.scrollTop = chatBox.value.scrollHeight;
  }
};

watch(messages, () => {
  persistWorkspaceState();
}, { deep: true });

watch(chatSessions, () => {
  persistWorkspaceState();
}, { deep: true });

watch([userInput, loading, activeMenu, selectedCategory, selectedEquipment, selectedProcessExample, currentRolloutId, isSidebarCollapsed, sidebarWidth, activeSessionId], () => {
  persistWorkspaceState();
});

watch([isSidebarCollapsed, sidebarWidth], () => {
  emitWorkspaceLayout();
});


watch(selectedEquipment, (v) => {
  if (activeMenu.value === 'unit' && v) {
    userInput.value = equipmentPrompts[v] || '';
  }
});

watch(selectedProcessExample, (v) => {
  if (activeMenu.value === 'process' && v) {
    userInput.value = processExamples[v] || '';
  }
});

const initializeWorkspace = async () => {
  await ensureUserWorkspaceContext();
  const restored = restoreWorkspaceState();
  ensureFallbackSession();
  emitWorkspaceLayout();
  await initBackendStatus();
  await syncSessionsFromServer({ restoreLocalIfEmpty: restored });
  await nextTick();
  scrollToBottom();
  workspaceInitialized.value = true;
};

const handleAuthChanged = async () => {
  const changed = await ensureUserWorkspaceContext();
  if (changed || !workspaceInitialized.value) {
    await initializeWorkspace();
    return;
  }
  if (!loading.value) {
    await syncSessionsFromServer({ restoreLocalIfEmpty: false });
  }
};

onMounted(async () => {
  window.addEventListener(AUTH_EVENT_NAME, handleAuthChanged);
  await initializeWorkspace();
});

onActivated(async () => {
  const changed = await ensureUserWorkspaceContext();
  if (changed || !workspaceInitialized.value) {
    await initializeWorkspace();
  } else {
    restoreWorkspaceState();
    ensureFallbackSession();
    emitWorkspaceLayout();
    if (!loading.value) {
      await syncSessionsFromServer({ restoreLocalIfEmpty: false });
    }
  }
  nextTick(scrollToBottom);
});

onDeactivated(() => {
  persistWorkspaceState();
});

onUnmounted(() => {
  window.removeEventListener(AUTH_EVENT_NAME, handleAuthChanged);
  persistWorkspaceState();
});
</script>

<style>
/* 自定义滚动条 */
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* 左侧菜单栏滚动条 */
aside .custom-scrollbar::-webkit-scrollbar-track { background: #f8fafc; }
aside .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; }
aside .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

.input-textarea {
  overflow-wrap: anywhere;
  word-break: break-word;
}

/* 动画效果 */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.animate-fadeIn {
  animation: fadeIn 0.2s ease-out;
}

/* 用户选择文本时禁止拖拽 */
.workspace-container * {
  user-select: none;
}

textarea, pre, .prose * {
  user-select: text;
}

/* Markdown 样式 - 使用更小的字体 */
.prose {
  font-size: 0.875rem; /* text-sm */
  line-height: 1.5;
}

.prose-sm {
  font-size: 0.75rem; /* text-xs */
  line-height: 1.4;
}

.prose table { @apply w-full border-collapse my-2 text-xs; }
.prose th { @apply bg-slate-100 border border-slate-300 p-1.5 text-left text-blue-600 text-xs; }
.prose td { @apply border border-slate-300 p-1.5 text-xs; }
.prose pre {
  @apply bg-slate-900 text-slate-100 p-2 rounded border border-slate-700 overflow-x-auto text-xs;
}
.prose code { @apply bg-blue-50 text-blue-700 px-1 py-0.5 rounded text-xs; }
.prose h1, .prose h2, .prose h3 { @apply text-gray-800 font-bold text-sm; }
.prose p { @apply text-gray-700 text-sm; }

/* 新增折叠动画 */
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
  max-height: 1000px;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}

/* 工具调用结果最大高度 */
pre.max-h-60 {
  max-height: 240px;
}

/* 文件下载按钮样式 */
.bg-indigo-50:hover {
  background-color: #e0e7ff !important;
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

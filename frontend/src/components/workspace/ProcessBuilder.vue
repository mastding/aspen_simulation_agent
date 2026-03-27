<template>
  <div class="process-builder bg-white overflow-hidden">
    <!-- 步骤指示器 -->
    <div class="flex items-center gap-0 border-b border-slate-100 bg-slate-50/50">
      <button
        v-for="(s, i) in steps"
        :key="i"
        class="flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-all border-b-2"
        :class="currentStep === i
          ? 'border-blue-500 text-blue-600 bg-white'
          : currentStep > i
            ? 'border-green-400 text-green-600 bg-green-50/30'
            : 'border-transparent text-slate-400 hover:text-slate-500'"
        @click="currentStep = i"
      >
        <span class="w-5 h-5 rounded-full text-[10px] flex items-center justify-center font-bold"
          :class="currentStep > i ? 'bg-green-100 text-green-600' : currentStep === i ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-400'">
          <svg v-if="currentStep > i" class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 13l4 4L19 7"/></svg>
          <span v-else>{{ i + 1 }}</span>
        </span>
        {{ s.label }}
      </button>
    </div>

    <div class="p-4 max-h-[340px] overflow-y-auto custom-scrollbar">
      <!-- Step 1: 选择设备 -->
      <div v-show="currentStep === 0">
        <p class="text-xs text-slate-500 mb-2">选择流程中需要的设备（可多选）：</p>
        <div v-for="(eqs, cat) in allEquipment" :key="cat" class="mb-3">
          <p class="text-[10px] text-slate-400 font-medium mb-1.5 uppercase tracking-wide">{{ catNames[cat] }}</p>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="eq in eqs" :key="eq.id"
              class="px-2.5 py-1.5 text-xs rounded-lg border transition-all flex items-center gap-1"
              :class="isSelected(eq.id)
                ? 'bg-blue-50 text-blue-600 border-blue-300 shadow-sm'
                : 'bg-white text-slate-500 border-slate-200 hover:border-blue-200'"
              @click="toggleEquipment(eq)"
            >
              <span class="w-4 h-4 rounded border flex items-center justify-center text-[10px]"
                :class="isSelected(eq.id) ? 'bg-blue-500 border-blue-500 text-white' : 'border-slate-300'">
                <svg v-if="isSelected(eq.id)" class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 13l4 4L19 7"/></svg>
              </span>
              {{ eq.name }}
            </button>
          </div>
        </div>
        <p v-if="!selectedEquipments.length" class="text-[10px] text-amber-500 mt-2">请至少选择一个设备</p>
      </div>

      <!-- Step 2: 连接流程 -->
      <div v-show="currentStep === 1">
        <p class="text-xs text-slate-500 mb-2">拖拽排列设备顺序，定义物料流向：</p>
        <div v-if="selectedEquipments.length" class="space-y-2">
          <!-- 流程图 -->
          <div class="flex items-center gap-1 flex-wrap bg-slate-50 rounded-lg p-3">
            <span class="text-xs text-slate-400 font-medium px-2 py-1 bg-white rounded border border-dashed border-slate-300">进料</span>
            <template v-for="(eq, i) in selectedEquipments" :key="eq.id">
              <svg class="w-4 h-4 text-slate-300 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
              <div class="flex items-center gap-1 px-2 py-1 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                <span>{{ eq.name.split(' ')[0] }}</span>
                <button @click="moveEquipment(i, -1)" v-if="i > 0" class="text-blue-400 hover:text-blue-600">
                  <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
                </button>
                <button @click="moveEquipment(i, 1)" v-if="i < selectedEquipments.length - 1" class="text-blue-400 hover:text-blue-600">
                  <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
                </button>
              </div>
            </template>
            <svg class="w-4 h-4 text-slate-300 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
            <span class="text-xs text-slate-400 font-medium px-2 py-1 bg-white rounded border border-dashed border-slate-300">产品</span>
          </div>
          <!-- 物性方法 -->
          <div class="flex items-center gap-2 mt-2">
            <label class="text-xs text-slate-500 shrink-0">物性方法：</label>
            <select v-model="thermoMethod" class="flex-1 text-xs border border-slate-200 rounded-lg px-2 py-1.5 text-slate-600 bg-white focus:outline-none focus:border-blue-400">
              <option v-for="m in thermoMethods" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>
        </div>
        <div v-else class="text-xs text-slate-400 bg-slate-50 rounded-lg p-4 text-center">请先在第①步选择设备</div>
      </div>

      <!-- Step 3: 进料条件 -->
      <div v-show="currentStep === 2">
        <p class="text-xs text-slate-500 mb-2">定义进料物流条件：</p>
        <div class="space-y-3">
          <div v-for="(feed, fi) in feeds" :key="fi" class="bg-slate-50 rounded-lg p-3 space-y-2 relative">
            <div class="flex items-center justify-between">
              <span class="text-xs font-medium text-slate-600">进料 {{ fi + 1 }}</span>
              <div class="flex items-center gap-1">
                <button v-if="feeds.length > 1" @click="feeds.splice(fi, 1)" class="text-slate-300 hover:text-red-400 transition-colors">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                </button>
              </div>
            </div>
            <div class="grid grid-cols-3 gap-2">
              <div>
                <label class="text-[10px] text-slate-400">温度</label>
                <input v-model="feed.temperature" placeholder="如 25℃" class="w-full text-xs border border-slate-200 rounded px-2 py-1.5 text-slate-600 focus:outline-none focus:border-blue-400" />
              </div>
              <div>
                <label class="text-[10px] text-slate-400">压力</label>
                <input v-model="feed.pressure" placeholder="如 0.1MPa" class="w-full text-xs border border-slate-200 rounded px-2 py-1.5 text-slate-600 focus:outline-none focus:border-blue-400" />
              </div>
              <div>
                <label class="text-[10px] text-slate-400">总流量</label>
                <input v-model="feed.flowRate" placeholder="如 5000kg/h" class="w-full text-xs border border-slate-200 rounded px-2 py-1.5 text-slate-600 focus:outline-none focus:border-blue-400" />
              </div>
            </div>
            <div>
              <label class="text-[10px] text-slate-400">组分及流量（每行一个，格式：组分名:流量）</label>
              <textarea v-model="feed.components" rows="2" placeholder="如：乙苯:4815kg/h&#10;水蒸气:327kg/h" class="w-full text-xs border border-slate-200 rounded px-2 py-1.5 text-slate-600 focus:outline-none focus:border-blue-400 resize-none" />
            </div>
          </div>
          <button @click="addFeed" class="w-full py-1.5 text-xs text-blue-500 border border-dashed border-blue-300 rounded-lg hover:bg-blue-50 transition-colors">+ 添加进料</button>
        </div>
      </div>

      <!-- Step 4: 操作参数 + 期望结果 -->
      <div v-show="currentStep === 3">
        <div class="space-y-3">
          <!-- 操作参数 -->
          <div>
            <p class="text-xs text-slate-500 mb-2">关键操作参数（选填，按设备填写）：</p>
            <div v-for="eq in selectedEquipments" :key="eq.id" class="mb-2">
              <label class="text-[10px] text-slate-400 font-medium">{{ eq.name }}</label>
              <input v-model="operatingParams[eq.id]" :placeholder="getParamHint(eq.id)" class="w-full text-xs border border-slate-200 rounded px-2 py-1.5 mt-0.5 text-slate-600 focus:outline-none focus:border-blue-400" />
            </div>
            <div v-if="!selectedEquipments.length" class="text-xs text-slate-400 bg-slate-50 rounded-lg p-3 text-center">请先在第①步选择设备</div>
          </div>
          <!-- 期望结果 -->
          <div>
            <p class="text-xs text-slate-500 mb-2">期望结果 / 产品要求：</p>
            <textarea v-model="expectedResult" rows="2" placeholder="如：产品苯乙烯纯度≥0.972&#10;塔顶乙苯回收率≥99.9%" class="w-full text-xs border border-slate-200 rounded px-2 py-1.5 text-slate-600 focus:outline-none focus:border-blue-400 resize-none" />
          </div>
          <!-- 补充说明 -->
          <div>
            <p class="text-xs text-slate-500 mb-2">补充说明（选填）：</p>
            <textarea v-model="extraNotes" rows="2" placeholder="如：优先使用RStoic反应器、反应方程式等" class="w-full text-xs border border-slate-200 rounded px-2 py-1.5 text-slate-600 focus:outline-none focus:border-blue-400 resize-none" />
          </div>
        </div>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div class="flex items-center justify-between px-4 py-2.5 border-t border-slate-100 bg-slate-50/30">
      <button v-if="currentStep > 0" @click="currentStep--" class="text-xs text-slate-400 hover:text-slate-600 transition-colors">← 上一步</button>
      <div v-else />
      <div class="flex items-center gap-2">
        <button @click="$emit('preview', buildPrompt())" class="px-3 py-1.5 text-xs text-slate-500 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors">预览描述</button>
        <button v-if="currentStep < steps.length - 1" @click="currentStep++" class="px-3 py-1.5 text-xs text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors">下一步 →</button>
        <button v-else @click="$emit('send', buildPrompt())" class="px-3 py-1.5 text-xs text-white bg-green-500 rounded-lg hover:bg-green-600 transition-colors">发送任务</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';

defineEmits(['send', 'preview']);

const currentStep = ref(0);
const steps = [
  { label: '选择设备' },
  { label: '连接流程' },
  { label: '进料条件' },
  { label: '参数与目标' },
];

const catNames = {
  simple: '常规单元', heat: '热交换', transport: '流体输送', tower: '塔设备', reactor: '反应器',
};

const allEquipment = {
  reactor: [
    { id: 'rstoic', name: '反应器 RStoic' },
    { id: 'rplug', name: '反应器 RPlug' },
    { id: 'rcstr', name: '反应器 RCSTR' },
  ],
  tower: [
    { id: 'radfrac', name: '精馏塔 RadFrac' },
    { id: 'distl', name: '精馏塔 Distl' },
    { id: 'dstwu', name: '精馏塔设计 DSTWU' },
    { id: 'extract', name: '萃取塔 Extract' },
  ],
  heat: [
    { id: 'heater', name: '换热器 Heater' },
    { id: 'heatx', name: '换热器 HeatX' },
  ],
  simple: [
    { id: 'mixer', name: '混合器 Mixer' },
    { id: 'sep', name: '分离器 Sep' },
    { id: 'flash', name: '闪蒸罐 Flash' },
    { id: 'fsplit', name: '分流器 FSplit' },
    { id: 'valve', name: '阀门 Valve' },
  ],
  transport: [
    { id: 'pump', name: '离心泵 Pump' },
    { id: 'compr', name: '压缩机 Compr' },
  ],
};

const thermoMethods = ['PENG-ROB', 'RK-SOAVE', 'NRTL', 'UNIQUAC', 'WILSON', 'CHAO-SEA', 'IAPWS-95'];
const thermoMethod = ref('PENG-ROB');

const selectedEquipments = ref([]);

function isSelected(id) {
  return selectedEquipments.value.some(e => e.id === id);
}

function toggleEquipment(eq) {
  const idx = selectedEquipments.value.findIndex(e => e.id === eq.id);
  if (idx >= 0) {
    selectedEquipments.value.splice(idx, 1);
  } else {
    selectedEquipments.value.push({ ...eq });
  }
}

function moveEquipment(i, dir) {
  const arr = selectedEquipments.value;
  const j = i + dir;
  if (j < 0 || j >= arr.length) return;
  [arr[i], arr[j]] = [arr[j], arr[i]];
}

// --- Step 3: feeds ---
const feeds = ref([{ temperature: '', pressure: '', flowRate: '', components: '' }]);
function addFeed() {
  feeds.value.push({ temperature: '', pressure: '', flowRate: '', components: '' });
}

// --- Step 4: params ---
const operatingParams = reactive({});
const expectedResult = ref('');
const extraNotes = ref('');

const paramHints = {
  rstoic: '反应温度、压力、反应方程式及转化率',
  rplug: '反应温度、压力、反应器长度/体积',
  rcstr: '反应温度、压力、反应器体积',
  radfrac: '塔板数、进料板位置、回流比、塔顶/塔底压力',
  distl: '塔板数、回流比、馏出比',
  dstwu: '轻/重关键组分回收率',
  extract: '塔板数、溶剂比',
  heater: '出口温度或热负荷',
  heatx: '热/冷侧出口温度',
  mixer: '（通常无需额外参数）',
  sep: '分离分率',
  flash: '闪蒸温度、压力',
  fsplit: '分流比',
  valve: '出口压力',
  pump: '出口压力、泵效率',
  compr: '出口压力、效率',
};
function getParamHint(id) {
  return paramHints[id] || '操作条件';
}

// --- Build prompt ---
function buildPrompt() {
  const parts = [];

  // 设备清单
  const eqNames = selectedEquipments.value.map(e => e.name).join('、');
  if (eqNames) parts.push(`【设备清单】使用以下设备：${eqNames}`);

  // 流程连接
  if (selectedEquipments.value.length > 1) {
    const flow = ['进料', ...selectedEquipments.value.map(e => e.name.split(' ')[0]), '产品'].join(' → ');
    parts.push(`【流程连接】${flow}`);
  }

  // 进料条件
  feeds.value.forEach((f, i) => {
    const lines = [];
    const label = feeds.value.length > 1 ? `进料${i + 1}` : '进料';
    if (f.temperature) lines.push(`温度：${f.temperature}`);
    if (f.pressure) lines.push(`压力：${f.pressure}`);
    if (f.flowRate) lines.push(`流量：${f.flowRate}`);
    if (f.components?.trim()) lines.push(`组分：${f.components.trim()}`);
    if (lines.length) parts.push(`【${label}条件】${lines.join('，')}`);
  });

  // 操作参数
  const paramLines = [];
  selectedEquipments.value.forEach(eq => {
    const v = (operatingParams[eq.id] || '').trim();
    if (v) paramLines.push(`${eq.name.split(' ')[0]}：${v}`);
  });
  if (paramLines.length) parts.push(`【操作参数】${paramLines.join('；')}`);

  // 物性方法
  parts.push(`【物性方法】${thermoMethod.value}`);

  // 期望结果
  if (expectedResult.value.trim()) parts.push(`【期望结果】${expectedResult.value.trim()}`);

  // 补充说明
  if (extraNotes.value.trim()) parts.push(`【补充说明】${extraNotes.value.trim()}`);

  return parts.join('\n');
}
</script>

<template>
  <div class="prompt-composer border-t border-slate-200/60 bg-white/80 backdrop-blur-sm">
    <!-- 模式切换栏：单元模拟 / 流程模拟 -->
    <div class="flex items-center gap-2 px-4 pt-3 pb-1">
      <button
        v-for="m in modes"
        :key="m.key"
        class="mode-btn px-3 py-1.5 text-xs rounded-full border transition-all duration-200"
        :class="activeMenu === m.key
          ? 'bg-blue-500 text-white border-blue-500 shadow-sm'
          : 'bg-white text-slate-500 border-slate-200 hover:border-blue-300 hover:text-blue-500'"
        @click="$emit('select-menu', activeMenu === m.key ? '' : m.key)"
      >
        <span v-html="m.icon" class="inline-block w-3.5 h-3.5 align-middle mr-1"></span>
        {{ m.label }}
      </button>
      <div class="flex-1" />
      <span class="text-[10px] text-slate-300">Ctrl+Enter 发送</span>
    </div>

    <!-- 单元模拟：示例任务 / 自定义创建 -->
    <div v-if="activeMenu === 'unit'" class="px-4 py-2 space-y-2">
      <!-- 模式切换 -->
      <div class="flex items-center gap-2 mb-1">
        <button
          class="px-2.5 py-1 text-xs rounded-md border transition-all"
          :class="unitMode === 'example' ? 'bg-blue-50 text-blue-600 border-blue-300' : 'bg-white text-slate-400 border-slate-200 hover:border-blue-200'"
          @click="unitMode = 'example'"
        >示例任务</button>
        <button
          class="px-2.5 py-1 text-xs rounded-md border transition-all"
          :class="unitMode === 'custom' ? 'bg-blue-50 text-blue-600 border-blue-300' : 'bg-white text-slate-400 border-slate-200 hover:border-blue-200'"
          @click="unitMode = 'custom'"
        >自定义创建</button>
      </div>
      <!-- 示例任务：设备类别 → 设备选择（自动填充预设 prompt） -->
      <template v-if="unitMode === 'example'">
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="(label, key) in categoryNames"
            :key="key"
            class="px-2 py-0.5 text-[11px] rounded-md border transition-all"
            :class="selectedCategory === key
              ? 'bg-blue-50 text-blue-600 border-blue-300'
              : 'bg-white text-slate-400 border-slate-200 hover:border-blue-200 hover:text-slate-600'"
            @click="$emit('category-change'); $emit('update:selected-category', selectedCategory === key ? null : key)"
          >{{ label }}</button>
        </div>
        <div v-if="selectedCategory && equipmentOptions.length" class="flex flex-wrap gap-1.5">
          <button
            v-for="eq in equipmentOptions"
            :key="eq.id"
            class="px-2 py-0.5 text-[11px] rounded-md border transition-all"
            :class="selectedEquipment === eq.id
              ? 'bg-green-50 text-green-600 border-green-300'
              : 'bg-white text-slate-400 border-slate-200 hover:border-green-200 hover:text-slate-600'"
            @click="$emit('update:selected-equipment', selectedEquipment === eq.id ? null : eq.id)"
          >{{ eq.name }}</button>
        </div>
      </template>
      <!-- 自定义创建：直接输入 -->
      <div v-if="unitMode === 'custom'" class="text-xs text-slate-400 pl-0.5">
        请在下方输入框中描述单元模拟任务，包括设备类型、进料条件、操作参数和物性方法
      </div>
    </div>

    <!-- 流程模拟：示例选择 + 结构化构建器 -->
    <div v-if="activeMenu === 'process'" class="px-4 py-2 space-y-2">
      <!-- 模式切换：示例 / 自定义构建 -->
      <div class="flex items-center gap-2 mb-1">
        <button
          class="px-2.5 py-1 text-xs rounded-md border transition-all"
          :class="processMode === 'example' ? 'bg-purple-50 text-purple-600 border-purple-300' : 'bg-white text-slate-400 border-slate-200 hover:border-purple-200'"
          @click="processMode = 'example'"
        >示例任务</button>
        <button
          class="px-2.5 py-1 text-xs rounded-md border transition-all"
          :class="processMode === 'builder' ? 'bg-purple-50 text-purple-600 border-purple-300' : 'bg-white text-slate-400 border-slate-200 hover:border-purple-200'"
          @click="processMode = 'builder'"
        >自定义构建</button>
      </div>
      <!-- 示例选择 -->
      <div v-if="processMode === 'example'" class="flex flex-wrap gap-1.5">
        <button
          v-for="(label, key) in processExampleNames"
          :key="key"
          class="px-2 py-0.5 text-[11px] rounded-md border transition-all"
          :class="selectedProcessExample === key
            ? 'bg-purple-50 text-purple-600 border-purple-300'
            : 'bg-white text-slate-400 border-slate-200 hover:border-purple-200 hover:text-slate-600'"
          @click="$emit('update:selected-process-example', selectedProcessExample === key ? null : key)"
        >{{ label }}</button>
      </div>
      <!-- 结构化构建器（弹窗模式） -->
      <Teleport to="body">
        <div v-if="processMode === 'builder'" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/30 backdrop-blur-sm" @click.self="processMode = 'example'">
          <div class="w-[680px] max-h-[80vh] bg-white rounded-xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden">
            <div class="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 bg-slate-50/50">
              <span class="text-sm font-semibold text-slate-700">流程自定义构建</span>
              <button @click="processMode = 'example'" class="text-slate-400 hover:text-slate-600 transition-colors">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
            <div class="flex-1 min-h-0 overflow-y-auto">
              <ProcessBuilder
                @preview="onBuilderPreview"
                @send="(p) => { onBuilderSend(p); processMode = 'example'; }"
              />
            </div>
          </div>
        </div>
      </Teleport>
    </div>

    <!-- 输入区 -->
    <div class="px-4 pb-5 pt-1">
      <div class="relative flex items-end gap-2 bg-slate-50 rounded-xl border border-slate-200 focus-within:border-blue-400 focus-within:ring-1 focus-within:ring-blue-100 transition-all">
        <textarea
          ref="textareaRef"
          :value="modelValue"
          @input="$emit('update:modelValue', $event.target.value)"
          @keydown.ctrl.enter.prevent="handleSend"
          :placeholder="placeholder"
          rows="4"
          class="flex-1 bg-transparent px-4 py-3 text-xs text-slate-700 placeholder-slate-300 resize-none outline-none max-h-40 custom-scrollbar"
        />
        <div class="flex items-center gap-1 pr-3 pb-2.5">
          <button v-if="loading" @click="$emit('stop')" class="p-2 rounded-lg bg-red-50 text-red-500 hover:bg-red-100 transition-colors" title="停止">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
          </button>
          <button v-else @click="handleSend" :disabled="!modelValue?.trim()" class="p-2 rounded-lg transition-colors" :class="modelValue?.trim() ? 'bg-blue-500 text-white hover:bg-blue-600' : 'bg-slate-100 text-slate-300'" title="发送">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import ProcessBuilder from './ProcessBuilder.vue';

const props = defineProps({
  modelValue: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  placeholder: { type: String, default: '' },
  activeMenu: { type: String, default: '' },
  selectedCategory: { type: String, default: null },
  selectedEquipment: { type: String, default: null },
  selectedProcessExample: { type: String, default: null },
  categoryNames: { type: Object, default: () => ({}) },
  processExampleNames: { type: Object, default: () => ({}) },
  equipmentOptions: { type: Array, default: () => [] },
  messagesLength: { type: Number, default: 0 },
});

const emit = defineEmits([
  'update:modelValue', 'send', 'stop', 'select-menu',
  'category-change', 'update:selected-category',
  'update:selected-equipment', 'update:selected-process-example',
]);

const textareaRef = ref(null);
const processMode = ref('example'); // 'example' | 'builder'
const unitMode = ref('example'); // 'example' | 'custom'

const modes = [
  { key: 'unit', label: '单元模拟', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>' },
  { key: 'process', label: '流程模拟', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12h4l3-9 4 18 3-9h4"/></svg>' },
];

function handleSend() {
  if (props.modelValue?.trim() && !props.loading) {
    emit('send');
  }
}

function onBuilderPreview(prompt) {
  emit('update:modelValue', prompt);
}

function onBuilderSend(prompt) {
  emit('update:modelValue', prompt);
  // nextTick to let v-model propagate, then send
  setTimeout(() => emit('send'), 0);
}
</script>

<template>
  <aside
    class="h-full flex flex-col border-r border-slate-200/60 bg-gradient-to-b from-slate-50 to-blue-50/30 transition-all duration-200 shrink-0 select-none relative"
    :style="{ width: isCollapsed ? '48px' : sidebarWidth + 'px' }"
  >
    <!-- 顶部：折叠按钮 + 新建 -->
    <div class="flex items-center gap-1 px-2 py-3" :class="isCollapsed ? 'justify-center' : 'justify-between'">
      <button @click="$emit('toggle-sidebar')" class="p-1.5 rounded-lg hover:bg-white/60 text-slate-400 hover:text-slate-600 transition-colors" title="折叠/展开">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
      </button>
      <button v-if="!isCollapsed" @click="$emit('create-session')" class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
        新对话
      </button>
    </div>

    <!-- 会话列表 -->
    <div v-if="!isCollapsed" class="flex-1 overflow-y-auto custom-scrollbar px-2 pb-2 space-y-0.5">
      <div
        v-for="session in chatSessions"
        :key="session.id"
        class="group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all duration-150 text-sm"
        :class="session.id === activeSessionId
          ? 'bg-white shadow-sm text-blue-700 font-medium'
          : 'text-slate-500 hover:bg-white/50 hover:text-slate-700'"
        @click="$emit('switch-session', session.id)"
      >
        <svg class="w-3.5 h-3.5 shrink-0 opacity-50" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span class="flex-1 truncate text-xs">{{ session.title || '新对话' }}</span>
        <button
          v-if="session.id === activeSessionId"
          @click.stop="$emit('delete-session', session.id)"
          class="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-50 text-slate-300 hover:text-red-400 transition-all"
          title="删除"
        >
          <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>
    </div>

    <!-- 拖拽手柄 -->
    <div
      v-if="!isCollapsed"
      class="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-blue-300/40 transition-colors z-10"
      @mousedown="startResize"
    />
  </aside>
</template>

<script setup>
const props = defineProps({
  chatSessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: '' },
  isCollapsed: { type: Boolean, default: false },
  sidebarWidth: { type: Number, default: 240 },
});
const emit = defineEmits(['create-session', 'switch-session', 'delete-session', 'toggle-sidebar', 'update:sidebar-width']);

let startX = 0;
let startW = 0;
function startResize(e) {
  startX = e.clientX;
  startW = props.sidebarWidth;
  const onMove = (ev) => {
    const w = Math.max(180, Math.min(400, startW + ev.clientX - startX));
    emit('update:sidebar-width', w);
  };
  const onUp = () => {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  };
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}
</script>

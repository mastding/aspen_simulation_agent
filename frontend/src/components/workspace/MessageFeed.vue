<template>
  <div class="message-feed space-y-3">
    <!-- 空状态引导 -->
    <div v-if="!messages.length && !loading" class="flex flex-col items-center justify-center h-full py-20 select-none">
      <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center mb-4">
        <svg class="w-8 h-8 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        </svg>
      </div>
      <p class="text-sm font-medium text-slate-500 mb-1">化工流程模拟智能助手</p>
      <p class="text-xs text-slate-400 max-w-xs text-center leading-relaxed">
        选择「单元模拟」或「流程模拟」模式，输入任务描述开始仿真
      </p>
    </div>

    <!-- 消息列表 -->
    <template v-for="msg in messages" :key="msg.id">
      <!-- 用户消息 -->
      <div v-if="msg.type === 'user'" class="flex justify-end">
        <div class="max-w-[75%] bg-blue-500 text-white px-4 py-2.5 rounded-2xl rounded-br-md text-sm leading-relaxed shadow-sm">
          {{ msg.content }}
        </div>
      </div>

      <!-- 思维链 -->
      <div v-else-if="msg.type === 'thought'" class="flex justify-start">
        <div class="max-w-[80%]">
          <button @click="$emit('toggle-collapse', msg.id)" class="flex items-center gap-1.5 text-xs text-amber-500 hover:text-amber-600 mb-1 transition-colors">
            <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zM12 16v-4M12 8h.01"/></svg>
            <span>思维链</span>
            <svg class="w-3 h-3 transition-transform" :class="msg.collapsed ? '' : 'rotate-180'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
          </button>
          <div v-show="!msg.collapsed" class="bg-amber-50/60 border border-amber-100 px-3 py-2 rounded-xl text-xs text-amber-800/80 leading-relaxed max-h-40 overflow-y-auto custom-scrollbar">
            {{ msg.content }}
          </div>
        </div>
      </div>

      <!-- 工具调用 -->
      <div v-else-if="msg.type === 'tool_request'" class="flex justify-start">
        <div class="max-w-[80%] w-full">
          <button @click="$emit('toggle-collapse', msg.id)" class="flex items-center gap-1.5 text-xs mb-1 transition-colors" :class="msg.is_error ? 'text-red-400 hover:text-red-500' : 'text-teal-500 hover:text-teal-600'">
            <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>
            <span class="font-medium">{{ toolDisplayName(msg.function_name) }}</span>
            <span v-if="msg.result" class="px-1.5 py-0.5 rounded text-[10px]" :class="msg.is_error ? 'bg-red-50 text-red-500' : 'bg-green-50 text-green-600'">
              {{ msg.is_error ? '失败' : '完成' }}
            </span>
            <span v-else class="px-1.5 py-0.5 rounded text-[10px] bg-blue-50 text-blue-500 animate-pulse">执行中</span>
            <svg class="w-3 h-3 transition-transform ml-auto" :class="msg.collapsed ? '' : 'rotate-180'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
          </button>
          <div v-show="!msg.collapsed" class="border rounded-xl overflow-hidden text-xs" :class="msg.is_error ? 'border-red-100 bg-red-50/30' : 'border-slate-100 bg-slate-50/50'">
            <!-- 参数 -->
            <div v-if="msg.args" class="px-3 py-2 border-b border-slate-100/60">
              <span class="text-slate-400 text-[10px]">参数</span>
              <pre class="mt-1 text-slate-600 whitespace-pre-wrap break-all max-h-24 overflow-y-auto custom-scrollbar">{{ formatArgs(msg.args) }}</pre>
            </div>
            <!-- 结果 -->
            <div v-if="msg.result" class="px-3 py-2">
              <span class="text-slate-400 text-[10px]">结果</span>
              <pre class="mt-1 whitespace-pre-wrap break-all max-h-60 overflow-y-auto custom-scrollbar" :class="msg.is_error ? 'text-red-600' : 'text-slate-600'">{{ formatResult(msg.result) }}</pre>
            </div>
            <!-- 文件下载 -->
            <div v-if="msg.file_paths && msg.file_paths.length" class="px-3 py-2 border-t border-slate-100/60 flex flex-wrap gap-1.5">
              <button v-for="(fp, fi) in msg.file_paths" :key="fi" @click="$emit('download-file', typeof fp === 'string' ? fp : (fp?.path || fp))" class="inline-flex items-center gap-1 px-2 py-1 bg-indigo-50 hover:bg-indigo-100 rounded text-indigo-600 text-[10px] transition-colors">
                <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                {{ extractFileName(fp) }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 文件下载 -->
      <div v-else-if="msg.type === 'file_download'" class="flex justify-start">
        <div class="max-w-[80%] space-y-1">
          <div v-for="(fp, fi) in msg.file_paths" :key="fi" class="inline-flex items-center gap-2 bg-indigo-50 hover:bg-indigo-100 px-3 py-2 rounded-lg cursor-pointer transition-colors" @click="$emit('download-file', typeof fp === 'string' ? fp : (fp?.path || fp))">
            <svg class="w-4 h-4 text-indigo-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
            <span class="text-xs text-indigo-600 truncate max-w-[200px]">{{ extractFileName(fp) }}</span>
          </div>
        </div>
      </div>

      <!-- 助手回复 -->
      <div v-else-if="msg.type === 'assistant'" class="flex justify-start">
        <div class="max-w-[80%] bg-white border border-slate-100 px-4 py-3 rounded-2xl rounded-bl-md shadow-sm">
          <div class="prose prose-sm text-sm text-slate-700 leading-relaxed" v-html="renderMarkdown(msg.content)"></div>
        </div>
      </div>
    </template>

    <!-- 加载指示器 -->
    <div v-if="loading" class="flex justify-start">
      <div class="flex items-center gap-2 bg-white/80 border border-slate-100 px-4 py-2.5 rounded-2xl rounded-bl-md">
        <div class="flex gap-1">
          <span class="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style="animation-delay:0ms"></span>
          <span class="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style="animation-delay:150ms"></span>
          <span class="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style="animation-delay:300ms"></span>
        </div>
        <span class="text-xs text-slate-400">思考中...</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  messages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  renderMarkdown: { type: Function, default: (t) => t },
});
defineEmits(['toggle-collapse', 'download-file']);

const toolNameMap = {
  get_schema: '获取流程Schema',
  run_simulation: '运行仿真',
  get_result: '获取仿真结果',
  download_aspen_file: '下载Aspen文件',
  memory_search_experience: '搜索经验',
  memory_get_experience: '获取经验详情',
};

function toolDisplayName(name) {
  return toolNameMap[name] || name;
}

function extractFileName(fp) {
  const s = typeof fp === 'string' ? fp : (fp?.path || fp?.name || String(fp || ''));
  return s.split(/[\\/]/).pop() || s;
}

function formatArgs(args) {
  if (!args) return '';
  if (typeof args === 'string') {
    try { return JSON.stringify(JSON.parse(args), null, 2); } catch { return args; }
  }
  return JSON.stringify(args, null, 2);
}

function formatResult(result) {
  if (!result) return '';
  if (typeof result === 'string') {
    try { return JSON.stringify(JSON.parse(result), null, 2); } catch { return result; }
  }
  return JSON.stringify(result, null, 2);
}
</script>

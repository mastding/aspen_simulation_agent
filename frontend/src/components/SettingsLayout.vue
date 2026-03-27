<template>
  <section class="h-full flex bg-[#f6f8fa]">
    <!-- Left sidebar -->
    <aside class="settings-sidebar shrink-0 w-[220px] border-r border-[#d1d9e0] bg-gradient-to-b from-slate-50 to-blue-50/30 overflow-y-auto">
      <div class="px-4 pt-5 pb-2">
        <h2 class="text-[15px] font-semibold text-[#1f2328]">{{ title }}</h2>
      </div>
      <nav class="px-2 pb-4">
        <template v-for="group in groups" :key="group.label">
          <div v-if="group.label" class="px-2 pt-4 pb-1 text-[11px] font-semibold text-[#656d76] uppercase tracking-wide">{{ group.label }}</div>
          <ul class="space-y-0.5">
            <li v-for="item in group.items" :key="item.id">
              <button
                @click="$emit('select', item.id)"
                class="w-full text-left px-3 py-[6px] rounded-md text-[13px] transition-colors flex items-center gap-2"
                :class="item.id === active
                  ? 'bg-[#0969da] text-white font-medium'
                  : 'text-[#1f2328] hover:bg-[#eaeef2]'"
              >
                <span v-if="item.icon" class="settings-nav-icon" :class="item.id === active ? 'text-white' : 'text-[#656d76]'" v-html="item.icon"></span>
                {{ item.label }}
                <span v-if="item.badge != null" class="ml-auto inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[11px] font-medium"
                  :class="item.id === active ? 'bg-white/25 text-white' : 'bg-[#e8e8e8] text-[#656d76]'"
                >{{ item.badge }}</span>
              </button>
            </li>
          </ul>
        </template>
      </nav>
    </aside>

    <!-- Right content panel -->
    <main class="flex-1 min-w-0 overflow-y-auto">
      <div :class="fluid ? 'px-6 py-6' : 'max-w-[980px] mx-auto px-6 py-6'">
        <slot />
      </div>
    </main>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  active: { type: String, default: '' },
  fluid: { type: Boolean, default: false },
  groups: {
    type: Array,
    default: () => [],
  },
});
defineEmits(['select']);
</script>

<style>
.settings-nav-icon {
  display: inline-flex;
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}
.settings-nav-icon svg {
  width: 100%;
  height: 100%;
}
</style>

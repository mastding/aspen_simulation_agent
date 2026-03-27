<template>
  <!-- 登录页 -->
  <div v-if="isLoginPage">
    <RouterView />
    <ToastContainer />
  </div>
  <!-- 管理员：完整导航布局 -->
  <div v-else-if="isAdminUser" class="h-screen app-shell flex flex-col">
    <header class="shrink-0 app-header sticky top-0 z-50">
      <div class="px-4 pt-2 pb-1">
        <div class="flex items-center justify-between gap-3 px-1 py-2">
          <div class="flex items-center gap-2"><img src="/logo.png" alt="logo" class="w-8 h-8 rounded" /><span class="app-title text-2xl md:text-2xl font-bold tracking-tight">{{ appTitle }}</span></div>
          <div class="flex items-center gap-3">
            <span class="text-xs text-gray-500">{{ currentUser?.phone }} (管理员)</span>
            <button @click="handleLogout" class="text-xs text-gray-400 hover:text-red-500 transition-colors" title="退出登录">退出</button>
            <RouterLink to="/help" class="help-q" aria-label="帮助中心" title="帮助中心">?</RouterLink>
          </div>
        </div>
        <nav class="mt-1 flex items-center gap-1.5 overflow-x-auto whitespace-nowrap app-nav px-1 py-1">
          <RouterLink
            v-for="item in allNavItems"
            :key="item.path"
            :to="item.path"
            class="app-nav-link inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border transition-colors"
            :class="route.path === item.path ? 'is-active' : 'is-idle'"
          >
            <span class="nav-icon" v-html="item.iconSvg"></span>
            <span>{{ item.label }}</span>
          </RouterLink>
        </nav>
      </div>
    </header>
    <main class="flex-1 min-h-0">
      <RouterView v-slot="{ Component, route: currentRoute }">
        <KeepAlive include="WorkspaceView">
          <component v-if="currentRoute.meta?.keepAlive" :is="Component" />
        </KeepAlive>
        <component v-if="!currentRoute.meta?.keepAlive" :is="Component" />
      </RouterView>
    </main>
    <ToastContainer />
  </div>
  <!-- 普通用户：全屏工作台，右上角用户名+退出 -->
  <div v-else class="h-screen flex flex-col">
    <div class="shrink-0 flex items-center justify-between gap-3 px-4 py-2 bg-white/80 backdrop-blur-sm border-b border-slate-100/60 z-50">
      <div class="flex items-center gap-2">
        <img src="/logo.png" alt="logo" class="w-7 h-7 rounded" />
        <span class="text-sm font-semibold text-slate-700 tracking-tight">化工流程模拟智能助手</span>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-xs text-slate-500">{{ currentUser?.phone }}</span>
        <button @click="handleLogout" class="text-xs text-slate-400 hover:text-red-500 transition-colors">退出</button>
      </div>
    </div>
    <div class="flex-1 min-h-0">
      <RouterView v-slot="{ Component, route: currentRoute }">
        <KeepAlive include="WorkspaceView">
          <component v-if="currentRoute.meta?.keepAlive" :is="Component" />
        </KeepAlive>
        <component v-if="!currentRoute.meta?.keepAlive" :is="Component" />
      </RouterView>
    </div>
    <ToastContainer />
  </div>
</template>

<script setup>
import { KeepAlive, onMounted, computed, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import ToastContainer from "./components/common/ToastContainer.vue";
import { getUser, clearAuth } from "./services/auth";

const route = useRoute();
const router = useRouter();
const appTitle = "化工流程模拟智能助手";
const icon = (path) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${path}"/></svg>`;

const currentUser = ref(getUser());
const isLoginPage = computed(() => route.path === '/login');
const isAdminUser = computed(() => currentUser.value?.role === 'admin');

watch(route, () => { currentUser.value = getUser(); });

onMounted(() => {
  document.documentElement.setAttribute("data-theme", "uipro_steel");
  localStorage.setItem("aspen.theme", "uipro_steel");
});

const allNavItems = [
  { path: "/workspace", label: "工作台", iconSvg: icon("M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5") },
  { path: "/runs", label: "任务历史", iconSvg: icon("M12 8v5l3 2M12 3a9 9 0 1 0 9 9") },
  { path: "/memory", label: "经验中心", iconSvg: icon("M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 3H20v18H6.5A2.5 2.5 0 0 1 4 18.5V5.5A2.5 2.5 0 0 1 6.5 3Z") },
  { path: "/rl-lab", label: "训练工作台", iconSvg: icon("M10 2v7.5L4.5 19a2 2 0 0 0 1.7 3h11.6a2 2 0 0 0 1.7-3L14 9.5V2") },
  { path: "/training", label: "训练发布", iconSvg: icon("M12 3v12M7 8l5-5 5 5M5 21h14") },
  { path: "/settings", label: "系统设置", iconSvg: icon("M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z") },
];

function handleLogout() {
  clearAuth();
  router.push('/login');
}
</script>

<style>
.nav-icon {
  display: inline-flex;
  width: 16px;
  height: 16px;
}
.nav-icon svg {
  width: 100%;
  height: 100%;
}
.app-nav-link.is-active {
  background: #0969da;
  color: #fff;
  border-color: #0969da;
}
.app-nav-link.is-idle {
  background: #fff;
  color: #656d76;
  border-color: #d0d7de;
}
.app-nav-link.is-idle:hover {
  background: #f6f8fa;
  color: #1f2328;
  border-color: #afb8c1;
}
.app-nav-link.is-active .nav-icon svg {
  stroke: #fff;
}
</style>

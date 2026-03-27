import { createRouter, createWebHistory } from "vue-router";
import { getToken } from "./services/auth";
import WorkspaceView from "./views/WorkspaceView.vue";
import RunsView from "./views/RunsView.vue";
import MemoryView from "./views/MemoryView.vue";
import RLLabView from "./views/RLLabView.vue";
import TrainingView from "./views/TrainingView.vue";
import HelpCenterView from "./views/HelpCenterView.vue";
import SettingsView from "./views/SettingsView.vue";
import LoginView from "./views/LoginView.vue";

const routes = [
  { path: "/", redirect: "/workspace" },
  { path: "/login", component: LoginView, meta: { public: true } },
  { path: "/workspace", component: WorkspaceView, meta: { keepAlive: true } },
  { path: "/runs", component: RunsView },
  { path: "/memory", component: MemoryView },
  { path: "/rl-lab", component: RLLabView },
  { path: "/training", component: TrainingView },
  { path: "/settings", component: SettingsView },
  { path: "/help", component: HelpCenterView },
  { path: "/metrics", redirect: "/runs" },
  { path: "/artifacts", redirect: "/runs" },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, from, next) => {
  if (to.meta.public) return next();
  const token = getToken();
  if (!token) return next("/login");
  next();
});

export default router;

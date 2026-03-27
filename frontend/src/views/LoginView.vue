<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
    <div class="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
      <h1 class="text-2xl font-bold text-center text-gray-800 mb-2">化工流程模拟智能助手</h1>
      <p class="text-sm text-center text-gray-400 mb-6">AI-Driven Chemical Process Simulation</p>

      <!-- Tab 切换 -->
      <div class="flex border-b border-gray-200 mb-6">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="flex-1 py-2 text-sm font-medium border-b-2 transition-colors"
          :class="activeTab === tab.key ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-400 hover:text-gray-600'"
          @click="switchTab(tab.key)"
        >{{ tab.label }}</button>
      </div>

      <!-- 用户名密码登录 -->
      <div v-if="activeTab === 'login'">
        <div class="space-y-4">
          <div>
            <label class="block text-sm text-gray-600 mb-1">用户名</label>
            <input v-model="loginUser" type="text" placeholder="请输入用户名" class="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm text-gray-800" />
          </div>
          <div>
            <label class="block text-sm text-gray-600 mb-1">密码</label>
            <input v-model="loginPass" type="password" placeholder="请输入密码" class="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm text-gray-800" @keyup.enter="handleLogin" />
          </div>
          <button @click="handleLogin" :disabled="loading" class="w-full py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 text-sm font-medium">
            {{ loading ? '登录中...' : '登录' }}
          </button>
          <p class="text-center text-xs text-gray-400">
            没有账号？
            <button @click="switchTab('register')" class="text-blue-500 hover:underline">立即注册</button>
          </p>
        </div>
      </div>

      <!-- 用户注册 -->
      <div v-if="activeTab === 'register'">
        <div class="space-y-4">
          <div>
            <label class="block text-sm text-gray-600 mb-1">用户名</label>
            <input v-model="regUser" type="text" placeholder="请输入用户名" class="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm text-gray-800" />
          </div>
          <div>
            <label class="block text-sm text-gray-600 mb-1">密码</label>
            <input v-model="regPass" type="password" placeholder="请输入密码（至少6位）" class="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm text-gray-800" />
          </div>
          <div>
            <label class="block text-sm text-gray-600 mb-1">确认密码</label>
            <input v-model="regConfirm" type="password" placeholder="请再次输入密码" class="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 text-sm text-gray-800" @keyup.enter="handleRegister" />
          </div>
          <button @click="handleRegister" :disabled="loading" class="w-full py-2.5 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 text-sm font-medium">
            {{ loading ? '注册中...' : '注册' }}
          </button>
          <p class="text-center text-xs text-gray-400">
            已有账号？
            <button @click="switchTab('login')" class="text-blue-500 hover:underline">返回登录</button>
          </p>
        </div>
      </div>

      <!-- 错误提示 -->
      <p v-if="errorMsg" class="mt-4 text-center text-sm text-red-500">{{ errorMsg }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { setToken, setUser } from '../services/auth';

const router = useRouter();

const tabs = [
  { key: 'login', label: '用户登录' },
  { key: 'register', label: '用户注册' },
];
const activeTab = ref('login');
const loading = ref(false);
const errorMsg = ref('');

const loginUser = ref('');
const loginPass = ref('');

const regUser = ref('');
const regPass = ref('');
const regConfirm = ref('');

function switchTab(key) {
  activeTab.value = key;
  errorMsg.value = '';
}

function resolveApiBase() {
  const host = window.location.hostname || '';
  if (host.includes('dicp.sixseven.ltd')) return 'http://aspenback.dicp.sixseven.ltd:5924';
  if (host === 'localhost' || host === '127.0.0.1') return '';
  const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${protocol}//${host}:38843`;
}

async function apiPost(path, body) {
  const base = resolveApiBase();
  const resp = await fetch(`${base}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
  return data;
}

async function handleLogin() {
  if (!loginUser.value.trim() || !loginPass.value.trim()) { errorMsg.value = '请输入用户名和密码'; return; }
  loading.value = true;
  errorMsg.value = '';
  try {
    const data = await apiPost('/api/auth/login', { phone: loginUser.value.trim(), password: loginPass.value.trim() });
    setToken(data.token);
    setUser(data.user);
    router.push('/workspace');
  } catch (e) { errorMsg.value = e.message; }
  finally { loading.value = false; }
}

async function handleRegister() {
  const username = regUser.value.trim();
  if (!username) { errorMsg.value = '请输入用户名'; return; }
  if (username.toLowerCase() === 'admin') { errorMsg.value = '不能使用 admin 作为用户名'; return; }
  if (!regPass.value.trim() || regPass.value.length < 6) { errorMsg.value = '密码长度不能少于6位'; return; }
  if (regPass.value !== regConfirm.value) { errorMsg.value = '两次密码输入不一致'; return; }
  loading.value = true;
  errorMsg.value = '';
  try {
    const data = await apiPost('/api/auth/register', { phone: username, password: regPass.value.trim() });
    setToken(data.token);
    setUser(data.user);
    router.push('/workspace');
  } catch (e) { errorMsg.value = e.message; }
  finally { loading.value = false; }
}
</script>

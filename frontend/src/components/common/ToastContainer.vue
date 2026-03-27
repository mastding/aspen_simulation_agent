<template>
  <div class="toast-stack">
    <transition-group name="toast">
      <div
        v-for="item in toastStore.items"
        :key="item.id"
        class="toast-card"
        :class="`toast-${item.type}`"
      >
        <div class="toast-body">
          <span class="toast-message">{{ item.message }}</span>
          <button class="toast-close" @click="removeToast(item.id)" aria-label="关闭">×</button>
        </div>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { removeToast, toastStore } from "../../services/toast";
</script>

<style scoped>
.toast-stack {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.toast-card {
  min-width: 280px;
  max-width: 420px;
  border-radius: 12px;
  border: 1px solid #d0d7de;
  background: #ffffff;
  box-shadow: 0 12px 32px rgba(31, 35, 40, 0.14);
  pointer-events: auto;
}

.toast-body {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
}

.toast-message {
  font-size: 13px;
  line-height: 1.5;
  color: #1f2328;
  white-space: pre-wrap;
  word-break: break-word;
}

.toast-close {
  border: none;
  background: transparent;
  color: #656d76;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
}

.toast-success {
  border-color: #1a7f37;
}

.toast-success .toast-message {
  color: #1a7f37;
}

.toast-error {
  border-color: #cf222e;
}

.toast-error .toast-message {
  color: #cf222e;
}

.toast-info {
  border-color: #0969da;
}

.toast-info .toast-message {
  color: #0969da;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.22s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px) translateX(12px);
}
</style>

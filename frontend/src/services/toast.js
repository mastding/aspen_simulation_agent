import { reactive } from "vue";

const TOAST_LIFETIME_MS = 3000;

export const toastStore = reactive({
  items: [],
});

let toastCounter = 0;

export function pushToast({ type = "info", message = "", duration = TOAST_LIFETIME_MS } = {}) {
  const text = String(message || "").trim();
  if (!text) return "";
  const id = `toast_${Date.now()}_${toastCounter++}`;
  toastStore.items.push({
    id,
    type,
    message: text,
  });
  const ttl = Number(duration);
  if (Number.isFinite(ttl) && ttl > 0) {
    window.setTimeout(() => removeToast(id), ttl);
  }
  return id;
}

export function removeToast(id) {
  const idx = toastStore.items.findIndex((item) => item.id === id);
  if (idx >= 0) {
    toastStore.items.splice(idx, 1);
  }
}

export function toastSuccess(message, duration) {
  return pushToast({ type: "success", message, duration });
}

export function toastError(message, duration) {
  return pushToast({ type: "error", message, duration });
}

export function toastInfo(message, duration) {
  return pushToast({ type: "info", message, duration });
}

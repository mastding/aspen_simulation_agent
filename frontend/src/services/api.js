import { getToken } from './auth';

function authHeaders(extra = {}) {
  const token = getToken();
  const headers = { ...extra };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

async function buildError(response) {
  let detail = '';
  try {
    const data = await response.json();
    detail = data?.detail || data?.message || '';
  } catch {
    try {
      detail = await response.text();
    } catch {
      detail = '';
    }
  }
  return new Error(detail || `HTTP ${response.status}: ${response.statusText}`);
}

export async function fetchJson(url) {
  const response = await fetch(url, { headers: authHeaders() });
  if (!response.ok) {
    throw await buildError(response);
  }
  return response.json();
}

export async function postJson(url, data) {
  const response = await fetch(url, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw await buildError(response);
  }
  return response.json();
}

export async function deleteJson(url) {
  const response = await fetch(url, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw await buildError(response);
  }
  return response.json();
}

export function fmtDateTime(dateStr) {
  if (!dateStr) return '-';
  let date;
  // 如果是数字且小于 1e12，说明是秒级时间戳，需要 *1000
  if (typeof dateStr === 'number' && dateStr < 1e12) {
    date = new Date(dateStr * 1000);
  } else {
    date = new Date(dateStr);
  }
  if (isNaN(date.getTime())) return dateStr;
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
}

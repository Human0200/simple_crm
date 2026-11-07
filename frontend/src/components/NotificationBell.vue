<template>
  <div v-if="auth.isAuthenticated" class="bell-wrap" ref="root">
    <button type="button" class="bell-btn" @click="toggle" aria-label="Уведомления">
      <span class="bell-icon">🔔</span>
      <span v-if="unread.total > 0" class="badge">{{ unread.total > 99 ? "99+" : unread.total }}</span>
    </button>

    <div v-if="open" class="dropdown">
      <div class="dropdown-head">Непрочитанные</div>
      <button
        v-for="item in unread.items"
        :key="item.task_id"
        type="button"
        class="dropdown-item"
        @click="openTask(item.task_id)"
      >
        <div class="item-title">{{ item.title }}</div>
        <div class="item-meta">
          <span v-if="item.comments" class="pill">комм. {{ item.comments }}</span>
          <span v-if="item.results" class="pill">рез. {{ item.results }}</span>
          <span v-if="item.timeline" class="pill">таймл. {{ item.timeline }}</span>
          <span v-if="item.email" class="pill">почта {{ item.email }}</span>
        </div>
      </button>
      <p v-if="unread.items.length === 0" class="empty">Нет новых событий</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useUnreadStore } from "../stores/unread";
import { onTaskEvent } from "../realtime";

const auth = useAuthStore();
const unread = useUnreadStore();
const router = useRouter();
const open = ref(false);
const root = ref(null);

function toggle() {
  open.value = !open.value;
  if (open.value) unread.refresh();
}

function openTask(taskId) {
  open.value = false;
  router.push({ name: "board", query: { task: String(taskId) } });
}

function onDocClick(e) {
  if (root.value && !root.value.contains(e.target)) {
    open.value = false;
  }
}

let unsubscribe = null;

onMounted(() => {
  document.addEventListener("click", onDocClick);
  if (auth.isAuthenticated) unread.refresh();
  unsubscribe = onTaskEvent(() => {
    if (auth.isAuthenticated) unread.refresh();
  });
});

onUnmounted(() => {
  document.removeEventListener("click", onDocClick);
  unsubscribe?.();
});

watch(
  () => auth.isAuthenticated,
  (ok) => {
    if (ok) unread.refresh();
    else unread.clear();
  }
);
</script>

<style scoped>
.bell-wrap {
  position: relative;
}

.bell-btn {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.bell-btn:hover {
  background: var(--bg);
}

.bell-icon {
  font-size: 16px;
  line-height: 1;
}

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #de350b;
  color: white;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  width: 320px;
  max-height: 360px;
  overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(9, 30, 66, 0.18);
  z-index: 100;
  padding: 8px;
}

.dropdown-head {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 6px 8px 10px;
}

.dropdown-item {
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  padding: 10px 8px;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dropdown-item:hover {
  background: var(--bg);
}

.item-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.pill {
  font-size: 11px;
  background: #ffebe6;
  color: #bf2600;
  border-radius: 10px;
  padding: 1px 7px;
  font-weight: 600;
}

.empty {
  margin: 0;
  padding: 12px 8px;
  color: var(--text-muted);
  font-size: 13px;
}
</style>

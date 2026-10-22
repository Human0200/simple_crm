<template>
  <div class="calendar-page">
    <header>
      <router-link to="/" class="back-link">← К доске</router-link>
      <div class="month-nav">
        <button class="btn secondary" @click="shiftMonth(-1)">←</button>
        <h1>{{ monthTitle }}</h1>
        <button class="btn secondary" @click="shiftMonth(1)">→</button>
      </div>
      <div></div>
    </header>

    <div class="grid">
      <div class="weekday" v-for="d in weekdays" :key="d">{{ d }}</div>

      <div
        v-for="cell in cells"
        :key="cell.key"
        class="day-cell"
        :class="{ 'other-month': !cell.inMonth, today: cell.isToday, selected: selectedDate === cell.iso }"
        @click="cell.inMonth && selectDate(cell.iso)"
      >
        <span class="day-number">{{ cell.day }}</span>
        <span v-if="cell.count > 0" class="day-count">{{ cell.count }}</span>
      </div>
    </div>

    <div class="day-panel" v-if="selectedDate">
      <h2>{{ formatSelected(selectedDate) }}</h2>
      <p v-if="selectedTasks.length === 0" class="muted">На этот день задач нет</p>
      <div class="task-list">
        <div
          v-for="t in selectedTasks"
          :key="t.id"
          class="task-row"
          @click="openTaskId = t.id"
        >
          <span class="status-dot" :class="t.status"></span>
          <span class="task-title">{{ t.title }}</span>
          <span class="task-status">{{ statusLabel(t.status) }}</span>
        </div>
      </div>
    </div>

    <TaskModal v-if="openTaskId" :taskId="openTaskId" @close="openTaskId = null" @updated="refresh" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { listTasks, STATUSES } from "../api/tasks";
import { onTaskEvent } from "../realtime";
import TaskModal from "../components/TaskModal.vue";

const tasks = ref([]);
const viewDate = ref(new Date());
const today = new Date();
const todayIso = toIso(today);
const selectedDate = ref(null);
const openTaskId = ref(null);

const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

function toIso(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function statusLabel(value) {
  return STATUSES.find((s) => s.value === value)?.label || value;
}

async function refresh() {
  tasks.value = await listTasks();
}

let unsubscribeRealtime = null;
onMounted(() => {
  refresh();
  unsubscribeRealtime = onTaskEvent(() => refresh());
});
onUnmounted(() => {
  unsubscribeRealtime?.();
});

const tasksByDate = computed(() => {
  const map = {};
  for (const t of tasks.value) {
    if (!t.due_date) continue;
    (map[t.due_date] ||= []).push(t);
  }
  return map;
});

const monthTitle = computed(() =>
  viewDate.value.toLocaleDateString("ru-RU", { month: "long", year: "numeric" })
);

const cells = computed(() => {
  const year = viewDate.value.getFullYear();
  const month = viewDate.value.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // Monday = 0
  const gridStart = new Date(year, month, 1 - startOffset);

  const result = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    const iso = toIso(d);
    result.push({
      key: iso,
      iso,
      day: d.getDate(),
      inMonth: d.getMonth() === month,
      isToday: iso === todayIso,
      count: (tasksByDate.value[iso] || []).length,
    });
  }
  return result;
});

const selectedTasks = computed(() =>
  selectedDate.value ? tasksByDate.value[selectedDate.value] || [] : []
);

function shiftMonth(delta) {
  const d = new Date(viewDate.value);
  d.setMonth(d.getMonth() + delta);
  viewDate.value = d;
}

function selectDate(iso) {
  selectedDate.value = iso;
}

function formatSelected(iso) {
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}
</script>

<style scoped>
.calendar-page {
  padding: 24px;
  max-width: 820px;
  margin: 0 auto;
}

header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.back-link {
  color: var(--primary);
  font-size: 13px;
  text-decoration: none;
}

.month-nav {
  display: flex;
  align-items: center;
  gap: 12px;
}

.month-nav h1 {
  font-size: 18px;
  margin: 0;
  text-transform: capitalize;
  min-width: 160px;
  text-align: center;
}

.grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}

.weekday {
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  padding-bottom: 4px;
}

.day-cell {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  min-height: 64px;
  padding: 6px 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.day-cell:hover {
  border-color: var(--primary);
}

.day-cell.other-month {
  opacity: 0.35;
  cursor: default;
}

.day-cell.today .day-number {
  color: var(--primary);
  font-weight: 700;
}

.day-cell.selected {
  border-color: var(--primary);
  background: #e9f2ff;
}

.day-number {
  font-size: 13px;
}

.day-count {
  align-self: flex-start;
  background: var(--primary);
  color: white;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 10px;
}

.day-panel {
  margin-top: 24px;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}

.day-panel h2 {
  font-size: 15px;
  margin: 0 0 10px;
  text-transform: capitalize;
}

.muted {
  color: var(--text-muted);
  font-size: 13px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}

.task-row:hover {
  border-color: var(--primary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #6b778c;
}

.status-dot.backlog {
  background: #6b778c;
}

.status-dot.in_progress {
  background: #0052cc;
}

.status-dot.review {
  background: #ff8b00;
}

.status-dot.done {
  background: #00875a;
}

.task-title {
  flex: 1;
}

.task-status {
  color: var(--text-muted);
  font-size: 12px;
}
</style>

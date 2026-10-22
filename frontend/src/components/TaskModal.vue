<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal" v-if="task">
      <div class="modal-header">
        <h2>{{ task.title }}</h2>
        <div class="header-actions">
          <button v-if="isCreator" type="button" class="btn secondary edit-btn" @click="$emit('edit', task)">
            Редактировать
          </button>
          <button class="close-btn" @click="$emit('close')" aria-label="Закрыть">×</button>
        </div>
      </div>

      <p class="description">{{ task.description || "Без описания" }}</p>
      <p v-if="task.due_date" class="due-date">Срок: {{ formatDueDate(task.due_date) }}</p>

      <div class="people">
        <div class="people-row">
          <span class="people-label">Постановщик</span>
          <span class="chip chip-creator">{{ userLabel(task.creator) }}</span>
        </div>
        <div class="people-row">
          <span class="people-label">Исполнители</span>
          <span v-if="task.assignees.length === 0" class="muted">—</span>
          <span v-for="u in task.assignees" :key="u.id" class="chip chip-assignee">{{ userLabel(u) }}</span>
        </div>
        <div class="people-row">
          <span class="people-label">Наблюдатели</span>
          <span v-if="task.observers.length === 0" class="muted">—</span>
          <span v-for="u in task.observers" :key="u.id" class="chip chip-observer">{{ userLabel(u) }}</span>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Статус</div>

        <div v-if="canChangeStatus" class="status-buttons">
          <button
            v-for="s in STATUSES"
            :key="s.value"
            type="button"
            class="status-btn"
            :class="{ active: task.status === s.value }"
            :disabled="!isStatusSelectable(s.value) || statusLoading"
            :title="!isStatusSelectable(s.value) ? 'Только постановщик может перевести задачу в этот статус' : ''"
            @click="pickStatus(s.value)"
          >
            {{ s.label }}
          </button>
        </div>
        <div v-else class="current-status-badge">{{ statusLabel(task.status) }}</div>

        <p v-if="canChangeStatus && !lastCommentIsResult" class="result-hint">
          Чтобы перевести задачу в «На проверку» или «Готово», отметьте последний комментарий как результат.
        </p>
        <p v-if="statusError" class="error-text">{{ statusError }}</p>
      </div>

      <div class="section">
        <div class="tabs">
          <button
            type="button"
            class="tab"
            :class="{ active: activeTab === 'comments' }"
            @click="activeTab = 'comments'"
          >
            Комментарии
          </button>
          <button
            type="button"
            class="tab"
            :class="{ active: activeTab === 'results' }"
            @click="activeTab = 'results'"
          >
            Результаты
            <span v-if="resultComments.length" class="tab-count">{{ resultComments.length }}</span>
          </button>
        </div>

        <div class="comments">
          <div
            v-for="c in visibleComments"
            :key="c.id"
            class="comment"
            :class="{ system: c.is_status_change, result: c.is_result }"
          >
            <div class="comment-head">
              <strong>{{ c.author.full_name }}</strong>
              <span class="time">{{ formatDate(c.created_at) }}</span>
            </div>
            <div v-if="c.is_status_change" class="status-change-line">
              Статус изменён: {{ statusLabel(c.from_status) }} → {{ statusLabel(c.to_status) }}
            </div>
            <div class="comment-text">{{ c.text }}</div>
            <div class="comment-footer">
              <span v-if="c.is_result" class="result-badge">★ Результат</span>
              <button
                v-if="canMarkResult(c)"
                type="button"
                class="toggle-result-btn"
                @click="toggleResult(c)"
              >
                {{ c.is_result ? "Снять отметку" : "Отметить результатом" }}
              </button>
            </div>
          </div>
          <p v-if="visibleComments.length === 0 && activeTab === 'comments'" class="muted">
            Пока нет комментариев
          </p>
          <p v-if="visibleComments.length === 0 && activeTab === 'results'" class="muted">
            Пока нет отмеченных результатов
          </p>
        </div>

        <form v-if="activeTab === 'comments'" class="new-comment" @submit.prevent="submitComment">
          <textarea
            v-model="commentText"
            rows="2"
            placeholder="Добавить комментарий..."
            required
          ></textarea>
          <label class="result-checkbox">
            <input type="checkbox" v-model="commentIsResult" />
            Отметить как результат
          </label>
          <button class="btn" type="submit" :disabled="commentLoading">Отправить</button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { getTask, addComment, setCommentResult, changeStatus, STATUSES } from "../api/tasks";
import { onTaskEvent } from "../realtime";
import { useAuthStore } from "../stores/auth";

const props = defineProps({
  taskId: { type: Number, required: true },
});
const emit = defineEmits(["close", "updated", "edit"]);

const auth = useAuthStore();
const task = ref(null);
const commentText = ref("");
const commentIsResult = ref(false);
const commentLoading = ref(false);
const statusError = ref("");
const statusLoading = ref(false);
const activeTab = ref("comments");

const ASSIGNEE_ALLOWED_STATUSES = ["backlog", "in_progress", "review"];
const REQUIRES_RESULT_STATUSES = ["review", "done"];

const isCreator = computed(() => task.value && task.value.creator.id === auth.user.id);

const canChangeStatus = computed(() => {
  if (!task.value) return false;
  const uid = auth.user.id;
  return (
    task.value.creator.id === uid ||
    task.value.assignees.some((u) => u.id === uid)
  );
});

const lastCommentIsResult = computed(() => {
  if (!task.value || task.value.comments.length === 0) return false;
  return task.value.comments[task.value.comments.length - 1].is_result;
});

function isStatusSelectable(value) {
  if (isCreator.value) return true;
  return ASSIGNEE_ALLOWED_STATUSES.includes(value);
}

const resultComments = computed(() =>
  task.value ? task.value.comments.filter((c) => c.is_result) : []
);

const visibleComments = computed(() =>
  activeTab.value === "results" ? resultComments.value : task.value?.comments || []
);

function canMarkResult(comment) {
  if (!task.value || comment.is_status_change) return false;
  return comment.author.id === auth.user.id || isCreator.value;
}

function statusLabel(value) {
  return STATUSES.find((s) => s.value === value)?.label || value;
}

function userLabel(user) {
  if (!user.teams || user.teams.length === 0) return user.full_name;
  return `${user.full_name} (${user.teams.map((t) => t.name).join(", ")})`;
}

function formatDate(iso) {
  return new Date(iso + "Z").toLocaleString("ru-RU");
}

function formatDueDate(isoDate) {
  return new Date(isoDate).toLocaleDateString("ru-RU");
}

async function load() {
  task.value = await getTask(props.taskId);
}
load();

watch(
  () => props.taskId,
  () => load()
);

let unsubscribeRealtime = null;
onMounted(() => {
  unsubscribeRealtime = onTaskEvent((event) => {
    if (event.task_id === props.taskId) {
      load();
    }
  });
});
onUnmounted(() => {
  unsubscribeRealtime?.();
});

async function submitComment() {
  commentLoading.value = true;
  try {
    task.value = await addComment(props.taskId, commentText.value, commentIsResult.value);
    commentText.value = "";
    commentIsResult.value = false;
    emit("updated", task.value);
  } finally {
    commentLoading.value = false;
  }
}

async function toggleResult(comment) {
  task.value = await setCommentResult(props.taskId, comment.id, !comment.is_result);
  emit("updated", task.value);
}

async function pickStatus(value) {
  if (value === task.value.status) return;
  statusError.value = "";
  if (REQUIRES_RESULT_STATUSES.includes(value) && !lastCommentIsResult.value) {
    statusError.value = `Чтобы перевести задачу в «${statusLabel(value)}», отметьте последний комментарий как результат`;
    return;
  }
  statusLoading.value = true;
  try {
    task.value = await changeStatus(props.taskId, value);
    emit("updated", task.value);
  } catch (e) {
    statusError.value = e.response?.data?.detail || "Не удалось изменить статус";
  } finally {
    statusLoading.value = false;
  }
}
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(9, 30, 66, 0.54);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 24px;
}

.modal {
  background: var(--surface);
  border-radius: 10px;
  padding: 28px;
  width: 560px;
  max-height: 88vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

h2 {
  margin: 0;
  font-size: 19px;
  line-height: 1.3;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.edit-btn {
  font-size: 12px;
  padding: 6px 10px;
}

.close-btn {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--text-muted);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.close-btn:hover {
  background: var(--bg);
  color: var(--text);
}

.description {
  margin: -12px 0 0;
  color: var(--text-muted);
  white-space: pre-wrap;
  font-size: 14px;
}

.due-date {
  margin: -8px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.people {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}

.people-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.people-label {
  width: 90px;
  flex-shrink: 0;
  color: var(--text-muted);
  font-weight: 600;
}

.chip {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  color: white;
}

.chip-creator {
  background: #6554c0;
}

.chip-assignee {
  background: #0052cc;
}

.chip-observer {
  background: #6b778c;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}

.section-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.03em;
}

.status-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.status-btn {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  padding: 8px 14px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
}

.status-btn:hover {
  border-color: var(--primary);
}

.status-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.status-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.status-btn:disabled:hover {
  border-color: var(--border);
}

.current-status-badge {
  display: inline-block;
  align-self: flex-start;
  background: var(--primary);
  color: white;
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
}

.result-hint {
  margin: 0;
  font-size: 12px;
  color: #974f00;
  background: #fffae6;
  border: 1px solid #ffe380;
  border-radius: 6px;
  padding: 8px 10px;
}

.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border);
  margin-bottom: -2px;
}

.tab {
  border: none;
  background: transparent;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 2px solid transparent;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

.tab-count {
  background: var(--bg);
  border-radius: 10px;
  padding: 0 7px;
  font-size: 11px;
}

.comments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
}

.comment {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
}

.comment.system {
  background: #f4f5f7;
}

.comment.result {
  border-color: #ffab00;
  background: #fffae6;
}

.comment-head {
  display: flex;
  justify-content: space-between;
  color: var(--text-muted);
  font-size: 12px;
  margin-bottom: 4px;
}

.status-change-line {
  font-weight: 600;
  margin-bottom: 4px;
}

.comment-text {
  white-space: pre-wrap;
}

.comment-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}

.result-badge {
  color: #974f00;
  font-size: 12px;
  font-weight: 700;
}

.toggle-result-btn {
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 12px;
  padding: 0;
  margin-left: auto;
}

.toggle-result-btn:hover {
  text-decoration: underline;
}

.muted {
  color: var(--text-muted);
  font-size: 13px;
}

.new-comment {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: stretch;
}

.new-comment textarea {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  resize: vertical;
}

.result-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
}

.new-comment .btn {
  align-self: flex-end;
}
</style>

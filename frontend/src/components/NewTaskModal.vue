<template>
  <div class="overlay" @click.self="$emit('close')">
    <form class="modal" @submit.prevent="submit">
      <div class="modal-header">
        <h2>{{ isEdit ? "Редактировать задачу" : "Новая задача" }}</h2>
        <button type="button" class="close-btn" @click="$emit('close')" aria-label="Закрыть">×</button>
      </div>

      <div class="field">
        <label for="title">Название</label>
        <input id="title" v-model="title" type="text" placeholder="Например: Позвонить клиенту" required autofocus />
      </div>

      <div class="field">
        <label for="description">Описание</label>
        <textarea id="description" v-model="description" rows="4" placeholder="Детали задачи (необязательно)"></textarea>
      </div>

      <div class="field">
        <label for="due_date">Срок выполнения</label>
        <input id="due_date" v-model="dueDate" type="date" />
      </div>

      <div class="field">
        <label for="client">Клиент (необязательно)</label>
        <select id="client" v-model="clientId">
          <option value="">Без клиента</option>
          <option v-for="c in clients" :key="c.id" :value="c.id">
            {{ c.name }}<template v-if="c.company"> — {{ c.company }}</template>
          </option>
        </select>
      </div>

      <div v-if="auth.user.is_admin" class="field">
        <label for="creator">Постановщик</label>
        <p class="hint">Админ может указать любого пользователя как постановщика задачи</p>
        <select id="creator" v-model="creatorId">
          <option v-for="u in allUsers" :key="u.id" :value="u.id">{{ userLabel(u) }}</option>
        </select>
      </div>

      <div class="field-row">
        <div class="field half">
          <label>Исполнители</label>
          <p class="hint">Кто будет выполнять задачу</p>
          <div class="people-list">
            <label v-for="u in assignableUsers" :key="'a' + u.id" class="people-item">
              <input type="checkbox" v-model="assigneeIds" :value="u.id" />
              <Avatar :user="u" :size="24" />
              <span>{{ userLabel(u) }}</span>
            </label>
            <p v-if="assignableUsers.length === 0" class="muted-note">
              Нет доступных исполнителей — обратитесь к администратору
            </p>
          </div>
        </div>

        <div class="field half">
          <label>Наблюдатели</label>
          <p class="hint">Кто будет следить за задачей</p>
          <div class="people-list">
            <label v-for="u in users" :key="'o' + u.id" class="people-item">
              <input type="checkbox" v-model="observerIds" :value="u.id" />
              <Avatar :user="u" :size="24" />
              <span>{{ userLabel(u) }}</span>
            </label>
            <p v-if="users.length === 0" class="muted-note">
              Нет доступных наблюдателей из связанных команд
            </p>
          </div>
        </div>
      </div>

      <p v-if="error" class="error-text">{{ error }}</p>

      <div class="actions">
        <button type="button" class="btn secondary" @click="$emit('close')">Отмена</button>
        <button type="submit" class="btn" :disabled="loading">
          {{ loading ? "Сохранение..." : isEdit ? "Сохранить изменения" : "Создать задачу" }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { createTask, updateTask } from "../api/tasks";
import { useAuthStore } from "../stores/auth";
import Avatar from "./Avatar.vue";

const props = defineProps({
  users: { type: Array, required: true },
  assignableUsers: { type: Array, required: true },
  allUsers: { type: Array, default: () => [] },
  clients: { type: Array, default: () => [] },
  task: { type: Object, default: null },
  funnelId: { type: Number, default: null },
});
const emit = defineEmits(["close", "created", "saved"]);

const auth = useAuthStore();

const isEdit = computed(() => !!props.task);

const title = ref(props.task?.title || "");
const description = ref(props.task?.description || "");
const dueDate = ref(props.task?.due_date || "");
const clientId = ref(props.task?.client?.id ?? "");
const creatorId = ref(props.task?.creator?.id || auth.user.id);
const assigneeIds = ref(props.task ? props.task.assignees.map((u) => u.id) : []);
const observerIds = ref(props.task ? props.task.observers.map((u) => u.id) : []);
const error = ref("");
const loading = ref(false);

function userLabel(user) {
  if (!user.teams || user.teams.length === 0) return user.full_name;
  return `${user.full_name} (${user.teams.map((t) => t.name).join(", ")})`;
}

async function submit() {
  error.value = "";
  loading.value = true;
  const payload = {
    title: title.value,
    description: description.value,
    due_date: dueDate.value || null,
    assignee_ids: assigneeIds.value,
    observer_ids: observerIds.value,
    client_id: clientId.value === "" || clientId.value == null ? null : Number(clientId.value),
  };
  if (auth.user.is_admin && !isEdit.value) {
    payload.creator_id = creatorId.value;
  }
  if (!isEdit.value && props.funnelId) {
    payload.funnel_id = props.funnelId;
  }
  try {
    if (isEdit.value) {
      const task = await updateTask(props.task.id, payload);
      emit("saved", task);
    } else {
      const task = await createTask(payload);
      emit("created", task);
    }
  } catch (e) {
    error.value = e.response?.data?.detail || "Не удалось сохранить задачу";
  } finally {
    loading.value = false;
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
  max-height: 90vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

h2 {
  margin: 0;
  font-size: 19px;
}

.close-btn {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--text-muted);
  padding: 2px 6px;
  border-radius: 4px;
}

.close-btn:hover {
  background: var(--bg);
  color: var(--text);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 13px;
  font-weight: 600;
}

.hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.muted-note {
  margin: 4px 2px;
  font-size: 12px;
  color: var(--text-muted);
}

input[type="text"],
input[type="date"],
textarea {
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 6px;
  width: 100%;
  font-size: 14px;
}

input[type="date"] {
  width: auto;
}

select {
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 14px;
}

textarea {
  resize: vertical;
}

.field-row {
  display: flex;
  gap: 16px;
}

.field.half {
  flex: 1;
  min-width: 0;
}

.people-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 160px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px;
}

.people-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 400;
  font-size: 13px;
  padding: 4px 6px;
  border-radius: 4px;
}

.people-item:hover {
  background: var(--bg);
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}
</style>

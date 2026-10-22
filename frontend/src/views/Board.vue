<template>
  <div class="board-page">
    <header>
      <h1>Simple CRM</h1>
      <div class="header-right">
        <router-link to="/calendar" class="btn secondary">Календарь</router-link>
        <router-link v-if="auth.user.is_admin" to="/admin" class="btn secondary">Админ</router-link>
        <router-link to="/profile" class="profile-link">
          <Avatar :user="auth.user" :size="32" />
          <span class="whoami">{{ auth.user.full_name }}</span>
        </router-link>
        <button class="btn secondary" @click="logout">Выйти</button>
      </div>
    </header>

    <div class="toolbar">
      <button v-if="auth.user.role === 'creator'" class="btn" @click="showNewTask = true">
        + Новая задача
      </button>
      <p v-else class="executor-note">Ваша роль не позволяет ставить задачи.</p>
    </div>

    <div class="columns">
      <div
        class="column"
        v-for="status in STATUSES"
        :key="status.value"
        :class="{ 'drop-target': dragOverStatus === status.value }"
        @dragover.prevent="dragOverStatus = status.value"
        @dragleave="onDragLeave(status.value)"
        @drop.prevent="onDrop(status.value)"
      >
        <div class="column-title">
          {{ status.label }}
          <span class="count">{{ tasksByStatus(status.value).length }}</span>
        </div>
        <TaskCard
          v-for="task in tasksByStatus(status.value)"
          :key="task.id"
          :task="task"
          :can-drag="canChangeStatus(task)"
          @open="openTask"
          @drag="draggingTaskId = $event"
        />
        <p v-if="tasksByStatus(status.value).length === 0" class="empty">Пусто</p>
      </div>
    </div>

    <NewTaskModal
      v-if="showNewTask"
      :users="users"
      :assignable-users="assignableUsers"
      :all-users="allUsers"
      @close="showNewTask = false"
      @created="onCreated"
    />

    <NewTaskModal
      v-if="editingTask"
      :users="users"
      :assignable-users="assignableUsers"
      :all-users="allUsers"
      :task="editingTask"
      @close="editingTask = null"
      @saved="onSaved"
    />

    <TaskModal
      v-if="openTaskId"
      :taskId="openTaskId"
      @close="openTaskId = null"
      @updated="onUpdated"
      @edit="onEditRequested"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import {
  listTasks,
  listUsers,
  listAssignableUsers,
  listObservableUsers,
  changeStatus,
  STATUSES,
} from "../api/tasks";
import { onTaskEvent } from "../realtime";
import TaskCard from "../components/TaskCard.vue";
import NewTaskModal from "../components/NewTaskModal.vue";
import TaskModal from "../components/TaskModal.vue";
import Avatar from "../components/Avatar.vue";

const auth = useAuthStore();
const router = useRouter();

const tasks = ref([]);
const users = ref([]);
const allUsers = ref([]);
const assignableUsers = ref([]);
const showNewTask = ref(false);
const openTaskId = ref(null);
const editingTask = ref(null);

const draggingTaskId = ref(null);
const dragOverStatus = ref(null);

function tasksByStatus(status) {
  return tasks.value.filter((t) => t.status === status);
}

const ASSIGNEE_ALLOWED_STATUSES = ["backlog", "in_progress", "review"];

function canChangeStatus(task) {
  const uid = auth.user.id;
  return task.creator.id === uid || task.assignees.some((u) => u.id === uid);
}

function canSetStatus(task, toStatus) {
  const uid = auth.user.id;
  if (task.creator.id === uid) return true;
  if (!task.assignees.some((u) => u.id === uid)) return false;
  return ASSIGNEE_ALLOWED_STATUSES.includes(toStatus);
}

async function refresh() {
  tasks.value = await listTasks();
}

let unsubscribeRealtime = null;

onMounted(async () => {
  await auth.refreshUser();
  await refresh();
  users.value = await listObservableUsers();
  allUsers.value = await listUsers();
  assignableUsers.value = await listAssignableUsers();
  unsubscribeRealtime = onTaskEvent(() => refresh());
});

onUnmounted(() => {
  unsubscribeRealtime?.();
});

function openTask(id) {
  openTaskId.value = id;
}

function onCreated() {
  showNewTask.value = false;
  refresh();
}

function onUpdated() {
  refresh();
}

function onEditRequested(task) {
  openTaskId.value = null;
  editingTask.value = task;
}

function onSaved() {
  editingTask.value = null;
  refresh();
}

function onDragLeave(status) {
  if (dragOverStatus.value === status) {
    dragOverStatus.value = null;
  }
}

async function onDrop(toStatus) {
  dragOverStatus.value = null;
  const task = tasks.value.find((t) => t.id === draggingTaskId.value);
  draggingTaskId.value = null;
  if (!task || task.status === toStatus || !canSetStatus(task, toStatus)) return;

  try {
    await changeStatus(task.id, toStatus);
    await refresh();
  } catch (e) {
    alert(e.response?.data?.detail || "Не удалось изменить статус");
  }
}

function logout() {
  auth.logout();
  router.push({ name: "login" });
}
</script>

<style scoped>
.board-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar {
  margin-bottom: 16px;
}

.executor-note {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

h1 {
  font-size: 20px;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.profile-link {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--text);
}

.whoami {
  font-size: 13px;
  color: var(--text-muted);
}

.columns {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.column {
  background: #ebecf0;
  border-radius: 6px;
  padding: 10px;
  min-height: 200px;
  border: 2px dashed transparent;
  transition: border-color 0.1s;
}

.column.drop-target {
  border-color: var(--primary);
}

.column-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  color: var(--text-muted);
  text-transform: uppercase;
}

.count {
  background: #dfe1e6;
  border-radius: 10px;
  padding: 0 8px;
}

.empty {
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
  margin-top: 20px;
}
</style>

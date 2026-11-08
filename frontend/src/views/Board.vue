<template>
  <div class="board-page">
    <header>
      <h1>Simple CRM</h1>
      <div class="header-right">
        <router-link to="/clients" class="btn secondary">Клиенты</router-link>
        <router-link to="/calendar" class="btn secondary">Календарь</router-link>
        <router-link v-if="auth.user.is_admin" to="/admin" class="btn secondary">Админ</router-link>
        <router-link to="/profile" class="profile-link">
          <Avatar :user="auth.user" :size="32" />
          <span class="whoami">{{ auth.user.full_name }}</span>
        </router-link>
        <button class="btn secondary" @click="logout">Выйти</button>
        <NotificationBell />
      </div>
    </header>

    <div class="funnel-tabs" v-if="funnels.length">
      <button
        v-for="f in funnels"
        :key="f.id"
        type="button"
        class="funnel-tab"
        :class="{ active: selectedFunnelId === f.id }"
        @click="selectFunnel(f.id)"
      >
        {{ f.name }}
        <span v-if="f.team" class="funnel-team">{{ f.team.name }}</span>
        <span v-if="(unreadByFunnel[f.id] || 0) > 0" class="funnel-unread">
          {{ unreadByFunnel[f.id] > 99 ? "99+" : unreadByFunnel[f.id] }}
        </span>
      </button>
    </div>

    <div class="toolbar">
      <button v-if="canCreateTask" class="btn" @click="showNewTask = true">
        + Новая задача
      </button>
      <p v-else class="executor-note">Ваша роль не позволяет ставить задачи.</p>
      <div v-if="auth.user.is_admin" class="stage-tools">
        <input v-model="newStageName" type="text" placeholder="Новая стадия" @keyup.enter="addStage" />
        <button type="button" class="btn secondary" :disabled="!newStageName.trim() || stageLoading" @click="addStage">
          + Стадия
        </button>
      </div>
    </div>
    <p v-if="stageError" class="error-text">{{ stageError }}</p>

    <div class="columns" :style="{ gridTemplateColumns: `repeat(${Math.max(stages.length, 1)}, minmax(200px, 1fr))` }">
      <div
        class="column"
        v-for="stage in stages"
        :key="stage.id"
        :class="{ 'drop-target': dragOverStageId === stage.id }"
        @dragover.prevent="dragOverStageId = stage.id"
        @dragleave="onDragLeave(stage.id)"
        @drop.prevent="onDrop(stage)"
      >
        <div class="column-title">
          <span>{{ stage.name }}</span>
          <span class="count">{{ tasksByStage(stage.id).length }}</span>
        </div>
        <TaskCard
          v-for="task in tasksByStage(stage.id)"
          :key="task.id"
          :task="task"
          :can-drag="canChangeStatus(task)"
          @open="openTask"
          @drag="draggingTaskId = $event"
        />
        <p v-if="tasksByStage(stage.id).length === 0" class="empty">Пусто</p>
      </div>
    </div>

    <NewTaskModal
      v-if="showNewTask"
      :users="users"
      :assignable-users="assignableUsers"
      :all-users="allUsers"
      :clients="clients"
      :funnel-id="selectedFunnelId"
      @close="showNewTask = false"
      @created="onCreated"
    />

    <NewTaskModal
      v-if="editingTask"
      :users="users"
      :assignable-users="assignableUsers"
      :all-users="allUsers"
      :clients="clients"
      :task="editingTask"
      @close="editingTask = null"
      @saved="onSaved"
    />

    <TaskModal
      v-if="openTaskId"
      :taskId="openTaskId"
      :stages="stages"
      @close="closeTask"
      @updated="onUpdated"
      @deleted="onDeleted"
      @edit="onEditRequested"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useUnreadStore } from "../stores/unread";
import {
  listTasks,
  listUsers,
  listAssignableUsers,
  listObservableUsers,
  changeStatus,
} from "../api/tasks";
import { listStages, createStage } from "../api/stages";
import { listFunnels, getPreferredFunnel } from "../api/funnels";
import { listClients } from "../api/clients";
import { onTaskEvent } from "../realtime";
import TaskCard from "../components/TaskCard.vue";
import NewTaskModal from "../components/NewTaskModal.vue";
import TaskModal from "../components/TaskModal.vue";
import Avatar from "../components/Avatar.vue";
import NotificationBell from "../components/NotificationBell.vue";

const auth = useAuthStore();
const unreadStore = useUnreadStore();
const router = useRouter();
const route = useRoute();
const canCreateTask = computed(
  () => auth.user?.is_admin || !!auth.capabilities?.can_create
);

const tasks = ref([]);
const allTasks = ref([]);
const stages = ref([]);
const funnels = ref([]);
const selectedFunnelId = ref(null);
const users = ref([]);
const allUsers = ref([]);
const assignableUsers = ref([]);
const clients = ref([]);
const showNewTask = ref(false);
const openTaskId = ref(null);
const editingTask = ref(null);
const newStageName = ref("");
const stageLoading = ref(false);
const stageError = ref("");

const draggingTaskId = ref(null);
const dragOverStageId = ref(null);

const stageIdSet = computed(() => new Set(stages.value.map((s) => s.id)));

function tasksByStage(stageId) {
  return tasks.value.filter((t) => t.stage_id === stageId || t.stage?.id === stageId);
}

const unreadByFunnel = computed(() => {
  const map = {};
  for (const f of funnels.value) {
    let total = unreadStore.forFunnel(f.id);
    if (!total) {
      total = (allTasks.value || []).reduce((sum, t) => {
        if (Number(t.stage?.funnel_id) !== Number(f.id)) return sum;
        return sum + (unreadStore.forTask(t.id)?.total || t.unread?.total || 0);
      }, 0);
    }
    map[f.id] = total;
  }
  return map;
});

function canChangeStatus(task) {
  const uid = auth.user.id;
  // админ может всегда; остальные — только постановщик или исполнитель
  if (auth.user.is_admin) return true;
  return task.creator.id === uid || task.assignees.some((u) => u.id === uid);
}

function canSetStage(task, stage) {
  const uid = auth.user.id;
  if (auth.user.is_admin || task.creator.id === uid) return true;
  if (!task.assignees.some((u) => u.id === uid)) return false;
  return !!stage.assignee_can_set;
}

async function loadFunnels() {
  const [list, preferred] = await Promise.all([listFunnels(), getPreferredFunnel()]);
  funnels.value = list;
  if (!selectedFunnelId.value || !list.some((f) => f.id === selectedFunnelId.value)) {
    selectedFunnelId.value = preferred?.id || list[0]?.id || null;
  }
}

async function selectFunnel(id) {
  selectedFunnelId.value = id;
  await refreshStagesAndTasks();
}

async function refreshStagesAndTasks() {
  const funnelId = selectedFunnelId.value;
  const [t, s] = await Promise.all([
    listTasks(),
    funnelId ? listStages(funnelId) : listStages(),
  ]);
  allTasks.value = t;
  const ids = new Set(s.map((x) => x.id));
  tasks.value = t.filter((task) => ids.has(task.stage_id) || ids.has(task.stage?.id));
  stages.value = s;
  unreadStore.hydrateFromTasks(tasks.value);
  await unreadStore.refresh();
}

async function refresh() {
  await loadFunnels();
  await refreshStagesAndTasks();
}

function openFromQuery() {
  const raw = route.query.task;
  if (!raw) return;
  const id = Number(raw);
  if (Number.isFinite(id) && id > 0) {
    openTaskId.value = id;
  }
}

let unsubscribeRealtime = null;

onMounted(async () => {
  await auth.refreshUser();
  await refresh();
  users.value = await listObservableUsers();
  allUsers.value = await listUsers();
  assignableUsers.value = await listAssignableUsers();
  clients.value = await listClients();
  openFromQuery();
  unsubscribeRealtime = onTaskEvent(() => refresh());
});

onUnmounted(() => {
  unsubscribeRealtime?.();
});

watch(
  () => route.query.task,
  () => openFromQuery()
);

function openTask(id) {
  openTaskId.value = id;
}

function closeTask() {
  openTaskId.value = null;
  if (route.query.task) {
    const q = { ...route.query };
    delete q.task;
    router.replace({ query: q });
  }
}

function onCreated() {
  showNewTask.value = false;
  refresh();
}

function onUpdated() {
  refresh();
}

function onDeleted() {
  closeTask();
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

function onDragLeave(stageId) {
  if (dragOverStageId.value === stageId) {
    dragOverStageId.value = null;
  }
}

async function onDrop(stage) {
  dragOverStageId.value = null;
  const task = tasks.value.find((t) => t.id === draggingTaskId.value);
  draggingTaskId.value = null;
  if (!task || task.stage_id === stage.id || !canSetStage(task, stage)) return;

  try {
    await changeStatus(task.id, stage.id);
    await refresh();
  } catch (e) {
    alert(e.response?.data?.detail || "Не удалось изменить стадию");
  }
}

async function addStage() {
  stageError.value = "";
  const name = newStageName.value.trim();
  if (!name || !selectedFunnelId.value) return;
  stageLoading.value = true;
  try {
    await createStage({ name, funnel_id: selectedFunnelId.value });
    newStageName.value = "";
    await refreshStagesAndTasks();
  } catch (e) {
    stageError.value = e.response?.data?.detail || "Не удалось создать стадию";
  } finally {
    stageLoading.value = false;
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
  max-width: 1400px;
  margin: 0 auto;
}

.funnel-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.funnel-tab {
  position: relative;
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  color: var(--text);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.funnel-tab.active {
  background: var(--text);
  color: #fff;
  border-color: var(--text);
}

.funnel-team {
  opacity: 0.7;
  font-size: 11px;
}

.funnel-unread {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #de350b;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.funnel-tab.active .funnel-unread {
  background: #ff5630;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.stage-tools {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.stage-tools input {
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
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
  gap: 16px;
  overflow-x: auto;
  padding-bottom: 8px;
}

.column {
  background: #ebecf0;
  border-radius: 6px;
  padding: 10px;
  min-height: 200px;
  min-width: 200px;
}

.column.drop-target {
  outline: 2px dashed var(--primary);
}

.column-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.count {
  background: rgba(9, 30, 66, 0.08);
  border-radius: 10px;
  padding: 0 7px;
  font-size: 11px;
}

.empty {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  margin: 20px 0;
}
</style>

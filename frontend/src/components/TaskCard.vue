<template>
  <div
    class="task-card"
    :class="{ draggable: canDrag }"
    :draggable="canDrag"
    @click="$emit('open', task.id)"
    @dragstart="onDragStart"
  >
    <span v-if="unreadTotal > 0" class="unread-badge">{{ unreadTotal > 99 ? "99+" : unreadTotal }}</span>
    <div class="title">{{ task.title }}</div>
    <div v-if="task.client" class="client-tag">{{ task.client.name }}</div>
    <div v-if="task.description" class="description">{{ task.description }}</div>

    <div class="footer">
      <div class="meta">
        <Avatar :user="task.creator" :size="22" :title="'Постановщик: ' + userLabel(task.creator)" />
        <template v-if="task.assignees?.length">
          <span class="assign-arrow" title="поставил задачу →">→</span>
          <Avatar
            v-for="a in task.assignees"
            :key="'a' + a.id"
            :user="a"
            :size="22"
            :title="'Исполнитель: ' + userLabel(a)"
          />
        </template>
        <template v-if="task.observers?.length">
          <span v-if="task.assignees?.length" class="meta-sep" aria-hidden="true">·</span>
          <Avatar
            v-for="o in task.observers"
            :key="'o' + o.id"
            :user="o"
            :size="22"
            :title="'Наблюдатель: ' + userLabel(o)"
          />
        </template>
      </div>
      <span v-if="task.due_date" class="due-date">до {{ formatDueDate(task.due_date) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import Avatar from "./Avatar.vue";
import { useUnreadStore } from "../stores/unread";

const props = defineProps({
  task: { type: Object, required: true },
  canDrag: { type: Boolean, default: false },
});
const emit = defineEmits(["open", "drag"]);
const unreadStore = useUnreadStore();

const unreadTotal = computed(() => {
  const fromStore = unreadStore.forTask(props.task.id)?.total || 0;
  const fromTask = props.task.unread?.total || 0;
  return Math.max(fromStore, fromTask);
});

function onDragStart(e) {
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", String(props.task.id));
  emit("drag", props.task.id);
}

function formatDueDate(isoDate) {
  return new Date(isoDate).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function userLabel(user) {
  if (!user.teams || user.teams.length === 0) return user.full_name;
  return `${user.full_name} (${user.teams.map((t) => t.name).join(", ")})`;
}
</script>

<style scoped>
.client-tag {
  font-size: 11px;
  font-weight: 600;
  color: #403294;
  background: #eae6ff;
  align-self: flex-start;
  padding: 2px 8px;
  border-radius: 10px;
  margin-top: 2px;
}

.task-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(9, 30, 66, 0.08);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-card:hover {
  border-color: var(--primary);
}

.task-card.draggable {
  cursor: grab;
}

.task-card.draggable:active {
  cursor: grabbing;
}

.unread-badge {
  position: absolute;
  top: -6px;
  right: -6px;
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
  z-index: 2;
}

.title {
  font-size: 14px;
  margin-bottom: 4px;
  padding-right: 12px;
}

.description {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.footer {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
}

.meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.assign-arrow {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  user-select: none;
}

.meta-sep {
  color: var(--border);
  font-size: 12px;
  line-height: 1;
  user-select: none;
}

.due-date {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  flex-shrink: 0;
}
</style>

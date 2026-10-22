<template>
  <div
    class="task-card"
    :class="{ draggable: canDrag }"
    :draggable="canDrag"
    @click="$emit('open', task.id)"
    @dragstart="onDragStart"
  >
    <div class="title">{{ task.title }}</div>
    <div v-if="task.description" class="description">{{ task.description }}</div>

    <div class="footer">
      <div class="meta">
        <Avatar :user="task.creator" :size="22" :title="'Постановщик: ' + userLabel(task.creator)" />
        <Avatar
          v-for="a in task.assignees"
          :key="'a' + a.id"
          :user="a"
          :size="22"
          :title="'Исполнитель: ' + userLabel(a)"
        />
        <Avatar
          v-for="o in task.observers"
          :key="'o' + o.id"
          :user="o"
          :size="22"
          :title="'Наблюдатель: ' + userLabel(o)"
        />
      </div>
      <span v-if="task.due_date" class="due-date">до {{ formatDueDate(task.due_date) }}</span>
    </div>
  </div>
</template>

<script setup>
import Avatar from "./Avatar.vue";

const props = defineProps({
  task: { type: Object, required: true },
  canDrag: { type: Boolean, default: false },
});
const emit = defineEmits(["open", "drag"]);

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
.task-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(9, 30, 66, 0.08);
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

.title {
  font-size: 14px;
  margin-bottom: 4px;
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
  gap: 4px;
  flex-wrap: wrap;
}

.due-date {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  flex-shrink: 0;
}
</style>

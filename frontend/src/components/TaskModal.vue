<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal" v-if="task" :class="{ 'modal-mail': activeTab === 'email' }">
      <div class="modal-main">
      <div class="modal-header">
        <h2>{{ task.title }}</h2>
        <div class="header-actions">
          <button v-if="canEdit" type="button" class="btn secondary edit-btn" @click="$emit('edit', task)">
            Редактировать
          </button>
          <button
            v-if="canDelete"
            type="button"
            class="btn secondary danger-btn"
            :disabled="deleteLoading"
            @click="removeTask"
          >
            {{ deleteLoading ? "Удаление…" : "Удалить" }}
          </button>
          <button class="close-btn" @click="$emit('close')" aria-label="Закрыть">×</button>
        </div>
      </div>

      <p v-if="deleteError" class="error-text">{{ deleteError }}</p>
      <p class="description">{{ task.description || "Без описания" }}</p>
      <p v-if="task.due_date" class="due-date">Срок: {{ formatDueDate(task.due_date) }}</p>
      <p v-if="task.client" class="client-line">
        Клиент:
        <router-link :to="{ name: 'clients' }" class="client-link" @click.stop>
          {{ task.client.name }}
        </router-link>
        <span v-if="task.client.company" class="muted"> · {{ task.client.company }}</span>
      </p>

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
            v-for="s in stages"
            :key="s.id"
            type="button"
            class="status-btn"
            :class="{ active: task.stage_id === s.id }"
            :disabled="!isStageSelectable(s) || statusLoading"
            :title="!isStageSelectable(s) ? 'Исполнитель не может перевести задачу в эту стадию' : ''"
            @click="pickStage(s)"
          >
            {{ s.name }}
          </button>
        </div>
        <div v-else class="current-status-badge">{{ stageLabel(task) }}</div>

        <p v-if="canChangeStatus && needsResultHint" class="result-hint">
          Для перевода в стадию с требованием результата отметьте последний комментарий как результат.
        </p>
        <p v-if="statusError" class="error-text">{{ statusError }}</p>
      </div>

      <div class="section">
        <div class="tabs">
          <button
            type="button"
            class="tab"
            :class="{ active: activeTab === 'comments' }"
            @click="selectTab('comments')"
          >
            Комментарии
            <span v-if="unread.comments" class="tab-badge">{{ unread.comments }}</span>
          </button>
          <button
            type="button"
            class="tab"
            :class="{ active: activeTab === 'results' }"
            @click="selectTab('results')"
          >
            Результаты
            <span v-if="resultComments.length" class="tab-count">{{ resultComments.length }}</span>
            <span v-if="unread.results" class="tab-badge">{{ unread.results }}</span>
          </button>
          <button
            type="button"
            class="tab"
            :class="{ active: activeTab === 'timeline' }"
            @click="selectTab('timeline')"
          >
            Таймлайн
            <span v-if="unread.timeline" class="tab-badge">{{ unread.timeline }}</span>
          </button>
          <button
            type="button"
            class="tab"
            :class="{ active: activeTab === 'email' }"
            @click="selectTab('email')"
          >
            Почта
            <span v-if="unread.email" class="tab-badge">{{ unread.email }}</span>
          </button>
        </div>

        <div v-if="activeTab === 'comments' || activeTab === 'results'" class="comments">
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

        <form
          v-if="activeTab === 'comments'"
          class="new-comment"
          @submit.prevent="submitComment"
        >
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

        <div v-if="activeTab === 'timeline'" class="timeline">
          <div v-for="ev in timelineEvents" :key="ev.id" class="timeline-item" :class="ev.event_type">
            <div class="timeline-dot"></div>
            <div class="timeline-body">
              <div class="timeline-head">
                <strong>{{ ev.title }}</strong>
                <span class="time">{{ formatDate(ev.created_at) }}</span>
              </div>
              <div class="timeline-meta">
                <span class="event-type">{{ eventTypeLabel(ev.event_type) }}</span>
                <span v-if="ev.actor"> · {{ ev.actor.full_name }}</span>
              </div>
              <div v-if="ev.detail" class="timeline-detail">{{ ev.detail }}</div>
            </div>
          </div>
          <p v-if="timelineEvents.length === 0" class="muted">Событий пока нет</p>
        </div>

        <div v-if="activeTab === 'email'" class="email-panel email-panel--hints">
          <p v-if="!task.client" class="result-hint">
            К задаче не привязан клиент — укажите получателя вручную. История переписки с клиентом
            появится после привязки.
          </p>
          <p v-else-if="!task.client.email" class="result-hint">
            У клиента «{{ task.client.name }}» не указан email — заполните карточку клиента.
          </p>
          <p v-if="!emailConfigured" class="result-hint">
            Почтовая интеграция не настроена. Администратор может включить её в разделе «Почта».
          </p>
          <p v-else-if="mailThread.length > 0" class="muted email-side-hint">
            Переписка справа. Новое письмо — кнопка «Написать письмо».
          </p>
          <p v-else class="muted email-side-hint">
            Переписка справа. Отправьте первое письмо в форме внизу панели.
          </p>
        </div>
      </div>
      </div>

      <aside v-if="activeTab === 'email'" class="mail-sidebar">
        <div class="mail-sidebar-head">
          <div>
            <div class="section-title">Переписка</div>
            <p class="muted small mail-count" v-if="!mailThreadLoading">
              {{ mailThread.length ? `${mailThread.length} писем` : "Пока пусто" }}
            </p>
          </div>
          <button
            v-if="emailConfigured && mailThread.length > 0"
            type="button"
            class="btn"
            @click="openComposeModal"
          >
            Написать письмо
          </button>
        </div>
        <div class="mail-thread">
          <MailLoading v-if="mailThreadLoading" />
          <template v-else>
            <div
              v-for="m in mailThread"
              :key="m.id"
              class="mail-bubble"
              :class="m.direction"
            >
              <div class="mail-meta">
                <strong>{{ m.direction === 'inbound' ? 'Клиент' : (m.actor?.full_name || 'Исходящее') }}</strong>
                <span class="muted">{{ formatDate(m.created_at) }}</span>
              </div>
              <div class="mail-subject">{{ m.subject || "Без темы" }}</div>
              <div class="mail-from muted small">
                {{ m.direction === 'inbound' ? `От: ${m.from_addr}` : `Кому: ${(m.to_addrs || []).join(", ")}` }}
              </div>
              <MailBody :body="m.body" />
            </div>
            <p v-if="mailThread.length === 0" class="muted mail-empty">
              Писем по этой задаче пока нет
            </p>
          </template>
        </div>

        <!-- Первое письмо: форма сразу внизу панели -->
        <div
          v-if="emailConfigured && !mailThreadLoading && mailThread.length === 0"
          class="mail-compose-inline"
        >
          <form class="email-form" @submit.prevent="submitEmail">
            <label v-if="messageTemplates.length">
              Шаблон
              <select
                :value="selectedTemplateId"
                @change="applyMessageTemplate(($event.target).value)"
              >
                <option value="">Без шаблона</option>
                <option v-for="tpl in messageTemplates" :key="tpl.id" :value="String(tpl.id)">
                  {{ tpl.name }}
                </option>
              </select>
            </label>
            <label>
              Кому
              <input v-model="emailTo" type="text" placeholder="a@x.com, b@y.com" required />
            </label>
            <div class="quick-emails" v-if="suggestedEmails.length">
              <button
                v-for="addr in suggestedEmails"
                :key="addr"
                type="button"
                class="chip-btn"
                @click="addRecipient(addr)"
              >
                {{ addr }}
              </button>
            </div>
            <label>
              Копия
              <input v-model="emailCc" type="text" placeholder="опционально" />
            </label>
            <label>
              Тема
              <input v-model="emailSubject" type="text" required />
            </label>
            <label>
              Текст
              <textarea v-model="emailBody" class="email-body" rows="4"></textarea>
            </label>
            <p v-if="emailError" class="error-text">{{ emailError }}</p>
            <button class="btn" type="submit" :disabled="emailLoading">
              {{ emailLoading ? "Отправка..." : "Отправить письмо" }}
            </button>
          </form>
        </div>
      </aside>

      <div
        v-if="showComposeModal"
        class="compose-overlay"
        @click.self="closeComposeModal"
      >
        <div class="compose-modal">
          <div class="compose-modal-head">
            <h3>Новое письмо</h3>
            <button type="button" class="close-btn" @click="closeComposeModal" aria-label="Закрыть">×</button>
          </div>
          <form class="email-form" @submit.prevent="submitEmail">
            <label v-if="messageTemplates.length">
              Шаблон
              <select
                :value="selectedTemplateId"
                @change="applyMessageTemplate(($event.target).value)"
              >
                <option value="">Без шаблона</option>
                <option v-for="tpl in messageTemplates" :key="tpl.id" :value="String(tpl.id)">
                  {{ tpl.name }}
                </option>
              </select>
            </label>
            <label>
              Кому
              <input v-model="emailTo" type="text" placeholder="a@x.com, b@y.com" required />
            </label>
            <div class="quick-emails" v-if="suggestedEmails.length">
              <button
                v-for="addr in suggestedEmails"
                :key="addr"
                type="button"
                class="chip-btn"
                @click="addRecipient(addr)"
              >
                {{ addr }}
              </button>
            </div>
            <label>
              Копия
              <input v-model="emailCc" type="text" placeholder="опционально" />
            </label>
            <label>
              Тема
              <input v-model="emailSubject" type="text" required />
            </label>
            <label>
              Текст
              <textarea v-model="emailBody" class="email-body" rows="8"></textarea>
            </label>
            <p v-if="emailError" class="error-text">{{ emailError }}</p>
            <div class="compose-actions">
              <button class="btn" type="submit" :disabled="emailLoading">
                {{ emailLoading ? "Отправка..." : "Отправить письмо" }}
              </button>
              <button type="button" class="btn secondary" @click="closeComposeModal">Отмена</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import {
  getTask,
  addComment,
  setCommentResult,
  changeStatus,
  sendTaskEmail,
  listTaskEmails,
  getEmailStatus,
  listMessageTemplates,
  deleteTask,
} from "../api/tasks";
import { listStages } from "../api/stages";
import { onTaskEvent } from "../realtime";
import { useAuthStore } from "../stores/auth";
import { useUnreadStore } from "../stores/unread";
import MailBody from "./MailBody.vue";
import MailLoading from "./MailLoading.vue";

const props = defineProps({
  taskId: { type: Number, required: true },
  stages: { type: Array, default: () => [] },
});
const emit = defineEmits(["close", "updated", "edit", "deleted"]);

const auth = useAuthStore();
const unreadStore = useUnreadStore();
const task = ref(null);
const commentText = ref("");
const commentIsResult = ref(false);
const commentLoading = ref(false);
const statusError = ref("");
const statusLoading = ref(false);
const deleteLoading = ref(false);
const deleteError = ref("");
const activeTab = ref("comments");
const emailConfigured = ref(false);
const emailTo = ref("");
const emailCc = ref("");
const emailSubject = ref("");
const emailBody = ref("");
const emailLoading = ref(false);
const emailError = ref("");
const mailThread = ref([]);
const mailThreadLoading = ref(false);
const showComposeModal = ref(false);
const messageTemplates = ref([]);
const selectedTemplateId = ref("");

const localStages = ref([]);
const stages = computed(() => (props.stages?.length ? props.stages : localStages.value));

const EVENT_LABELS = {
  created: "создание",
  updated: "изменение",
  status_changed: "статус",
  commented: "комментарий",
  email_sent: "почта",
  email_received: "входящее",
  automation: "автоматизация",
  client_linked: "клиент",
};

const isCreator = computed(() => task.value && task.value.creator.id === auth.user.id);
const caps = computed(() => auth.capabilities);
const canEdit = computed(() => {
  if (!task.value) return false;
  if (auth.user.is_admin || caps.value.can_edit_any) return true;
  return isCreator.value && caps.value.can_edit;
});
const canDelete = computed(() => {
  if (!task.value) return false;
  if (auth.user.is_admin || caps.value.can_delete_any) return true;
  return isCreator.value && caps.value.can_delete;
});

const canChangeStatus = computed(() => {
  if (!task.value) return false;
  // админ — без ограничений; остальные — постановщик или исполнитель
  if (auth.user.is_admin) return true;
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

const needsResultHint = computed(() => {
  if (lastCommentIsResult.value) return false;
  return stages.value.some((s) => s.requires_result);
});

function isStageSelectable(stage) {
  if (isCreator.value || auth.user.is_admin) return true;
  return !!stage.assignee_can_set;
}

const resultComments = computed(() =>
  task.value ? task.value.comments.filter((c) => c.is_result) : []
);

const visibleComments = computed(() =>
  activeTab.value === "results" ? resultComments.value : task.value?.comments || []
);

const timelineEvents = computed(() => {
  const events = task.value?.timeline || [];
  return [...events].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
});

const suggestedEmails = computed(() => {
  if (!task.value) return [];
  const set = new Set();
  if (task.value.client?.email) set.add(task.value.client.email);
  const people = [task.value.creator, ...task.value.assignees, ...task.value.observers];
  for (const u of people) {
    if (u.email) set.add(u.email);
  }
  return [...set];
});

const unread = computed(() => {
  if (task.value?.unread) return task.value.unread;
  return unreadStore.forTask(props.taskId);
});

async function selectTab(tab) {
  activeTab.value = tab;
  if (unread.value?.[tab] > 0) {
    try {
      const counts = await unreadStore.markRead(props.taskId, [tab]);
      if (task.value) task.value.unread = counts;
      emit("updated", task.value);
    } catch {
      // ignore
    }
  }
  if (tab === "email") {
    initEmailDraft();
    loadMailThread();
  }
}

function canMarkResult(comment) {
  if (!task.value || comment.is_status_change) return false;
  return comment.author.id === auth.user.id || isCreator.value;
}

function statusLabel(value) {
  const stage = stages.value.find((s) => s.key === value || s.id === value);
  return stage?.name || value;
}

function stageLabel(t) {
  if (t.stage?.name) return t.stage.name;
  return statusLabel(t.status);
}

function eventTypeLabel(type) {
  return EVENT_LABELS[type] || type;
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

function splitEmails(raw) {
  return raw
    .split(/[,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function addRecipient(addr) {
  const current = splitEmails(emailTo.value);
  if (!current.includes(addr)) {
    emailTo.value = [...current, addr].join(", ");
  }
}

function emailTemplateContext() {
  const t = task.value;
  const client = t?.client;
  return {
    date: new Date().toISOString().slice(0, 10),
    source_title: t?.title || "",
    source_id: t?.id || "",
    source_stage: stageLabel(t) || "",
    client_name: client?.name || "",
    client_company: client?.company || "",
    client_id: client?.id || "",
    client_email: client?.email || "",
    client_phone: client?.phone || "",
    notes: client?.notes || "",
  };
}

function renderTemplate(tpl, ctx) {
  let result = tpl || "";
  for (const [key, value] of Object.entries(ctx)) {
    result = result.split(`{${key}}`).join(String(value ?? ""));
  }
  return result;
}

function applyMessageTemplate(templateId) {
  selectedTemplateId.value = templateId === "" || templateId == null ? "" : String(templateId);
  if (!selectedTemplateId.value) {
    emailSubject.value = "";
    emailBody.value = "";
    return;
  }
  const tpl = messageTemplates.value.find((x) => String(x.id) === selectedTemplateId.value);
  if (!tpl) return;
  const ctx = emailTemplateContext();
  emailSubject.value = renderTemplate(tpl.subject_template, ctx);
  emailBody.value = renderTemplate(tpl.body_template, ctx);
}

function initEmailDraft() {
  if (!task.value) return;
  const clientEmail = task.value.client?.email || "";
  emailTo.value = clientEmail || suggestedEmails.value[0] || emailTo.value || "";
  const preferred =
    messageTemplates.value.find((t) =>
      (t.subject_template || "").includes("Автоматизация ваших бизнес-процессов")
    ) || messageTemplates.value[0];
  if (preferred) {
    applyMessageTemplate(preferred.id);
  } else {
    selectedTemplateId.value = "";
    emailSubject.value = "";
    emailBody.value = "";
  }
}

function openComposeModal() {
  initEmailDraft();
  emailError.value = "";
  showComposeModal.value = true;
}

function closeComposeModal() {
  showComposeModal.value = false;
  emailError.value = "";
  selectedTemplateId.value = "";
}

async function loadMailThread() {
  mailThreadLoading.value = true;
  try {
    mailThread.value = await listTaskEmails(props.taskId);
  } catch {
    mailThread.value = [];
  } finally {
    mailThreadLoading.value = false;
  }
}

async function load() {
  task.value = await getTask(props.taskId);
  if (task.value?.unread) {
    unreadStore.applyTaskUnread(props.taskId, task.value.unread);
  }
  // при открытии помечаем активную вкладку прочитанной
  await selectTab(activeTab.value);
}

async function ensureStages() {
  if (!props.value.length) {
    try {
      localStages.value = await listStages();
    } catch {
      localStages.value = [];
    }
  }
}

load();
ensureStages();
getEmailStatus()
  .then((s) => {
    emailConfigured.value = !!s.configured;
  })
  .catch(() => {
    emailConfigured.value = false;
  });
listMessageTemplates()
  .then((list) => {
    messageTemplates.value = list || [];
  })
  .catch(() => {
    messageTemplates.value = [];
  });

watch(
  () => props.taskId,
  () => {
    activeTab.value = "comments";
    load();
  }
);

let unsubscribeRealtime = null;
onMounted(() => {
  unsubscribeRealtime = onTaskEvent((event) => {
    if (event.task_id === props.taskId) {
      if (event.type === "task_deleted") {
        emit("deleted", props.taskId);
        emit("close");
        unreadStore.refresh();
        return;
      }
      load();
      if (event.type === "email_received" && activeTab.value === "email") {
        loadMailThread();
      }
    } else {
      unreadStore.refresh();
    }
  });
});
onUnmounted(() => {
  unsubscribeRealtime?.();
});

async function removeTask() {
  if (!task.value) return;
  if (!confirm(`Удалить задачу «${task.value.title}»?`)) return;
  deleteLoading.value = true;
  deleteError.value = "";
  try {
    await deleteTask(props.taskId);
    emit("deleted", props.taskId);
    emit("close");
    unreadStore.refresh();
  } catch (e) {
    deleteError.value = e.response?.data?.detail || "Не удалось удалить задачу";
  } finally {
    deleteLoading.value = false;
  }
}

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

async function pickStage(stage) {
  if (stage.id === task.value.stage_id) return;
  statusError.value = "";
  if (stage.requires_result && !lastCommentIsResult.value) {
    statusError.value = `Чтобы перевести задачу в «${stage.name}», отметьте последний комментарий как результат`;
    return;
  }
  statusLoading.value = true;
  try {
    task.value = await changeStatus(props.taskId, stage.id);
    emit("updated", task.value);
  } catch (e) {
    statusError.value = e.response?.data?.detail || "Не удалось изменить стадию";
  } finally {
    statusLoading.value = false;
  }
}

async function submitEmail() {
  emailError.value = "";
  emailLoading.value = true;
  try {
    task.value = await sendTaskEmail(props.taskId, {
      to_emails: splitEmails(emailTo.value),
      cc_emails: splitEmails(emailCc.value),
      subject: emailSubject.value,
      body: emailBody.value,
    });
    emailBody.value = "";
    closeComposeModal();
    await loadMailThread();
    emit("updated", task.value);
    activeTab.value = "email";
  } catch (e) {
    emailError.value = e.response?.data?.detail || "Не удалось отправить письмо";
  } finally {
    emailLoading.value = false;
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
  padding: 0;
  width: 620px;
  max-height: 88vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}

.modal-main {
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
  min-height: 0;
  flex: 1;
}

.modal.modal-mail {
  width: min(1120px, 96vw);
  height: 90vh;
  max-height: 90vh;
  flex-direction: row;
  align-items: stretch;
}

.modal.modal-mail .modal-main {
  flex: 0 0 min(440px, 42%);
  max-width: 480px;
  border-right: 1px solid var(--border);
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

.edit-btn,
.danger-btn {
  font-size: 12px;
  padding: 6px 10px;
}

.danger-btn {
  color: #b42318;
  border-color: #f3c0bc;
}

.danger-btn:hover:not(:disabled) {
  background: #fef3f2;
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

.client-line {
  margin: -8px 0 0;
  font-size: 13px;
}

.client-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.client-link:hover {
  text-decoration: underline;
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
  flex-wrap: wrap;
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

.tab-badge {
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

.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 320px;
  overflow-y: auto;
  padding-left: 6px;
}

.timeline-item {
  display: grid;
  grid-template-columns: 16px 1fr;
  gap: 10px;
  position: relative;
  padding-bottom: 14px;
}

.timeline-item:not(:last-child)::before {
  content: "";
  position: absolute;
  left: 7px;
  top: 14px;
  bottom: 0;
  width: 2px;
  background: var(--border);
}

.timeline-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--primary);
  margin-top: 4px;
  z-index: 1;
}

.timeline-item.email_sent .timeline-dot {
  background: #00875a;
}

.timeline-item.automation .timeline-dot {
  background: #6554c0;
}

.timeline-item.status_changed .timeline-dot {
  background: #ff8b00;
}

.timeline-body {
  font-size: 13px;
}

.timeline-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.timeline-meta {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 2px;
}

.event-type {
  text-transform: uppercase;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.timeline-detail {
  margin-top: 6px;
  white-space: pre-wrap;
  color: var(--text);
  background: var(--bg);
  border-radius: 6px;
  padding: 8px 10px;
}

.email-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.email-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}

.email-form input,
.email-form textarea,
.email-form select {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-family: inherit;
  font-size: 13px;
}

.email-form textarea.email-body {
  height: 250px;
  resize: vertical;
}

.quick-emails {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip-btn {
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: 12px;
  padding: 3px 10px;
  font-size: 12px;
}

.chip-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.mail-sidebar {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #f7f8fa;
}

.mail-sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}

.mail-count {
  margin: 4px 0 0;
}

.mail-thread {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px 20px;
  margin: 0;
}

.mail-empty {
  margin: 24px 0;
  text-align: center;
}

.mail-compose-inline {
  border-top: 1px solid var(--border);
  padding: 16px 20px;
  background: var(--surface);
  flex-shrink: 0;
  max-height: 45%;
  overflow-y: auto;
}

.email-side-hint {
  margin: 0;
}

.compose-overlay {
  position: absolute;
  inset: 0;
  background: rgba(9, 30, 66, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
  padding: 24px;
  border-radius: 10px;
}

.compose-modal {
  background: var(--surface);
  border-radius: 10px;
  padding: 20px 24px;
  width: min(520px, 100%);
  max-height: 85%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: 0 12px 32px rgba(9, 30, 66, 0.22);
}

.compose-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.compose-modal-head h3 {
  margin: 0;
  font-size: 16px;
}

.compose-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.mail-bubble {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--bg);
}

.mail-bubble.outbound {
  border-left: 3px solid #2563eb;
}

.mail-bubble.inbound {
  border-left: 3px solid #16a34a;
  background: #f0fdf4;
}

.mail-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 4px;
}

.mail-subject {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 2px;
}

.mail-body {
  margin: 8px 0 0;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.4;
}

.email-form .btn {
  align-self: flex-end;
}

.small {
  font-size: 12px;
}

@media (max-width: 860px) {
  .modal.modal-mail {
    flex-direction: column;
    height: 92vh;
  }

  .modal.modal-mail .modal-main {
    flex: 0 0 auto;
    max-width: none;
    max-height: 38%;
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
}
</style>

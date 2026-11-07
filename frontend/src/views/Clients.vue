<template>
  <div class="clients-page">
    <header>
      <router-link to="/" class="back-link">← К доске</router-link>
      <h1>Клиенты</h1>
      <button class="btn" @click="showForm = true">+ Клиент</button>
    </header>

    <div class="layout">
      <section class="list-card">
        <input
          v-model="search"
          type="search"
          class="search"
          placeholder="Поиск по имени, компании, email..."
        />
        <div
          v-for="c in filtered"
          :key="c.id"
          class="client-row"
          :class="{ active: selectedId === c.id }"
          @click="openClient(c.id)"
        >
          <div>
            <strong>{{ c.name }}</strong>
            <span v-if="c.company" class="muted"> · {{ c.company }}</span>
          </div>
          <div class="row-meta">
            <span class="muted">{{ c.tasks_count }} задач</span>
            <span v-if="c.last_activity_at" class="muted">
              · активность {{ formatDate(c.last_activity_at) }}
            </span>
          </div>
        </div>
        <p v-if="filtered.length === 0" class="muted">Клиентов пока нет</p>
      </section>

      <section v-if="detail" class="detail-card">
        <div class="detail-header">
          <div>
            <h2>{{ detail.name }}</h2>
            <p class="muted">{{ detail.company || "Без компании" }}</p>
          </div>
          <div class="detail-actions">
            <button type="button" class="btn secondary" @click="startEdit">Изменить</button>
            <button type="button" class="link-btn danger" @click="remove">Удалить</button>
          </div>
        </div>

        <div class="info-grid">
          <div><span class="label">Email</span>{{ detail.email || "—" }}</div>
          <div><span class="label">Телефон</span>{{ detail.phone || "—" }}</div>
          <div class="full">
            <span class="label">Заметки</span>
            <div class="notes">{{ detail.notes || "—" }}</div>
          </div>
        </div>

        <h3>Переписка</h3>
        <div class="mail-thread">
          <MailLoading v-if="mailLoading" />
          <template v-else>
            <div
              v-for="m in clientMails"
              :key="m.id"
              class="mail-bubble"
              :class="m.direction"
            >
              <div class="mail-meta">
                <strong>
                  {{ m.direction === "inbound" ? "Клиент" : (m.actor?.full_name || "Исходящее") }}
                  <span v-if="m.task_id" class="muted"> · задача #{{ m.task_id }}</span>
                </strong>
                <span class="muted">{{ formatDate(m.created_at) }}</span>
              </div>
              <div class="mail-subject">{{ m.subject || "Без темы" }}</div>
              <div class="mail-from muted small">
                {{ m.direction === "inbound" ? `От: ${m.from_addr}` : `Кому: ${(m.to_addrs || []).join(", ")}` }}
              </div>
              <MailBody :body="m.body" />
            </div>
            <p v-if="clientMails.length === 0" class="muted">Переписки пока нет</p>
          </template>
        </div>

        <h3>Таймлайн</h3>
        <div class="timeline">
          <div
            v-for="ev in timelineSorted"
            :key="ev.id"
            class="timeline-item"
          >
            <div class="dot"></div>
            <div>
              <div class="tl-head">
                <strong>{{ ev.title }}</strong>
                <span class="muted">{{ formatDate(ev.created_at) }}</span>
              </div>
              <div class="muted small">
                {{ eventLabel(ev.event_type) }}
                <span v-if="ev.actor"> · {{ ev.actor.full_name }}</span>
              </div>
              <div v-if="ev.detail" class="tl-detail">{{ ev.detail }}</div>
            </div>
          </div>
          <p v-if="timelineSorted.length === 0" class="muted">Событий нет</p>
        </div>

        <form class="note-form" @submit.prevent="submitNote">
          <textarea v-model="noteText" rows="2" placeholder="Добавить заметку в таймлайн..." required />
          <button class="btn" type="submit" :disabled="noteLoading">Добавить</button>
        </form>
      </section>
    </div>

    <div v-if="showForm" class="overlay" @click.self="closeForm">
      <form class="modal" @submit.prevent="saveClient">
        <h2>{{ editingId ? "Редактировать клиента" : "Новый клиент" }}</h2>
        <label>Имя / название<input v-model="form.name" required /></label>
        <label>Компания<input v-model="form.company" /></label>
        <label>Email<input v-model="form.email" type="email" /></label>
        <label>Телефон<input v-model="form.phone" /></label>
        <label>Заметки<textarea v-model="form.notes" rows="3" /></label>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="actions">
          <button type="button" class="btn secondary" @click="closeForm">Отмена</button>
          <button class="btn" type="submit" :disabled="formLoading">
            {{ formLoading ? "Сохранение..." : "Сохранить" }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import MailBody from "../components/MailBody.vue";
import MailLoading from "../components/MailLoading.vue";
import {
  listClients,
  getClient,
  createClient,
  updateClient,
  deleteClient,
  addClientNote,
  listClientEmails,
} from "../api/clients";

const clients = ref([]);
const search = ref("");
const selectedId = ref(null);
const detail = ref(null);
const clientMails = ref([]);
const mailLoading = ref(false);
const showForm = ref(false);
const editingId = ref(null);
const form = reactive({ name: "", company: "", email: "", phone: "", notes: "" });
const formLoading = ref(false);
const formError = ref("");
const noteText = ref("");
const noteLoading = ref(false);

const EVENT_LABELS = {
  created: "создание",
  updated: "изменение",
  note: "заметка",
  task_linked: "задача",
  task_activity: "активность по задаче",
  email_sent: "почта",
  email_received: "входящее",
  automation: "автоматизация",
};

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return clients.value;
  return clients.value.filter((c) =>
    [c.name, c.company, c.email, c.phone].join(" ").toLowerCase().includes(q)
  );
});

const timelineSorted = computed(() => {
  const events = detail.value?.timeline || [];
  return [...events].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
});

function formatDate(iso) {
  return new Date(iso + (String(iso).endsWith("Z") ? "" : "Z")).toLocaleString("ru-RU");
}

function eventLabel(type) {
  return EVENT_LABELS[type] || type;
}

async function refreshList() {
  clients.value = await listClients();
}

async function openClient(id) {
  selectedId.value = id;
  detail.value = await getClient(id);
  mailLoading.value = true;
  clientMails.value = [];
  try {
    clientMails.value = await listClientEmails(id);
  } catch {
    clientMails.value = [];
  } finally {
    mailLoading.value = false;
  }
}

function closeForm() {
  showForm.value = false;
  editingId.value = null;
  formError.value = "";
  form.name = "";
  form.company = "";
  form.email = "";
  form.phone = "";
  form.notes = "";
}

function startEdit() {
  if (!detail.value) return;
  editingId.value = detail.value.id;
  form.name = detail.value.name;
  form.company = detail.value.company || "";
  form.email = detail.value.email || "";
  form.phone = detail.value.phone || "";
  form.notes = detail.value.notes || "";
  showForm.value = true;
}

async function saveClient() {
  formError.value = "";
  formLoading.value = true;
  try {
    const payload = { ...form };
    let saved;
    if (editingId.value) {
      saved = await updateClient(editingId.value, payload);
    } else {
      saved = await createClient(payload);
    }
    closeForm();
    await refreshList();
    await openClient(saved.id);
  } catch (e) {
    formError.value = e.response?.data?.detail || "Не удалось сохранить";
  } finally {
    formLoading.value = false;
  }
}

async function remove() {
  if (!detail.value) return;
  if (!confirm(`Удалить клиента «${detail.value.name}»?`)) return;
  await deleteClient(detail.value.id);
  detail.value = null;
  selectedId.value = null;
  await refreshList();
}

async function submitNote() {
  noteLoading.value = true;
  try {
    detail.value = await addClientNote(detail.value.id, noteText.value);
    noteText.value = "";
    await refreshList();
  } finally {
    noteLoading.value = false;
  }
}

onMounted(refreshList);
</script>

<style scoped>
.clients-page {
  padding: 24px;
  max-width: 1100px;
  margin: 0 auto;
}

header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.back-link {
  color: var(--primary);
  font-size: 13px;
  text-decoration: none;
}

h1 {
  margin: 0;
  font-size: 20px;
  flex: 1;
}

.layout {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 16px;
  align-items: start;
}

.list-card,
.detail-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}

.search {
  width: 100%;
  margin-bottom: 12px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
}

.client-row {
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
}

.client-row:hover {
  background: var(--bg);
}

.client-row.active {
  border-color: var(--primary);
  background: #deebff;
}

.row-meta {
  font-size: 12px;
  margin-top: 2px;
}

.muted {
  color: var(--text-muted);
}

.detail-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

h2 {
  margin: 0;
  font-size: 18px;
}

h3 {
  margin: 18px 0 8px;
  font-size: 13px;
  text-transform: uppercase;
  color: var(--text-muted);
}

.detail-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  font-size: 14px;
}

.info-grid .full {
  grid-column: 1 / -1;
}

.label {
  display: block;
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-muted);
  font-weight: 700;
  margin-bottom: 2px;
}

.notes {
  white-space: pre-wrap;
}

.mail-thread {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 320px;
  overflow-y: auto;
  margin-bottom: 8px;
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
}

.mail-body {
  margin: 8px 0 0;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.4;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 360px;
  overflow-y: auto;
}

.timeline-item {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 10px;
  padding-bottom: 12px;
  position: relative;
}

.timeline-item:not(:last-child)::before {
  content: "";
  position: absolute;
  left: 5px;
  top: 12px;
  bottom: 0;
  width: 2px;
  background: var(--border);
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--primary);
  margin-top: 4px;
  z-index: 1;
}

.tl-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.small {
  font-size: 12px;
}

.tl-detail {
  margin-top: 6px;
  background: var(--bg);
  border-radius: 6px;
  padding: 8px 10px;
  white-space: pre-wrap;
  font-size: 13px;
}

.note-form {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.note-form textarea {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-family: inherit;
}

.link-btn {
  border: none;
  background: transparent;
  color: var(--danger);
  font-size: 12px;
}

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
  padding: 24px;
  width: 420px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.modal label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}

.modal input,
.modal textarea {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-family: inherit;
  font-size: 13px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

@media (max-width: 800px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>

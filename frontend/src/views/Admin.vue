<template>
  <div class="admin-page">
    <header>
      <router-link to="/" class="back-link">← К доске</router-link>
      <h1>Администрирование</h1>
    </header>

    <section class="card">
      <h2>Пользователи</h2>
      <table class="users-table">
        <thead>
          <tr>
            <th></th>
            <th>Имя</th>
            <th>Логин</th>
            <th>Команды</th>
            <th>Роль</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td><Avatar :user="u" :size="26" /></td>
            <td>{{ u.full_name }} <span v-if="u.is_admin" class="admin-tag">админ</span></td>
            <td class="muted">{{ u.username }}</td>
            <td>
              <span v-if="u.teams.length === 0" class="muted">—</span>
              <span v-for="t in u.teams" :key="t.id" class="chip">{{ t.name }}</span>
            </td>
            <td>
              <select :value="u.role" @change="onRoleChange(u, $event)">
                <option value="creator">Может ставить задачи</option>
                <option value="executor">Исполнитель</option>
                <option value="observer">Наблюдатель</option>
              </select>
            </td>
            <td>
              <button
                v-if="!u.is_admin"
                type="button"
                class="link-btn danger"
                @click="removeUser(u)"
              >
                Удалить
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <form class="inline-form" @submit.prevent="submitNewUser">
        <input v-model="newUser.username" type="text" placeholder="Логин" required />
        <input v-model="newUser.full_name" type="text" placeholder="Имя" required />
        <input v-model="newUser.password" type="password" placeholder="Пароль" required />
        <button class="btn" type="submit" :disabled="newUserLoading">Создать пользователя</button>
      </form>
      <p v-if="newUserError" class="error-text">{{ newUserError }}</p>
      <p v-if="userActionError" class="error-text">{{ userActionError }}</p>
    </section>

    <section class="card">
      <h2>Команды</h2>
      <div class="teams-list">
        <div v-for="t in teams" :key="t.id" class="team-block">
          <div class="team-header">
            <strong>{{ t.name }}</strong>
            <button class="link-btn danger" @click="removeTeam(t)">Удалить команду</button>
          </div>
          <div class="member-chips">
            <span v-for="m in t.members" :key="m.id" class="chip removable">
              {{ m.full_name }}
              <button type="button" class="chip-remove" @click="removeMember(t, m)">×</button>
            </span>
            <span v-if="t.members.length === 0" class="muted">Нет участников</span>
          </div>
          <div class="add-member">
            <select :value="''" @change="onAddMember(t, $event)">
              <option value="" disabled selected>Добавить участника...</option>
              <option v-for="u in nonMembers(t)" :key="u.id" :value="u.id">{{ u.full_name }}</option>
            </select>
            <span v-if="nonMembers(t).length === 0" class="muted">Все пользователи уже в команде</span>
          </div>
        </div>
      </div>

      <form class="inline-form" @submit.prevent="submitNewTeam">
        <input v-model="newTeamName" type="text" placeholder="Название команды" required />
        <button class="btn" type="submit" :disabled="newTeamLoading">Создать команду</button>
      </form>
      <p v-if="teamError" class="error-text">{{ teamError }}</p>
    </section>

    <section class="card">
      <h2>Права на постановку задач между командами</h2>
      <p class="hint">
        Участники команды «От кого» смогут ставить задачи участникам команды «Кому».
        Внутри своей команды ставить задачи можно всегда без дополнительных прав.
      </p>

      <div class="permissions-list">
        <div v-for="p in permissions" :key="p.id" class="permission-row">
          <span class="chip">{{ p.from_team.name }}</span>
          <span class="arrow">→</span>
          <span class="chip">{{ p.to_team.name }}</span>
          <button class="link-btn danger" @click="removePermission(p)">Удалить</button>
        </div>
        <p v-if="permissions.length === 0" class="muted">Прав пока не настроено</p>
      </div>

      <form class="inline-form" @submit.prevent="submitNewPermission">
        <select v-model="newPermission.from_team_id" required>
          <option value="" disabled selected>От команды...</option>
          <option v-for="t in teams" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
        <span class="arrow">→</span>
        <select v-model="newPermission.to_team_id" required>
          <option value="" disabled selected>Команде...</option>
          <option v-for="t in teams" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
        <button class="btn" type="submit" :disabled="permissionLoading">Добавить право</button>
      </form>
      <p v-if="permissionError" class="error-text">{{ permissionError }}</p>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import Avatar from "../components/Avatar.vue";
import {
  listAllUsers,
  createUser,
  deleteUser,
  updateUserRole,
  listTeams,
  createTeam,
  deleteTeam,
  addTeamMember,
  removeTeamMember,
  listPermissions,
  createPermission,
  deletePermission,
} from "../api/admin";

const users = ref([]);
const teams = ref([]);
const permissions = ref([]);

const newUser = reactive({ username: "", full_name: "", password: "" });
const newUserLoading = ref(false);
const newUserError = ref("");
const userActionError = ref("");

const newTeamName = ref("");
const newTeamLoading = ref(false);
const teamError = ref("");

const newPermission = reactive({ from_team_id: "", to_team_id: "" });
const permissionLoading = ref(false);
const permissionError = ref("");

async function refreshAll() {
  const [u, t, p] = await Promise.all([listAllUsers(), listTeams(), listPermissions()]);
  users.value = u;
  teams.value = t;
  permissions.value = p;
}

onMounted(refreshAll);

function nonMembers(team) {
  const memberIds = new Set(team.members.map((m) => m.id));
  return users.value.filter((u) => !memberIds.has(u.id));
}

async function submitNewUser() {
  newUserError.value = "";
  newUserLoading.value = true;
  try {
    await createUser({ ...newUser });
    newUser.username = "";
    newUser.full_name = "";
    newUser.password = "";
    await refreshAll();
  } catch (e) {
    newUserError.value = e.response?.data?.detail || "Не удалось создать пользователя";
  } finally {
    newUserLoading.value = false;
  }
}

async function submitNewTeam() {
  teamError.value = "";
  newTeamLoading.value = true;
  try {
    await createTeam(newTeamName.value.trim());
    newTeamName.value = "";
    await refreshAll();
  } catch (e) {
    teamError.value = e.response?.data?.detail || "Не удалось создать команду";
  } finally {
    newTeamLoading.value = false;
  }
}

async function onRoleChange(user, event) {
  userActionError.value = "";
  const role = event.target.value;
  try {
    await updateUserRole(user.id, role);
    await refreshAll();
  } catch (e) {
    userActionError.value = e.response?.data?.detail || "Не удалось изменить роль";
    event.target.value = user.role;
  }
}

async function removeUser(user) {
  userActionError.value = "";
  if (!confirm(`Удалить пользователя «${user.full_name}»?`)) return;
  try {
    await deleteUser(user.id);
    await refreshAll();
  } catch (e) {
    userActionError.value = e.response?.data?.detail || "Не удалось удалить пользователя";
  }
}

async function removeTeam(team) {
  teamError.value = "";
  if (!confirm(`Удалить команду «${team.name}»?`)) return;
  try {
    await deleteTeam(team.id);
    await refreshAll();
  } catch (e) {
    teamError.value = e.response?.data?.detail || "Не удалось удалить команду";
  }
}

async function onAddMember(team, event) {
  const userId = Number(event.target.value);
  event.target.value = "";
  if (!userId) return;
  teamError.value = "";
  try {
    await addTeamMember(team.id, userId);
    await refreshAll();
  } catch (e) {
    teamError.value = e.response?.data?.detail || "Не удалось добавить участника";
  }
}

async function removeMember(team, user) {
  teamError.value = "";
  try {
    await removeTeamMember(team.id, user.id);
    await refreshAll();
  } catch (e) {
    teamError.value = e.response?.data?.detail || "Не удалось убрать участника";
  }
}

async function submitNewPermission() {
  permissionError.value = "";
  if (!newPermission.from_team_id || !newPermission.to_team_id) return;
  permissionLoading.value = true;
  try {
    await createPermission(newPermission.from_team_id, newPermission.to_team_id);
    newPermission.from_team_id = "";
    newPermission.to_team_id = "";
    await refreshAll();
  } catch (e) {
    permissionError.value = e.response?.data?.detail || "Не удалось добавить право";
  } finally {
    permissionLoading.value = false;
  }
}

async function removePermission(p) {
  await deletePermission(p.id);
  await refreshAll();
}
</script>

<style scoped>
.admin-page {
  padding: 24px;
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-link {
  color: var(--primary);
  font-size: 13px;
  text-decoration: none;
}

h1 {
  font-size: 20px;
  margin: 0;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

h2 {
  font-size: 15px;
  margin: 0;
}

.hint {
  margin: -8px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.users-table th {
  text-align: left;
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  padding: 4px 8px;
  border-bottom: 1px solid var(--border);
}

.users-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
}

.admin-tag {
  background: #6554c0;
  color: white;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: 6px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--bg);
  border: 1px solid var(--border);
  padding: 2px 9px;
  border-radius: 12px;
  font-size: 12px;
  margin-right: 4px;
}

.chip.removable {
  padding-right: 4px;
}

.chip-remove {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1;
  padding: 0 2px;
}

.chip-remove:hover {
  color: var(--danger);
}

.muted {
  color: var(--text-muted);
  font-size: 12px;
}

.inline-form {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.inline-form input,
.inline-form select {
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}

.teams-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.team-block {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.team-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.member-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.add-member {
  display: flex;
  gap: 8px;
}

.btn.small {
  padding: 5px 10px;
  font-size: 12px;
}

.link-btn {
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 12px;
  padding: 0;
}

.link-btn.danger {
  color: var(--danger);
}

.link-btn:hover {
  text-decoration: underline;
}

.permissions-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.permission-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.arrow {
  color: var(--text-muted);
}
</style>

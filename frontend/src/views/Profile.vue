<template>
  <div class="profile-page">
    <router-link to="/" class="back-link">← К доске</router-link>

    <div class="profile-card">
      <div class="avatar-block">
        <Avatar :user="auth.user" :size="112" />
        <label class="btn secondary upload-btn">
          {{ avatarLoading ? "Загрузка..." : "Изменить фото" }}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="onFileChange"
            hidden
          />
        </label>
        <p v-if="avatarError" class="error-text">{{ avatarError }}</p>
      </div>

      <div class="info-block">
        <h1>Профиль</h1>

        <div class="field">
          <span class="field-label">Логин</span>
          <span class="field-value readonly">{{ auth.user.username }}</span>
        </div>

        <div class="field">
          <span class="field-label">Команда</span>
          <span class="field-value readonly teams-value">
            <span v-if="auth.user.teams.length === 0" class="muted">Без команды</span>
            <span v-for="t in auth.user.teams" :key="t.id" class="chip">{{ t.name }}</span>
          </span>
        </div>

        <div class="field">
          <span class="field-label">Роль</span>
          <span class="field-value readonly">
            {{ roleLabel(auth.user.role) }}
          </span>
        </div>

        <div class="field">
          <label class="field-label" for="full_name">Имя</label>
          <input id="full_name" v-model="fullName" type="text" class="field-value" />
        </div>

        <div class="field">
          <label class="field-label" for="bio">О себе</label>
          <textarea
            id="bio"
            v-model="bio"
            rows="5"
            class="field-value"
            placeholder="Расскажите немного о себе..."
          ></textarea>
        </div>

        <p v-if="profileError" class="error-text">{{ profileError }}</p>
        <p v-if="saved" class="saved-text">Сохранено</p>

        <button class="btn save-btn" :disabled="profileLoading" @click="saveProfile">
          {{ profileLoading ? "Сохранение..." : "Сохранить изменения" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useAuthStore } from "../stores/auth";
import { updateProfile, uploadAvatar } from "../api/profile";
import Avatar from "../components/Avatar.vue";

const auth = useAuthStore();
const fullName = ref(auth.user.full_name);
const bio = ref(auth.user.bio || "");
const profileLoading = ref(false);
const profileError = ref("");
const saved = ref(false);
const avatarLoading = ref(false);
const avatarError = ref("");

onMounted(async () => {
  await auth.refreshUser();
  fullName.value = auth.user.full_name;
  bio.value = auth.user.bio || "";
});

const ROLE_LABELS = {
  creator: "Может ставить задачи",
  executor: "Исполнитель",
  observer: "Наблюдатель",
};

function roleLabel(role) {
  return ROLE_LABELS[role] || role;
}

async function saveProfile() {
  profileError.value = "";
  saved.value = false;
  if (!fullName.value.trim()) {
    profileError.value = "Имя не может быть пустым";
    return;
  }
  profileLoading.value = true;
  try {
    const updated = await updateProfile(fullName.value, bio.value);
    auth.setUser(updated);
    saved.value = true;
  } catch (e) {
    profileError.value = e.response?.data?.detail || "Не удалось сохранить";
  } finally {
    profileLoading.value = false;
  }
}

async function onFileChange(e) {
  const file = e.target.files[0];
  if (!file) return;
  avatarError.value = "";
  avatarLoading.value = true;
  try {
    const updated = await uploadAvatar(file);
    auth.setUser(updated);
  } catch (err) {
    avatarError.value = err.response?.data?.detail || "Не удалось загрузить аватар";
  } finally {
    avatarLoading.value = false;
    e.target.value = "";
  }
}
</script>

<style scoped>
.profile-page {
  padding: 24px;
  max-width: 560px;
  margin: 0 auto;
}

.back-link {
  display: inline-block;
  color: var(--primary);
  font-size: 13px;
  text-decoration: none;
  margin-bottom: 16px;
}

.profile-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

.avatar-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.upload-btn {
  font-size: 12px;
  padding: 6px 12px;
}

.info-block {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

h1 {
  font-size: 18px;
  margin: 0 0 4px;
  text-align: center;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.field-label {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.field-value {
  font-size: 14px;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 6px;
  width: 100%;
  font-family: inherit;
}

.field-value.readonly {
  background: var(--bg);
  color: var(--text-muted);
  border-color: transparent;
}

.teams-value {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.teams-value .chip {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  color: var(--text);
}

.teams-value .muted {
  color: var(--text-muted);
  font-size: 13px;
}

textarea.field-value {
  resize: vertical;
}

.saved-text {
  color: #00875a;
  font-size: 13px;
  margin: 0;
}

.save-btn {
  align-self: flex-start;
}
</style>

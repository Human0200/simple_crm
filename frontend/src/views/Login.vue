<template>
  <div class="login-screen">
    <form class="login-card" @submit.prevent="submit">
      <h1>Simple CRM</h1>
      <p class="subtitle">Войдите в свой рабочий аккаунт</p>

      <label>Логин</label>
      <input v-model="username" type="text" autocomplete="username" required />

      <label>Пароль</label>
      <input v-model="password" type="password" autocomplete="current-password" required />

      <p v-if="error" class="error-text">{{ error }}</p>

      <button class="btn" type="submit" :disabled="loading">
        {{ loading ? "Вход..." : "Войти" }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

const auth = useAuthStore();
const router = useRouter();

async function submit() {
  error.value = "";
  loading.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    router.push({ name: "board" });
  } catch (e) {
    error.value = e.response?.data?.detail || "Ошибка входа";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-screen {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 32px;
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

h1 {
  margin: 0 0 4px;
  font-size: 22px;
}

.subtitle {
  margin: 0 0 16px;
  color: var(--text-muted);
  font-size: 13px;
}

label {
  font-size: 13px;
  font-weight: 600;
  margin-top: 8px;
}

input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
}

button {
  margin-top: 16px;
}
</style>

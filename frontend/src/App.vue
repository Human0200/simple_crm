<template>
  <div class="app-shell">
    <div v-if="auth.isAuthenticated" class="global-notes">
      <NotificationBell />
    </div>
    <router-view />
  </div>
</template>

<script setup>
import { watch, onMounted, onUnmounted } from "vue";
import { useAuthStore } from "./stores/auth";
import { useUnreadStore } from "./stores/unread";
import { connectRealtime, disconnectRealtime } from "./realtime";
import NotificationBell from "./components/NotificationBell.vue";

const auth = useAuthStore();
const unread = useUnreadStore();

onMounted(() => {
  if (auth.isAuthenticated) {
    connectRealtime();
    unread.refresh();
  }
});

watch(
  () => auth.isAuthenticated,
  (isAuthenticated) => {
    if (isAuthenticated) {
      connectRealtime();
      unread.refresh();
    } else {
      disconnectRealtime();
      unread.clear();
    }
  }
);

onUnmounted(disconnectRealtime);
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.global-notes {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 80;
}
</style>

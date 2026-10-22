<template>
  <router-view />
</template>

<script setup>
import { watch, onMounted, onUnmounted } from "vue";
import { useAuthStore } from "./stores/auth";
import { connectRealtime, disconnectRealtime } from "./realtime";

const auth = useAuthStore();

onMounted(() => {
  if (auth.isAuthenticated) connectRealtime();
});

watch(
  () => auth.isAuthenticated,
  (isAuthenticated) => {
    if (isAuthenticated) {
      connectRealtime();
    } else {
      disconnectRealtime();
    }
  }
);

onUnmounted(disconnectRealtime);
</script>

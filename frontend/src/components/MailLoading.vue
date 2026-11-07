<template>
  <div class="mail-loading" role="status" aria-live="polite">
    <span class="mail-loading-spinner" aria-hidden="true"></span>
    <span class="mail-loading-text">{{ text }}</span>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: "Загрузка почты..." },
});
</script>

<style scoped>
.mail-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 12px;
  margin: 8px 0;
  border-radius: 8px;
  background: #f4f5f7;
  color: #5e6c84;
  font-size: 13px;
}

.mail-loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid #dfe1e6;
  border-top-color: #0052cc;
  border-radius: 50%;
  animation: mail-spin 0.7s linear infinite;
  flex-shrink: 0;
}

.mail-loading-text {
  line-height: 1.3;
}

@keyframes mail-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

<template>
  <div class="mail-body-wrap">
    <pre class="mail-body">{{ shownText }}</pre>
    <button
      v-if="parts.rest"
      type="button"
      class="mail-quote-toggle"
      @click="expanded = !expanded"
    >
      {{ expanded ? "Скрыть цитату и подпись" : "Показать цитату и подпись" }}
    </button>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { splitMailBody } from "../utils/mailBody";

const props = defineProps({
  body: { type: String, default: "" },
});

const expanded = ref(false);
const parts = computed(() => splitMailBody(props.body));

watch(
  () => props.body,
  () => {
    expanded.value = false;
  }
);

const shownText = computed(() => {
  if (!parts.value.rest) return parts.value.main || "—";
  if (expanded.value) {
    return [parts.value.main, parts.value.rest].filter(Boolean).join("\n\n");
  }
  return parts.value.main || "—";
});
</script>

<style scoped>
.mail-body-wrap {
  margin-top: 6px;
}

.mail-body {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.45;
}

.mail-quote-toggle {
  margin-top: 8px;
  padding: 0;
  border: 0;
  background: none;
  color: #0052cc;
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
}

.mail-quote-toggle:hover {
  color: #0747a6;
}
</style>

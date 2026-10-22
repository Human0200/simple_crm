<template>
  <img
    v-if="url"
    :src="url"
    :alt="user.full_name"
    :title="title || user.full_name"
    class="avatar img"
    :style="sizeStyle"
  />
  <span
    v-else
    class="avatar initials"
    :title="title || user.full_name"
    :style="[sizeStyle, { background: color }]"
  >
    {{ initials }}
  </span>
</template>

<script setup>
import { computed } from "vue";
import { avatarUrl } from "../api/profile";

const props = defineProps({
  user: { type: Object, required: true },
  size: { type: Number, default: 28 },
  title: { type: String, default: "" },
});

const url = computed(() => avatarUrl(props.user));

const initials = computed(() =>
  props.user.full_name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
);

const PALETTE = ["#6554c0", "#0052cc", "#00875a", "#de350b", "#ff8b00", "#6b778c"];
const color = computed(() => PALETTE[props.user.id % PALETTE.length]);

const sizeStyle = computed(() => ({
  width: props.size + "px",
  height: props.size + "px",
  fontSize: Math.round(props.size * 0.4) + "px",
}));
</script>

<style scoped>
.avatar {
  border-radius: 50%;
  flex-shrink: 0;
}

.avatar.img {
  object-fit: cover;
}

.avatar.initials {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
}
</style>

<template>
  <span class="status-dot" :class="`status-dot-${status}`" />
</template>

<script setup>
defineProps({
  status: { type: String, default: 'stopped' },
});
</script>

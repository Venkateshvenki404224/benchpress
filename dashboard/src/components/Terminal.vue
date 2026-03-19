<template>
  <div ref="termRef" class="terminal">
    <div v-for="(line, i) in lines" :key="i" class="terminal-line" :class="`terminal-line-${line.type || 'info'}`">
      <span v-if="line.timestamp" class="text-bp-dim mr-2">[{{ formatTime(line.timestamp) }}]</span>
      <span>{{ line.message }}</span>
    </div>
    <div v-if="lines.length === 0" class="text-bp-dim">Waiting for logs...</div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue';

const props = defineProps({
  lines: { type: Array, default: () => [] },
});

const termRef = ref(null);

function formatTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleTimeString();
}

watch(
  () => props.lines.length,
  async () => {
    await nextTick();
    if (termRef.value) {
      termRef.value.scrollTop = termRef.value.scrollHeight;
    }
  }
);
</script>

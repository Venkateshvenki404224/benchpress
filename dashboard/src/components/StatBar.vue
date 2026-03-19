<template>
  <div>
    <div class="flex justify-between text-xs mb-1">
      <span class="text-bp-muted">{{ label }}</span>
      <span class="text-bp-text font-mono">{{ value }}%</span>
    </div>
    <div class="stat-bar">
      <div class="stat-bar-fill" :style="{ width: value + '%', backgroundColor: barColor }" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  label: String,
  value: { type: Number, default: 0 },
  color: { type: String, default: 'green' },
});

const barColor = computed(() => {
  if (props.value > 80) return '#ef4444';
  if (props.value > 60) return '#f59e0b';
  return props.color === 'cyan' ? '#06b6d4' : '#22c55e';
});
</script>

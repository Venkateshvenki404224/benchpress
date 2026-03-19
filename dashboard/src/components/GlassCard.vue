<template>
  <div class="glass-card glass-card-glow p-6" :class="[shimmer && 'shimmer-border', $attrs.class]">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  shimmer: { type: Boolean, default: false },
});
</script>

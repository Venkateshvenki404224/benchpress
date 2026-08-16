<template>
	<div class="flex flex-col items-center gap-3 px-4 py-10 text-center">
		<component :is="icon" v-if="icon" class="size-5 text-ink-gray-4" />
		<p class="max-w-md text-body text-ink-gray-6">{{ message }}</p>
		<slot name="action" />
	</div>
</template>

<script setup>
// No table gets a bare "No labs found." — an empty state is one sentence plus
// the action that fixes it.
defineProps({
	message: { type: String, required: true },
	icon: { type: [Object, Function], default: null },
});
</script>

<template>
	<button
		class="mb-3.5 flex items-center gap-1.5 text-xs text-ink-gray-5 hover:text-ink-gray-9"
		data-test="back-link"
		@click="router.push(to)"
	>
		<ChevronLeftIcon class="size-3.5" />
		{{ label }}
	</button>
</template>

<script setup>
// The way back from a screen the sidebar does not carry. Build and deploy
// history live under Labs and Instances rather than in the nav, so each one
// states its parent instead of leaving the user on a dead end.
import { useRouter } from "vue-router";

import ChevronLeftIcon from "~icons/lucide/chevron-left";

defineProps({
	to: { type: [String, Object], required: true },
	label: { type: String, required: true },
});

const router = useRouter();
</script>

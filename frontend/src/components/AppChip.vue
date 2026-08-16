<template>
	<span
		class="inline-flex items-center gap-1.5 rounded-full border border-outline-gray-1 bg-surface-white px-2 py-0.5 text-2xs text-ink-gray-7"
	>
		<AppIcon :app="app" :size="12" />
		{{ label }}
	</span>
</template>

<script setup>
import AppIcon from "@/components/AppIcon.vue";
import { labelFor } from "@/utils/appIcons";
import { computed } from "vue";

const props = defineProps({
	app: { type: String, required: true },
});

const label = computed(() => labelFor(props.app));
</script>

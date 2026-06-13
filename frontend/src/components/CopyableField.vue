<template>
	<div class="flex items-center gap-4 py-3">
		<label class="w-36 shrink-0 text-sm font-medium text-ink-gray-9">{{ label }}</label>
		<div class="flex flex-1 items-center gap-2">
			<a
				v-if="href"
				:href="href"
				target="_blank"
				class="flex-1 truncate rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-blue-3 hover:underline"
				>{{ display }}</a
			>
			<code
				v-else
				class="flex-1 rounded bg-surface-gray-1 px-4 py-2.5 font-mono text-sm text-ink-gray-8"
				>{{ display }}</code
			>
			<Button :icon="CopyIcon" variant="ghost" size="sm" label="Copy" @click="copy" />
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { Button, toast } from "frappe-ui";
import CopyIcon from "~icons/lucide/copy";

const props = defineProps({
	label: { type: String, required: true },
	value: { type: String, default: null },
	masked: { type: Boolean, default: false },
	href: { type: String, default: null },
});

const display = computed(() => {
	if (props.masked) return props.value ? "••••••••••••" : "—";
	return props.value ?? "—";
});

function copy() {
	navigator.clipboard.writeText(props.value || "");
	toast.success("Copied");
}
</script>

<template>
	<div class="border border-outline-gray-3 rounded-lg overflow-hidden">
		<!-- Step header -->
		<div
			class="flex items-center gap-3 px-4 py-2.5 bg-surface-gray-6 cursor-pointer select-none hover:bg-surface-gray-5 transition-colors"
			@click="isOpen = !isOpen"
		>
			<!-- Status indicator -->
			<span class="flex h-5 w-5 shrink-0 items-center justify-center">
				<span
					v-if="status === 'success'"
					class="h-2.5 w-2.5 rounded-full bg-surface-green-3"
				/>
				<span
					v-else-if="status === 'error'"
					class="h-2.5 w-2.5 rounded-full bg-surface-red-5"
				/>
				<span
					v-else-if="status === 'running'"
					class="h-2.5 w-2.5 animate-pulse rounded-full bg-amber-500"
				/>
				<span v-else class="h-2.5 w-2.5 rounded-full bg-surface-gray-4" />
			</span>

			<!-- Chevron -->
			<ChevronRightIcon
				class="h-4 w-4 shrink-0 text-ink-gray-4 transition-transform duration-200"
				:class="{ 'rotate-90': isOpen }"
			/>

			<!-- Title -->
			<span class="flex-1 truncate font-mono text-sm text-ink-gray-2">{{ title }}</span>

			<!-- Duration -->
			<span v-if="duration" class="shrink-0 text-xs text-ink-gray-5">{{ duration }}</span>
		</div>

		<!-- Output -->
		<div
			v-show="isOpen"
			ref="outputEl"
			class="max-h-[50vh] overflow-y-auto bg-surface-gray-7 px-4 py-3"
		>
			<pre
				v-if="output"
				class="whitespace-pre-wrap break-words font-mono text-xs leading-5 text-ink-gray-3"
				>{{ output }}</pre
			>
			<span v-else class="text-xs text-ink-gray-4">No output</span>
		</div>
	</div>
</template>

<script setup>
import { ref, watch, nextTick } from "vue";
import ChevronRightIcon from "~icons/lucide/chevron-right";

const props = defineProps({
	title: { type: String, required: true },
	output: { type: String, default: "" },
	status: { type: String, default: "pending" },
	duration: { type: String, default: "" },
	defaultOpen: { type: Boolean, default: false },
});

const isOpen = ref(props.defaultOpen);
const outputEl = ref(null);

// Auto-scroll when output changes (for live streaming)
watch(
	() => props.output,
	async () => {
		if (isOpen.value && outputEl.value) {
			await nextTick();
			outputEl.value.scrollTop = outputEl.value.scrollHeight;
		}
	}
);
</script>

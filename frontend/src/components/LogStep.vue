<template>
	<div class="overflow-hidden rounded-control border border-outline-gray-1">
		<!-- Step header -->
		<div
			class="flex cursor-pointer select-none items-center gap-3 bg-surface-gray-2 px-4 py-2.5 transition-colors hover:bg-surface-gray-3"
			@click="isOpen = !isOpen"
		>
			<!-- Status indicator. The running state is the same spinning ring the
			     deploy stepper uses — the design permits two animations, and a
			     third pulse here would have been a third. -->
			<span class="flex h-5 w-5 shrink-0 items-center justify-center">
				<span
					v-if="status === 'success'"
					class="h-2.5 w-2.5 rounded-full bg-surface-green-3"
				/>
				<span
					v-else-if="status === 'error'"
					class="h-2.5 w-2.5 rounded-full bg-surface-red-4"
				/>
				<span
					v-else-if="status === 'running'"
					class="size-3.5 animate-step-spin rounded-full border-2 border-outline-gray-2 border-t-ink-blue-3"
				/>
				<span v-else class="h-2.5 w-2.5 rounded-full bg-surface-gray-4" />
			</span>

			<!-- Chevron -->
			<svg
				class="h-4 w-4 shrink-0 text-ink-gray-5 transition-transform duration-200"
				:class="{ 'rotate-90': isOpen }"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
			>
				<polyline points="9 18 15 12 9 6" />
			</svg>

			<!-- Title -->
			<span class="flex-1 truncate font-mono text-body text-ink-gray-8">{{ title }}</span>

			<!-- Duration -->
			<span v-if="duration" class="shrink-0 text-2xs text-ink-gray-5">{{ duration }}</span>
		</div>

		<!-- Output -->
		<div
			v-show="isOpen"
			ref="outputEl"
			class="max-h-[50vh] overflow-y-auto bg-surface-gray-1 px-4 py-3"
		>
			<pre
				v-if="output"
				class="whitespace-pre-wrap break-words font-mono text-2xs leading-5 text-ink-gray-7"
				>{{ output }}</pre
			>
			<span v-else class="text-2xs text-ink-gray-5">No output</span>
		</div>
	</div>
</template>

<script setup>
import { ref, watch, nextTick } from "vue";

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

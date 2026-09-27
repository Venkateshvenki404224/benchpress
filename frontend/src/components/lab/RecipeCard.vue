<template>
	<article
		class="flex flex-col rounded-card border border-outline-gray-1 bg-surface-white px-4 pb-3 pt-4 transition-shadow duration-150 ease-out hover:shadow-card-hover"
	>
		<div class="flex items-center gap-2.5">
			<span
				class="grid size-8 flex-none place-items-center rounded-md border border-outline-gray-1 bg-surface-white"
			>
				<img
					v-if="logo"
					:src="logo"
					:alt="title"
					class="size-full rounded-md object-cover"
				/>
				<AppIcon v-else :app="mark" :size="20" />
			</span>
			<div class="min-w-0 flex-1">
				<h2 class="truncate text-sm font-semibold text-ink-gray-9">{{ title }}</h2>
				<p class="truncate text-meta text-ink-gray-4">{{ subtitle }}</p>
			</div>
			<slot name="badge" />
		</div>

		<p class="mb-3 mt-2.5 min-h-[34px] text-xs text-ink-gray-6">{{ description }}</p>

		<div class="mb-3 flex flex-wrap items-center gap-1.5" data-test="recipe-chips">
			<AppChip v-for="app in shownApps" :key="app" :app="app" />
			<span
				v-for="chip in chips"
				:key="chip"
				class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-2xs text-ink-gray-6"
			>
				{{ chip }}
			</span>
		</div>

		<div class="mt-auto flex items-center gap-2 border-t border-outline-gray-1 pt-2.5">
			<slot name="footer" />
		</div>
	</article>
</template>

<script setup>
import AppChip from "@/components/AppChip.vue";
import AppIcon from "@/components/AppIcon.vue";
import { installedApps, markApp } from "@/utils/labSpecs";
import { computed } from "vue";

const props = defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
	logo: { type: String, default: "" },
	description: { type: String, default: "" },
	apps: { type: Array, default: () => [] },
	chips: { type: Array, default: () => [] },
});

const shownApps = computed(() => installedApps(props.apps));
const mark = computed(() => markApp(props.apps));
</script>

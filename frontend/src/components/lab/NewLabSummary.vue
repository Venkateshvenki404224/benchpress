<template>
	<aside
		class="rounded-card border border-outline-gray-1 bg-surface-white p-4 lg:sticky lg:top-[22px]"
		data-test="new-lab-summary"
	>
		<h2 class="text-sm font-semibold text-ink-gray-9">What gets built</h2>
		<p class="mt-1 text-xs text-ink-gray-5">
			Saving writes a Draft lab. Building runs the image job — usually two to six minutes —
			and the lab becomes Ready.
		</p>

		<ul class="mt-3">
			<li
				v-for="line in lines"
				:key="line"
				class="flex items-baseline gap-2 py-1 text-xs text-ink-gray-7"
			>
				<span class="mt-1.5 size-[5px] flex-none rounded-full bg-surface-gray-4" />
				<span class="min-w-0 break-words">{{ line }}</span>
			</li>
		</ul>

		<div class="mt-4 flex flex-col gap-2 border-t border-outline-gray-1 pt-3.5">
			<Button
				variant="solid"
				:loading="building"
				:disabled="saving || building"
				data-test="save-and-build"
				@click="emit('build')"
			>
				Save and build image
			</Button>
			<Button
				variant="subtle"
				:loading="saving"
				:disabled="saving || building"
				data-test="save-draft"
				@click="emit('draft')"
			>
				Save as draft
			</Button>
		</div>
	</aside>
</template>

<script setup>
// The rail states what this form produces, recomputed from the form on every
// keystroke — `utils/labForm.buildSummary` is the whole of it, so the sentences
// here can never describe a default the fields above have already changed.
import { Button } from "frappe-ui";

defineProps({
	lines: { type: Array, required: true },
	saving: { type: Boolean, default: false },
	building: { type: Boolean, default: false },
});

const emit = defineEmits(["build", "draft"]);
</script>

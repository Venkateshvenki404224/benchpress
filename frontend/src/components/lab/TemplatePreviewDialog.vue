<template>
	<Dialog
		v-model="isOpen"
		:options="{ title: template?.title || 'Template', size: 'lg' }"
		data-test="template-preview-dialog"
	>
		<template #body-content>
			<div v-if="template" class="flex items-start gap-2.5">
				<span
					class="grid size-9 flex-none place-items-center rounded-md border border-outline-gray-1 bg-surface-white"
				>
					<img
						v-if="template.logo"
						:src="template.logo"
						:alt="template.title"
						class="size-full rounded-md object-cover"
					/>
					<AppIcon v-else :app="mark" :size="22" />
				</span>
				<div class="min-w-0 flex-1">
					<p class="text-meta text-ink-gray-5">{{ template.frappe_version }}</p>
					<p class="mt-0.5 text-sm text-ink-gray-7" data-test="preview-description">
						{{ template.description || "No description yet." }}
					</p>
				</div>
			</div>

			<div class="mt-4" data-test="preview-apps">
				<p class="mb-1.5 text-meta font-medium text-ink-gray-5">Apps included</p>
				<div class="flex flex-wrap items-center gap-1.5">
					<AppChip v-for="app in shownApps" :key="app" :app="app" />
				</div>
			</div>

			<div class="mt-4" data-test="preview-resources">
				<p class="mb-1.5 text-meta font-medium text-ink-gray-5">Resources</p>
				<div class="flex flex-wrap items-center gap-1.5">
					<span
						v-for="chip in chips"
						:key="chip"
						class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-2xs text-ink-gray-6"
					>
						{{ chip }}
					</span>
				</div>
			</div>

			<p v-if="footnote" class="mt-4 text-meta text-ink-gray-5" data-test="preview-footnote">
				{{ footnote }}
			</p>

			<ErrorMessage class="mt-3" :message="error" />
		</template>

		<template #actions>
			<Button
				v-if="template?.lab"
				class="w-full"
				variant="solid"
				data-test="preview-open-lab"
				@click="goToLab"
			>
				Go to lab
			</Button>
			<Button
				v-else
				class="w-full"
				variant="solid"
				:loading="pending"
				data-test="preview-use-template"
				@click="confirmUse"
			>
				Use template
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
// The card's "Use template" / "Go to lab" button already does the real work;
// this dialog only shows what a template actually contains before that click,
// per GH#383 — a user should be able to see what's inside before committing.
import AppChip from "@/components/AppChip.vue";
import AppIcon from "@/components/AppIcon.vue";
import { installedApps, markApp, resourceChips } from "@/utils/labSpecs";
import { Button, Dialog, ErrorMessage } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	template: { type: Object, default: null },
	pending: { type: Boolean, default: false },
	error: { type: String, default: "" },
	footnote: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue", "use", "go-to-lab"]);

const isOpen = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

const appNames = computed(() => props.template?.apps?.map((app) => app.app_name) ?? []);
const shownApps = computed(() => installedApps(appNames.value));
const mark = computed(() => markApp(appNames.value));
const chips = computed(() => (props.template ? resourceChips(props.template) : []));

function confirmUse() {
	if (!props.template) return;
	emit("use", props.template);
}

function goToLab() {
	if (!props.template?.lab) return;
	emit("go-to-lab", props.template);
}
</script>

<template>
	<SectionCard :padded="false">
		<template #default>
			<header
				class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-b border-outline-gray-1 px-4 py-3"
			>
				<h2 class="text-sm font-semibold text-ink-gray-9">Apps</h2>
				<p class="text-meta text-ink-gray-5">
					Cloned at build time — frappe is always included
				</p>
			</header>

			<div class="px-4 py-3">
				<div
					v-if="apps.length"
					class="mb-1.5 flex gap-2 px-0.5 text-2xs font-medium text-ink-gray-5"
				>
					<span class="flex-1">App</span>
					<span class="flex-[2]">Git URL</span>
					<span class="w-[110px]">Branch</span>
					<span class="w-[26px]" />
				</div>

				<div
					v-for="(app, index) in apps"
					:key="index"
					class="mb-2 flex items-center gap-2"
					:data-test="`app-row-${index}`"
				>
					<TextInput
						class="flex-1"
						placeholder="erpnext"
						:model-value="app.app_name"
						:data-test="`app-name-${index}`"
						@update:model-value="update(index, 'app_name', $event)"
					/>
					<TextInput
						class="flex-[2] [&_input]:font-mono [&_input]:text-2xs"
						placeholder="https://github.com/frappe/erpnext"
						:model-value="app.git_url"
						:data-test="`app-url-${index}`"
						@update:model-value="update(index, 'git_url', $event)"
					/>
					<TextInput
						class="w-[110px] [&_input]:font-mono [&_input]:text-2xs"
						placeholder="version-16"
						:model-value="app.branch"
						:data-test="`app-branch-${index}`"
						@update:model-value="update(index, 'branch', $event)"
					/>
					<Button
						variant="outline"
						:data-test="`remove-app-${index}`"
						aria-label="Remove app"
						@click="emit('remove', index)"
					>
						<template #icon><XIcon class="size-3.5" /></template>
					</Button>
				</div>

				<p v-if="!apps.length" class="pb-2 text-body text-ink-gray-5">
					No apps yet — this lab builds a bare Frappe bench.
				</p>

				<Button variant="subtle" data-test="add-app" @click="emit('add')">
					<template #prefix><PlusIcon class="size-3.5" /></template>
					Add app
				</Button>
			</div>
		</template>
	</SectionCard>
</template>

<script setup>
// The Lab App child table, as the form edits it. Git URL and branch are shown
// in mono because they are values the user pastes and compares character by
// character, not prose. The card owns no state: every edit is emitted so the
// page's one reactive form stays the single source the summary rail reads.
import SectionCard from "@/components/SectionCard.vue";
import { Button, TextInput } from "frappe-ui";

import PlusIcon from "~icons/lucide/plus";
import XIcon from "~icons/lucide/x";

defineProps({
	apps: { type: Array, required: true },
});

const emit = defineEmits(["add", "remove", "update"]);

function update(index, field, value) {
	emit("update", { index, field, value });
}
</script>

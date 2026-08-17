<template>
	<Dialog v-model="isSettingsOpen" :options="{ size: '4xl' }">
		<template #body>
			<div class="flex h-[520px] max-h-[78vh]" data-test="settings">
				<nav
					class="hidden w-[196px] flex-none flex-col border-r border-outline-gray-1 bg-surface-gray-1 p-2 sm:flex"
				>
					<p class="px-2 py-1.5 text-xs text-ink-gray-5">Server</p>
					<button
						v-for="group in SETTINGS_GROUPS"
						:key="group.key"
						type="button"
						class="flex items-center gap-2 rounded px-2 py-1.5 text-left text-base"
						:class="
							group.key === activeGroup.key
								? 'bg-surface-selected text-ink-gray-9 shadow-sm'
								: 'text-ink-gray-7 hover:bg-surface-gray-2'
						"
						:data-test="`tab-${group.tab}`"
						@click="activeKey = group.key"
					>
						<component :is="group.icon" class="size-4 flex-none text-ink-gray-6" />
						{{ group.title }}
					</button>
				</nav>

				<section class="flex min-w-0 flex-1 flex-col">
					<header
						class="flex flex-none items-start gap-3 border-b border-outline-gray-1 px-5 py-3.5"
					>
						<div class="min-w-0 flex-1">
							<h2 class="text-lg font-semibold text-ink-gray-9">
								{{ activeGroup.title }}
							</h2>
							<p class="mt-0.5 text-xs text-ink-gray-5">{{ activeGroup.note }}</p>
						</div>
						<Button variant="ghost" data-test="close-settings" @click="close">
							<template #icon><XIcon class="size-4 text-ink-gray-7" /></template>
						</Button>
					</header>

					<div class="flex-1 overflow-auto px-5 py-1" :data-test="activeGroup.key">
						<p v-if="!settingsResource.doc" class="py-4 text-body text-ink-gray-5">
							Loading settings…
						</p>
						<div
							v-for="field in activeGroup.fields"
							v-else
							:key="field.key"
							class="grid items-start gap-2 border-b border-outline-gray-1 py-3.5 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_260px] sm:gap-6"
						>
							<div class="min-w-0">
								<p class="text-base text-ink-gray-8">{{ field.label }}</p>
								<p v-if="field.help" class="mt-0.5 text-2xs text-ink-gray-5">
									{{ field.help }}
								</p>
							</div>
							<div>
								<FormControl
									v-model="form[field.key]"
									:type="field.type ?? 'text'"
									:class="
										field.mono ? '[&_input]:font-mono [&_input]:text-xs' : ''
									"
									:placeholder="field.placeholder"
									:data-test="field.key"
								/>
								<ErrorMessage class="mt-1" :message="errorFor(field.key)" />
							</div>
						</div>
					</div>

					<footer
						class="flex flex-none flex-wrap items-center gap-2.5 border-t border-outline-gray-1 px-5 py-3"
					>
						<span class="text-xs text-ink-gray-5" data-test="last-saved">
							{{ lastSaved }}
						</span>
						<div class="ml-auto flex items-center gap-2">
							<Button
								variant="subtle"
								:disabled="!isDirty"
								data-test="discard-settings"
								@click="discardSettings"
							>
								Discard
							</Button>
							<Button
								variant="solid"
								:loading="settingsResource.setValue.loading"
								:disabled="!isDirty"
								data-test="save-settings"
								@click="saveSettings"
							>
								Save settings
							</Button>
						</div>
						<ErrorMessage
							class="basis-full"
							:message="settingsResource.setValue.error"
						/>
					</footer>
				</section>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
// Server settings, shaped like frappe-ui's SettingsDialog: grouped nav on the
// left, one panel per group on the right, header pinned while the body
// scrolls. The component itself only exists in frappe-ui's 1.0 beta, which
// drops ListView and ConfirmDialog this app still uses, so the layout is
// rebuilt here on 0.1.278 primitives.
import {
	SETTINGS_GROUPS,
	discardSettings,
	errorFor,
	form,
	isDirty,
	isSettingsOpen,
	lastSaved,
	saveSettings,
	settingsResource,
} from "@/data/benchpressSettings";
import { Button, Dialog, ErrorMessage, FormControl } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import XIcon from "~icons/lucide/x";

const route = useRoute();
const router = useRouter();
const activeKey = ref(SETTINGS_GROUPS[0].key);

const activeGroup = computed(
	() => SETTINGS_GROUPS.find((group) => group.key === activeKey.value) ?? SETTINGS_GROUPS[0]
);

// `/settings` still resolves — it opens this dialog over Overview — so closing
// it has to take the URL off that route rather than leave it lying.
watch(isSettingsOpen, (open) => {
	if (!open && route.name === "Settings") router.replace({ name: "Overview" });
});

function close() {
	isSettingsOpen.value = false;
}
</script>

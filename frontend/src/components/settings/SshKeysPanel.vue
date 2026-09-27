<template>
	<div class="py-3.5" data-test="ssh-keys-panel">
		<div class="mb-3 flex flex-wrap items-center gap-2">
			<p class="min-w-0 flex-1 text-xs text-ink-gray-6">
				A new key reaches a bench on its next deploy.
			</p>
			<Button variant="solid" data-test="add-ssh-key" @click="openAdd">
				<template #prefix><PlusIcon class="size-3.5" /></template>
				Add SSH key
			</Button>
		</div>

		<ul
			v-if="rows.length"
			class="divide-y divide-outline-gray-modals rounded border border-outline-gray-modals"
		>
			<li
				v-for="(key, index) in rows"
				:key="index"
				class="flex items-center gap-3 px-3 py-2.5"
				:data-test="`ssh-key-${index}`"
			>
				<KeyRoundIcon class="size-4 flex-none text-ink-gray-5" />
				<div class="min-w-0 flex-1">
					<p class="truncate text-base text-ink-gray-8">{{ key.comment || key.type }}</p>
					<p class="truncate font-mono text-2xs text-ink-gray-5">
						{{ key.fingerprint }}
					</p>
				</div>
				<Badge :label="key.badge" />
			</li>
		</ul>
		<p v-else-if="sshKeysResource.loading" class="py-4 text-body text-ink-gray-5">
			Loading keys…
		</p>
		<EmptyState
			v-else-if="sshKeysResource.data"
			message="No SSH key yet. Add the one in ~/.ssh/id_ed25519.pub."
		/>
		<ErrorMessage :message="sshKeysResource.error" />

		<Dialog v-model="adding" :options="{ title: 'Add SSH key' }">
			<template #body-content>
				<div class="[&_textarea]:font-mono [&_textarea]:text-xs" data-test="ssh-key-input">
					<Textarea
						v-model="draft"
						:rows="5"
						spellcheck="false"
						placeholder="ssh-ed25519 AAAA… you@laptop"
						aria-label="SSH public key"
					/>
				</div>
				<ErrorMessage class="mt-2" :message="addSshKeyResource.error" />
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button @click="adding = false">Cancel</Button>
					<Button
						variant="solid"
						:loading="addSshKeyResource.loading"
						:disabled="!draft.trim()"
						data-test="save-ssh-key"
						@click="submitKey"
					>
						Add key
					</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import EmptyState from "@/components/EmptyState.vue";
import { addSshKeyResource, loadSshKeys, sshKeys, sshKeysResource } from "@/data/sshKeys";
import { Badge, Button, Dialog, ErrorMessage, Textarea, toast } from "frappe-ui";
import { computed, onMounted, ref } from "vue";

import KeyRoundIcon from "~icons/lucide/key-round";
import PlusIcon from "~icons/lucide/plus";

const SHORT_TYPES = {
	"ssh-ed25519": "ed25519",
	"ssh-rsa": "rsa",
	"sk-ssh-ed25519@openssh.com": "ed25519-sk",
};

const adding = ref(false);
const draft = ref("");

const rows = computed(() => sshKeys.value.map((key) => ({ ...key, badge: shortType(key.type) })));

onMounted(loadSshKeys);

function shortType(type) {
	return type.startsWith("ecdsa-") ? "ecdsa" : SHORT_TYPES[type] ?? type;
}

function openAdd() {
	addSshKeyResource.reset();
	adding.value = true;
}

async function submitKey() {
	try {
		sshKeysResource.setData(await addSshKeyResource.submit({ key: draft.value }));
	} catch {
		return;
	}
	draft.value = "";
	adding.value = false;
	toast.success("SSH key added.");
}
</script>

<template>
	<Dialog
		v-model="isOpen"
		:options="{ title: 'code-server password', size: 'sm' }"
		data-test="code-server-dialog"
	>
		<template #body-content>
			<p class="text-body text-ink-gray-6" data-test="code-server-message">
				{{ prompt.message }}
			</p>

			<div v-if="prompt.status === PROMPT_READY" class="mt-3 flex items-center gap-2">
				<!-- Shown, not masked: this dialog exists to be read and pasted
				     into the tab that just opened. -->
				<FormControl
					class="min-w-0 flex-1"
					type="text"
					:model-value="prompt.password"
					readonly
					data-test="code-server-password"
				/>
				<Tooltip :text="copied ? 'Copied' : 'Copy'">
					<Button
						variant="subtle"
						aria-label="Copy the code-server password"
						data-test="copy-code-server-password"
						@click="copy"
					>
						<!-- A tooltip closes on the click that opens it, so the
						     icon carries the confirmation too. -->
						<template #icon>
							<component
								:is="copied ? CheckIcon : CopyIcon"
								class="size-3.5"
								:class="copied ? 'text-ink-green-3' : ''"
							/>
						</template>
					</Button>
				</Tooltip>
			</div>

			<ErrorMessage class="mt-3" :message="prompt.error" />
		</template>
	</Dialog>
</template>

<script setup>
// The password for the IDE tab the click just opened. `get_code_server_credentials`
// was written for exactly this and had no caller until now; it guards on the bench
// running and on a stored address, so a dead IDE says so here rather than after a
// login attempt.
import { PROMPT_READY, codeServerPrompt } from "@/utils/labActions";
import { Button, Dialog, ErrorMessage, FormControl, Tooltip } from "frappe-ui";
import { computed, ref } from "vue";

import CheckIcon from "~icons/lucide/check";
import CopyIcon from "~icons/lucide/copy";

const COPIED_FEEDBACK_MS = 2000;

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	loading: { type: Boolean, default: false },
	error: { type: [String, Object], default: "" },
	password: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

const isOpen = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

const prompt = computed(() =>
	codeServerPrompt({ loading: props.loading, error: props.error, password: props.password })
);

const copied = ref(false);
let copiedTimer = null;

async function copy() {
	try {
		await navigator.clipboard.writeText(prompt.value.password);
	} catch (error) {
		return;
	}
	copied.value = true;
	clearTimeout(copiedTimer);
	copiedTimer = setTimeout(() => (copied.value = false), COPIED_FEEDBACK_MS);
}
</script>

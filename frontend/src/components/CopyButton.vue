<template>
	<Tooltip :text="copied ? 'Copied' : 'Copy'">
		<Button variant="ghost" size="sm" :aria-label="`Copy ${label}`" @click="copy">
			<template #icon>
				<component
					:is="copied ? CheckIcon : CopyIcon"
					class="size-3.5"
					:class="copied ? 'text-ink-green-3' : ''"
				/>
			</template>
		</Button>
	</Tooltip>
</template>

<script setup>
import { Button, Tooltip } from "frappe-ui";
import { onBeforeUnmount, ref } from "vue";

import CheckIcon from "~icons/lucide/check";
import CopyIcon from "~icons/lucide/copy";

const COPIED_FEEDBACK_MS = 2000;

const props = defineProps({
	label: { type: String, required: true },
	value: { type: String, required: true },
});

const copied = ref(false);
let timer = null;

onBeforeUnmount(() => clearTimeout(timer));

async function copy() {
	try {
		await navigator.clipboard.writeText(props.value);
	} catch {
		return;
	}
	copied.value = true;
	clearTimeout(timer);
	timer = setTimeout(() => (copied.value = false), COPIED_FEEDBACK_MS);
}
</script>

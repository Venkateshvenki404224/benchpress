<template>
	<Badge :theme="tone.theme" :class="tone.badgeClass" size="sm" :data-test="`status-${label}`">
		<template #prefix>
			<span class="size-[5px] rounded-full" :class="tone.dot" />
		</template>
		{{ label }}
	</Badge>
</template>

<script setup>
import { labelFor, themeFor } from "@/utils/statusThemes";
import { Badge } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	status: { type: String, default: "" },
});

const tone = computed(() => themeFor(props.status));
const label = computed(() => labelFor(props.status));
</script>

<template>
	<div class="mb-3 flex flex-wrap items-center gap-2">
		<FormControl
			v-model="search"
			class="w-[240px]"
			type="text"
			:placeholder="searchPlaceholder"
			:data-test="searchTestId"
		>
			<template #prefix><SearchIcon class="size-3.5 text-ink-gray-4" /></template>
		</FormControl>
		<Select
			v-for="control in controls"
			:key="control.key"
			:model-value="selected[control.key]"
			:options="control.options"
			:class="control.class"
			:data-test="control.testId"
			@update:model-value="(value) => pick(control.key, value)"
		/>
	</div>
</template>

<script setup>
import { FormControl, Select } from "frappe-ui";
import { computed } from "vue";

import SearchIcon from "~icons/lucide/search";

const props = defineProps({
	modelValue: { type: String, default: "" },
	selected: { type: Object, required: true },
	controls: { type: Array, required: true },
	searchPlaceholder: { type: String, default: "Search" },
	searchTestId: { type: String, default: undefined },
});

const emit = defineEmits(["update:modelValue", "update:selected"]);

const search = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

function pick(key, value) {
	emit("update:selected", { ...props.selected, [key]: value });
}
</script>

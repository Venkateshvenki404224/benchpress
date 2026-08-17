<template>
	<img :src="source" :alt="label" :width="size" :height="size" class="object-contain" />
</template>

<script setup>
import { iconFor, labelFor } from "@/utils/appIcons";
import { computed } from "vue";

const props = defineProps({
	app: { type: String, default: "frappe" },
	size: { type: Number, default: 18 },
});

const source = computed(() => iconFor(props.app));
const label = computed(() => labelFor(props.app));
</script>

<template>
	<SectionCard title="Shared infrastructure" data-test="infrastructure">
		<CheckList :checks="checks" test-prefix="infrastructure" />
	</SectionCard>
</template>

<script setup>
import CheckList from "@/components/CheckList.vue";
import SectionCard from "@/components/SectionCard.vue";

// The five real checks from benchpress.diagnostics — never a placeholder list.
defineProps({
	checks: { type: Array, default: () => [] },
});
</script>

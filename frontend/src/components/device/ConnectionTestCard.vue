<template>
	<SectionCard title="A site will not open?" data-test="connection-test">
		<div v-for="(check, index) in CHECKS" :key="index" class="flex gap-2.5 py-1">
			<span class="mt-1.5 size-[5px] flex-none rounded-full bg-surface-gray-4" />
			<p class="text-2xs text-ink-gray-7">{{ check }}</p>
		</div>

		<Button
			class="mt-3 w-full"
			:loading="resource.loading"
			data-test="run-connection-test"
			@click="runTest"
		>
			Run connection test
		</Button>

		<ErrorMessage class="mt-2" :message="resource.error" />

		<div v-if="results.length" class="mt-3 border-t border-outline-gray-1 pt-2">
			<p class="mb-1 text-2xs font-semibold text-ink-gray-8" data-test="test-verdict">
				{{ verdict }}
			</p>
			<CheckList :checks="results" test-prefix="connection-check" />
		</div>
	</SectionCard>
</template>

<script setup>
// The three self-checks the design lists, plus the real test behind them. The
// result names the failing check and what to do about it — a boolean would
// leave a stranded user exactly where they started.
import CheckList from "@/components/CheckList.vue";
import SectionCard from "@/components/SectionCard.vue";
import { connectionTestResource } from "@/data/devices";
import { Button, ErrorMessage } from "frappe-ui";
import { computed } from "vue";

const CHECKS = [
	"Check the tunnel is on — the chip in the header turns green.",
	"The instance must be Running, not Stopped.",
	"One config per machine; sharing a config disconnects the other device.",
];

const emit = defineEmits(["tested"]);

const resource = connectionTestResource;
const results = computed(() => resource.data ?? []);

const verdict = computed(() => {
	const failed = results.value.find((check) => check.status !== "Active");
	return failed ? `First failing check: ${failed.label}.` : "Every check passed.";
});

async function runTest() {
	await resource.fetch();
	emit("tested");
}
</script>

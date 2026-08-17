<template>
	<section
		class="rounded-card border border-outline-gray-1 bg-surface-white"
		data-test="raw-log"
	>
		<header class="flex items-center gap-2 px-4 py-2.5">
			<button
				class="flex min-w-0 flex-1 items-center gap-2 text-left"
				:aria-expanded="open"
				data-test="raw-log-toggle"
				@click="open = !open"
			>
				<ChevronRightIcon
					class="size-3.5 flex-none text-ink-gray-5 transition-transform duration-150"
					:class="open ? 'rotate-90' : ''"
				/>
				<span class="text-body font-medium text-ink-gray-8">Raw log</span>
				<span class="text-2xs text-ink-gray-5" data-test="raw-log-count">
					{{ lineCount }} {{ lineCount === 1 ? "line" : "lines" }}
				</span>
			</button>
			<Button
				variant="subtle"
				size="sm"
				:disabled="!lines.length"
				data-test="raw-log-download"
				@click="download"
			>
				<template #prefix><DownloadIcon class="size-3.5" /></template>
				Download
			</Button>
		</header>

		<div
			v-if="open"
			class="max-h-[420px] overflow-auto border-t border-outline-gray-1 bg-surface-gray-1 px-4 py-3"
			data-test="raw-log-body"
		>
			<p
				v-for="(line, index) in lines"
				:key="index"
				class="whitespace-pre-wrap break-words font-mono text-2xs leading-5"
				:class="TONES[classifyLine(line)]"
			>
				{{ line }}
			</p>
		</div>
	</section>
</template>

<script setup>
import { classifyLine } from "@/utils/deploySteps";
import { Button } from "frappe-ui";
import { computed, ref } from "vue";
import ChevronRightIcon from "~icons/lucide/chevron-right";
import DownloadIcon from "~icons/lucide/download";

// The log is no longer the interface — the stepper is — so it sits collapsed
// under it, colour-coded by what each line is and downloadable whole.
const TONES = {
	error: "text-ink-red-4",
	success: "text-ink-green-3",
	step: "text-ink-blue-3",
	info: "text-ink-gray-6",
};

const props = defineProps({
	rawLog: { type: String, default: "" },
	fileName: { type: String, default: "deploy.log" },
});

const open = ref(false);

const lines = computed(() => props.rawLog.split("\n").filter((line) => line.trim()));
const lineCount = computed(() => lines.value.length);

function download() {
	const url = URL.createObjectURL(new Blob([props.rawLog], { type: "text/plain" }));
	const link = document.createElement("a");
	link.href = url;
	link.download = props.fileName;
	link.click();
	URL.revokeObjectURL(url);
}
</script>

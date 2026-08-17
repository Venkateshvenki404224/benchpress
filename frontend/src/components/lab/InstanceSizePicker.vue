<template>
	<div>
		<div class="mb-1.5 flex flex-wrap items-baseline gap-x-2">
			<p class="text-xs font-medium text-ink-gray-7">Instance size</p>
			<p class="text-2xs text-ink-gray-5">
				Sets the container limits{{ priced ? " and the price" : "" }}
			</p>
		</div>

		<div
			class="grid gap-2"
			style="grid-template-columns: repeat(auto-fit, minmax(148px, 1fr))"
			data-test="instance-size-picker"
		>
			<button
				v-for="size in sizes"
				:key="size.name"
				type="button"
				class="rounded-card border px-3 py-2 text-left transition-colors"
				:class="
					size.name === modelValue
						? 'border-outline-gray-4 bg-surface-gray-2'
						: 'border-outline-gray-1 bg-surface-white hover:bg-surface-gray-1'
				"
				:data-test="`instance-size-${size.name}`"
				:aria-pressed="size.name === modelValue"
				@click="emit('update:modelValue', size.name)"
			>
				<span class="block text-xs font-medium text-ink-gray-9">{{
					size.size_label
				}}</span>
				<span class="mt-0.5 block text-2xs text-ink-gray-5">{{ specLine(size) }}</span>
				<span v-if="priced" class="mt-0.5 block text-2xs font-medium text-ink-gray-7">
					{{ rateLabel(size.credits_per_hour) }}
				</span>
			</button>
		</div>
	</div>
</template>

<script setup>
// The price belongs at the moment of choosing, which is here — a size is the only
// field on this form that costs money, so it is the only one that shows a rate.
// The rate is hidden entirely when credits are off: a self-hoster picking a
// container size should not be shown a currency that does not exist for them.
import { rateLabel } from "@/utils/credits";
import { cpuLabel, memoryLabel } from "@/utils/labSpecs";

defineProps({
	sizes: { type: Array, required: true },
	modelValue: { type: String, default: "" },
	priced: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

function specLine(size) {
	return `${memoryLabel(size.memory_limit)} · ${cpuLabel(size.cpu_cores)}`;
}
</script>

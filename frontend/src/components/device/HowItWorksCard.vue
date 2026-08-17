<template>
	<SectionCard title="How this works" data-test="how-this-works">
		<p class="text-2xs text-ink-gray-6">
			Instances are never published to the internet. WireGuard is the only way in.
		</p>
		<div v-for="(step, index) in STEPS" :key="index" class="mt-2.5 flex gap-2.5">
			<span
				class="flex size-[17px] flex-none items-center justify-center rounded-full bg-surface-gray-2 text-[10px] font-semibold text-ink-gray-7"
			>
				{{ index + 1 }}
			</span>
			<p class="text-2xs text-ink-gray-7">{{ step }}</p>
		</div>
	</SectionCard>
</template>

<script setup>
// The three steps of the journey, in the order a new user performs them.
import SectionCard from "@/components/SectionCard.vue";

const STEPS = [
	"Register the machine here — it gets a fixed IP on the lab network.",
	"Import the config into the WireGuard app, or scan the QR on a phone.",
	"Turn the tunnel on. Sites, SSH and VS Code resolve immediately.",
];
</script>

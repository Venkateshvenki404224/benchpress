<template>
	<div class="flex flex-col items-center gap-2">
		<canvas
			v-show="text"
			ref="canvas"
			class="rounded-md border border-outline-gray-1 bg-white p-1"
			data-test="device-qr-canvas"
		/>
		<div
			v-if="!text"
			class="flex size-[112px] flex-col items-center justify-center gap-1.5 rounded-md border border-dashed border-outline-gray-2 px-2 text-center text-2xs text-ink-gray-5"
			data-test="device-qr-placeholder"
		>
			<QrCodeIcon class="size-5" />
			{{ placeholder }}
		</div>
		<p v-if="text" class="max-w-[180px] text-center text-2xs text-ink-gray-5">
			Scan with the WireGuard app
		</p>
	</div>
</template>

<script setup>
// The QR is drawn on a white canvas in both themes on purpose: a scanner reads
// dark-on-light, so inverting it in dark mode would make it unscannable.
import QRCode from "qrcode";
import { nextTick, ref, watch } from "vue";

import QrCodeIcon from "~icons/lucide/qr-code";

const props = defineProps({
	text: { type: String, default: "" },
	size: { type: Number, default: 180 },
	placeholder: { type: String, default: "QR appears once the device is registered" },
});

const canvas = ref(null);

watch(() => props.text, render, { immediate: true });

async function render(text) {
	if (!text) return;
	await nextTick();
	if (!canvas.value) return;
	await QRCode.toCanvas(canvas.value, text, { width: props.size, margin: 1 });
}
</script>

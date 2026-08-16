<template>
	<section class="rounded-card border border-outline-gray-1 bg-surface-white">
		<header
			v-if="title || $slots.action"
			class="flex items-center gap-2 border-b border-outline-gray-1 px-4 py-3"
		>
			<h2 class="text-sm font-semibold text-ink-gray-9">{{ title }}</h2>
			<div class="ml-auto flex items-center gap-2">
				<slot name="action" />
			</div>
		</header>
		<div :class="padded ? 'p-4' : ''">
			<slot />
		</div>
	</section>
</template>

<script setup>
// The outlined card the design uses everywhere: 1px hairline, 11px radius,
// white surface. Cards are outlined, never shadowed.
defineProps({
	title: { type: String, default: "" },
	// Lists bleed to the card edge; everything else gets the 15-18px padding.
	padded: { type: Boolean, default: true },
});
</script>

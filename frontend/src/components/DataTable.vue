<template>
	<!-- The hook sits here, not on ListView: it declares `inheritAttrs: false`
	     and forwards only class and style, so any other attribute is dropped. -->
	<div
		class="overflow-hidden rounded-card border border-outline-gray-1 bg-surface-white"
		:data-test="dataTest"
	>
		<ListView :columns="columns" :rows="rows" :options="tableOptions" row-key="name">
			<!-- The design's column header is a strip flush with the card, not
			     frappe-ui's floating rounded pill. -->
			<ListHeader class="!mb-0 !rounded-none !bg-surface-gray-1 !px-4 !py-2.5" />
			<ListRows />
			<template #cell="cell">
				<slot name="cell" v-bind="cell" />
			</template>
		</ListView>
	</div>
</template>

<script setup>
// The one table both list surfaces use: an outlined card that clips the header
// strip, rows tall enough for the two-line name cell, and a single `cell` slot
// the page fills per column. Below the card's width the table scrolls inside
// it — ListView's own `overflow-x-auto` — rather than crushing the name column.
import { ListHeader, ListRows, ListView } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	columns: { type: Array, required: true },
	rows: { type: Array, required: true },
	// Where a row click goes; `null` leaves rows inert.
	rowRoute: { type: Function, default: null },
	rowHeight: { type: Number, default: 52 },
	dataTest: { type: String, default: "" },
});

const tableOptions = computed(() => ({
	getRowRoute: props.rowRoute,
	rowHeight: props.rowHeight,
	showTooltip: false,
	selectable: false,
	resizeColumn: false,
}));
</script>

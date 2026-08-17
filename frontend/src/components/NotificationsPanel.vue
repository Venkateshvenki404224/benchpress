<template>
	<!-- A backdrop that dims nothing: it exists so a click anywhere outside
	     the panel closes it, the way the sidebar's own menus behave. -->
	<div v-if="isNotificationsOpen" class="absolute inset-0 z-20" @click="close" />

	<Transition
		enter-active-class="transition-transform duration-200 ease-out"
		leave-active-class="transition-transform duration-150 ease-in"
		enter-from-class="-translate-x-full"
		leave-to-class="-translate-x-full"
	>
		<aside
			v-if="isNotificationsOpen"
			class="absolute inset-y-0 left-0 z-30 flex w-[420px] max-w-full flex-col border-r border-outline-gray-1 bg-surface-white shadow-2xl"
			data-test="notifications"
		>
			<header class="flex flex-none items-center gap-2 px-4 py-3.5">
				<h2 class="text-lg font-semibold text-ink-gray-9">Notifications</h2>
				<Button
					class="ml-auto"
					variant="ghost"
					data-test="close-notifications"
					@click="close"
				>
					<template #icon><XIcon class="size-4 text-ink-gray-7" /></template>
				</Button>
			</header>

			<div class="min-h-0 flex-1 overflow-auto">
				<EmptyState
					v-if="!notifications.length"
					message="You are all caught up!"
					:icon="BellIcon"
				/>
				<ActivityRow
					v-for="(event, index) in notifications"
					:key="`${event.timestamp}-${index}`"
					:event="event"
					class="border-b border-outline-gray-1 last:border-b-0"
					:data-test="`notification-${index}`"
				/>
			</div>
		</aside>
	</Transition>
</template>

<script setup>
// The panel behind the sidebar's Notifications item: it slides out beside the
// sidebar rather than opening a modal, so the screen underneath stays put.
// It reports the same deploy and build events the Overview feed shows, so a
// user on Labs or Devices still learns that a deploy failed.
import ActivityRow from "@/components/ActivityRow.vue";
import EmptyState from "@/components/EmptyState.vue";
import { isNotificationsOpen, notifications } from "@/data/notifications";
import { Button } from "frappe-ui";
import { onBeforeUnmount, onMounted } from "vue";

import BellIcon from "~icons/lucide/bell";
import XIcon from "~icons/lucide/x";

function close() {
	isNotificationsOpen.value = false;
}

function onKeydown(event) {
	if (event.key === "Escape") close();
}

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

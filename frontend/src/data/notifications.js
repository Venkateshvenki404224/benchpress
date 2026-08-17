import { overviewResource } from "@/data/overview";
import { computed, ref } from "vue";

/**
 * BenchPress has no notification store of its own; what a user wants to be
 * told about is exactly the deploy and build activity the Overview already
 * scopes to them, so the panel reads that one resource.
 */
export const isNotificationsOpen = ref(false);

export const notifications = computed(() => overviewResource.data?.activity ?? []);

/** Failures are the only events worth a badge — successes need no chasing. */
export const attentionCount = computed(
	() => notifications.value.filter((event) => event.log_type === "error").length
);

/** The sidebar item is the only trigger, so it opens and closes the panel. */
export function toggleNotifications() {
	if (isNotificationsOpen.value) {
		isNotificationsOpen.value = false;
		return;
	}
	if (!overviewResource.data) overviewResource.reload();
	isNotificationsOpen.value = true;
}

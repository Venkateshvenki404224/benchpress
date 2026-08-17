import { computed, ref } from "vue";

/**
 * The palette is opened from the sidebar and from the keyboard, so its open
 * state lives outside the component that renders it.
 */
export const isSearchOpen = ref(false);

export const searchShortcut = computed(() =>
	/Mac|iPhone|iPad/.test(navigator.platform ?? "") ? "⌘K" : "Ctrl K"
);

export function openSearch() {
	isSearchOpen.value = true;
}

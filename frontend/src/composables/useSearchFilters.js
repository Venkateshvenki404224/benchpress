import { ALL, matches, matchesSearch, optionsFrom } from "@/utils/filters";
import { computed, ref } from "vue";

/** Search text plus one select per filter, and the rows that pass them all. */
export function useSearchFilters(source, { searchIn, filters }) {
	const search = ref("");
	const selected = ref(allOf(filters));

	const controls = computed(() =>
		filters.map((filter) => ({
			key: filter.key,
			testId: filter.testId,
			class: filter.class,
			options: optionsFrom(
				filter.label,
				source.value.flatMap((row) => filter.value(row)),
				filter.labelFor
			),
		}))
	);

	const rows = computed(() => source.value.filter(passes));

	function passes(row) {
		return (
			filters.every((filter) => matches(filter.value(row), selected.value[filter.key])) &&
			matchesSearch(searchIn(row), search.value)
		);
	}

	function clearFilters() {
		search.value = "";
		selected.value = allOf(filters);
	}

	return { search, selected, controls, rows, clearFilters };
}

function allOf(filters) {
	return Object.fromEntries(filters.map((filter) => [filter.key, ALL]));
}

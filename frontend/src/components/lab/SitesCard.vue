<template>
	<SectionCard title="Sites" :padded="!rows.length" data-test="sites-card">
		<ul v-if="rows.length" class="divide-y divide-outline-gray-1">
			<li
				v-for="site in rows"
				:key="site.name"
				class="flex flex-wrap items-center gap-3 px-4 py-3"
				:data-test="`site-${site.name}`"
			>
				<div class="min-w-0 flex-1">
					<p class="truncate text-body font-medium text-ink-gray-9">
						{{ site.site_name }}
					</p>
					<div class="mt-1 flex flex-wrap gap-1">
						<AppChip v-for="app in site.apps" :key="app" :app="app" />
						<span v-if="!site.apps?.length" class="text-2xs text-ink-gray-4">
							Bare site
						</span>
					</div>
					<!-- A disabled button emits no hover events, so the reason is a
					     caption under the row and never a tooltip. -->
					<p
						v-if="site.open.hint"
						class="mt-1 text-2xs text-ink-gray-5"
						:data-test="`site-hint-${site.name}`"
					>
						{{ site.open.hint }}
					</p>
				</div>
				<StatusBadge :status="site.status" />
				<Button
					variant="subtle"
					size="sm"
					:disabled="site.open.disabled"
					:data-test="`open-site-${site.name}`"
					@click="emit('open', site)"
				>
					{{ site.open.label }}
				</Button>
			</li>
		</ul>

		<EmptyState
			v-else
			message="No site yet — one is created automatically when this lab is deployed."
		/>
	</SectionCard>
</template>

<script setup>
// The sites a bench serves, and nothing more: a site is created by the deploy,
// so there is no create path to offer here. A site that cannot be opened is
// never hidden — its button stays, disabled, and names which of the two
// reasons applies, because a stopped container and a down tunnel send the user
// somewhere different.
import AppChip from "@/components/AppChip.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { siteOpenAction } from "@/utils/labActions";
import { Button } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	// Each site as `get_lab` returned it, plus the `url` its Open button opens.
	sites: { type: Array, default: () => [] },
	reachable: { type: Boolean, default: false },
});

const emit = defineEmits(["open"]);

// The card renders what it is handed: the address comes from the page, and the
// button's state from one pure function, so neither is decided in a template.
const rows = computed(() =>
	props.sites.map((site) => ({
		...site,
		open: siteOpenAction({
			status: site.status,
			url: site.url,
			vpnConnected: props.reachable,
		}),
	}))
);
</script>

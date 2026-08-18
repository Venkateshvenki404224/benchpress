<template>
	<SectionCard title="Sites" :padded="!sites.length" data-test="sites-card">
		<ul v-if="sites.length" class="divide-y divide-outline-gray-1">
			<li
				v-for="site in sites"
				:key="site.name"
				class="flex flex-wrap items-center gap-3 px-4 py-3"
				:data-test="`site-${site.name}`"
			>
				<div class="min-w-0 flex-1">
					<p class="truncate text-body font-medium text-ink-gray-9">
						{{ site.full_domain || site.site_name }}
					</p>
					<div class="mt-1 flex flex-wrap gap-1">
						<AppChip v-for="app in site.apps" :key="app" :app="app" />
						<span v-if="!site.apps?.length" class="text-2xs text-ink-gray-4">
							Bare site
						</span>
					</div>
				</div>
				<StatusBadge :status="site.status" />
				<Button
					variant="subtle"
					size="sm"
					:disabled="!openable(site)"
					:data-test="`open-site-${site.name}`"
					@click="emit('open', site)"
				>
					{{ openable(site) ? "Open" : "Unreachable" }}
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
// so there is no create path to offer here. A site that cannot be reached is
// never hidden — its button stays, disabled, and says "Unreachable" so the
// tunnel, or a site nothing serves, is the obvious suspect.
import AppChip from "@/components/AppChip.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { Button } from "frappe-ui";

const props = defineProps({
	// Each site as `get_lab` returned it, plus the `url` its Open button opens.
	sites: { type: Array, default: () => [] },
	reachable: { type: Boolean, default: false },
});

const emit = defineEmits(["open"]);

function openable(site) {
	return props.reachable && !!site.url;
}
</script>

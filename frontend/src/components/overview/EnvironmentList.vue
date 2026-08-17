<template>
	<SectionCard :title="heading" :padded="false" data-test="environments">
		<template #action>
			<router-link to="/bench-instances" class="text-meta text-ink-blue-3">
				All instances
			</router-link>
		</template>

		<EmptyState
			v-if="!environments.length"
			message="No environments yet — deploying a lab creates one, with its own site and IDE."
		>
			<template #action>
				<Button variant="solid" @click="$router.push('/labs/templates')">
					Start from a template
				</Button>
			</template>
		</EmptyState>

		<div
			v-for="environment in environments"
			:key="environment.name"
			role="button"
			tabindex="0"
			class="flex cursor-pointer items-center gap-3 border-b border-outline-gray-1 px-4 py-3 last:border-b-0 hover:bg-surface-gray-1"
			:data-test="`environment-${environment.name}`"
			@click="openLab(environment)"
			@keydown.enter="openLab(environment)"
		>
			<span
				class="grid size-[30px] flex-none place-items-center rounded-md border border-outline-gray-1 bg-surface-white"
			>
				<AppIcon :app="environment.app" :size="18" />
			</span>
			<!-- `bench_name` is `md5(user + lab)`; every surface names a bench
			     after the lab it runs instead — `utils/labSpecs.benchLabel`. -->
			<div class="min-w-0 flex-1">
				<p class="truncate text-body font-medium text-ink-gray-9">
					{{ benchLabel(environment.lab) || environment.name }}
				</p>
				<p class="truncate text-2xs text-ink-gray-4">
					{{ environment.site || environment.lab_title }}
				</p>
			</div>
			<span class="hidden text-2xs sm:block" :class="healthClass(environment)">
				{{ healthLabel(environment) }}
			</span>
			<StatusBadge :status="environment.status" />
			<Button
				variant="subtle"
				size="sm"
				:disabled="isUnreachable(environment)"
				:data-test="`environment-action-${environment.name}`"
				@click.stop="runAction(environment)"
			>
				{{ actionLabel(environment) }}
			</Button>
		</div>
	</SectionCard>
</template>

<script setup>
import AppIcon from "@/components/AppIcon.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { benchLabel } from "@/utils/labSpecs";
import { labelFor, themeFor } from "@/utils/statusThemes";
import { Button } from "frappe-ui";
import { computed } from "vue";
import { useRouter } from "vue-router";

const props = defineProps({
	environments: { type: Array, default: () => [] },
	isAdmin: { type: Boolean, default: false },
	vpnConnected: { type: Boolean, default: false },
});

const router = useRouter();
const heading = computed(() => (props.isAdmin ? "All instances" : "My environments"));

function healthLabel(environment) {
	return labelFor(environment.container_health);
}

function healthClass(environment) {
	return themeFor(environment.container_health).text;
}

function hasSite(environment) {
	return environment.status === "Running" && !!environment.site;
}

// Nothing unreachable is hidden — it is disabled and the label says why.
function isUnreachable(environment) {
	return hasSite(environment) && !props.vpnConnected;
}

function actionLabel(environment) {
	if (!hasSite(environment)) return "View";
	return props.vpnConnected ? "Open site" : "Open site — VPN off";
}

function runAction(environment) {
	if (hasSite(environment)) {
		window.open(`http://${environment.site}`, "_blank", "noopener");
		return;
	}
	openLab(environment);
}

function openLab(environment) {
	router.push({ name: "LabDetail", params: { labId: environment.lab } });
}
</script>

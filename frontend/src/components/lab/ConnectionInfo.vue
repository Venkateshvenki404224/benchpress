<template>
	<div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
		<h2 class="mb-3 text-base font-semibold text-ink-gray-9">Connection Information</h2>
		<p class="mb-5 text-sm leading-relaxed text-ink-gray-6">
			This server is accessible through
			<strong class="text-ink-gray-8">Code</strong> or
			<strong class="text-ink-gray-8">SSH</strong>. Code is accessible under VPN in one click
			and you do not have to SSH into your lab. Just ensure you are connected to VPN. To keep
			you secure, this password changes during every redeploy.
		</p>
		<div class="space-y-0 divide-y divide-outline-gray-1">
			<div class="flex items-center gap-4 py-3">
				<label class="w-36 shrink-0 text-sm font-medium text-ink-gray-9"
					>Public Access</label
				>
				<div class="flex flex-1 items-center gap-3">
					<Switch
						:modelValue="!!bench.is_public"
						:disabled="visibilityLoading"
						@update:modelValue="(v) => emit('toggle-visibility', v)"
					/>
					<span class="text-sm text-ink-gray-6">{{
						bench.is_public
							? "Anyone with the link can open this bench"
							: "Visitors must sign in with the credentials below"
					}}</span>
				</div>
			</div>
			<CopyableField
				v-if="!bench.is_public && bench.public_username"
				label="Access Username"
				:value="bench.public_username"
			/>
			<CopyableField
				v-if="!bench.is_public && bench.public_password"
				label="Access Password"
				:value="bench.public_password"
				masked
			/>
			<CopyableField
				v-if="bench.public_url"
				label="Public URL"
				:value="bench.public_url"
				:href="bench.public_url"
			/>
			<CopyableField label="Device IP" :value="benchIp" />
			<CopyableField label="SSH Command" :value="sshCommand" />
			<CopyableField label="Username" :value="sshUsername" />
			<CopyableField label="su Password" :value="sshPassword" masked />
			<CopyableField label="Admin Password" :value="adminPassword" masked />
			<CopyableField label="VS Port Forward" :value="siteUrl" />
			<CopyableField
				v-if="enableCodeServer && codeServerUrl"
				label="VS Code URL"
				:value="codeServerUrl"
			/>
			<CopyableField
				v-if="enableCodeServer && codeServerPassword"
				label="VS Code Password"
				:value="codeServerPassword"
				masked
			/>
		</div>
	</div>
</template>

<script setup>
import { Switch } from "frappe-ui";
import CopyableField from "@/components/CopyableField.vue";

defineProps({
	bench: { type: Object, required: true },
	enableCodeServer: { type: Boolean, default: false },
	visibilityLoading: { type: Boolean, default: false },
	benchIp: { type: String, default: null },
	sshCommand: { type: String, default: null },
	sshUsername: { type: String, default: null },
	sshPassword: { type: String, default: null },
	adminPassword: { type: String, default: null },
	siteUrl: { type: String, default: null },
	codeServerUrl: { type: String, default: null },
	codeServerPassword: { type: String, default: null },
});

const emit = defineEmits(["toggle-visibility"]);
</script>

<template>
	<SectionCard title="Connection details" :padded="false" data-test="connection-details">
		<template #action>
			<Button
				variant="subtle"
				size="sm"
				data-test="reveal-secrets"
				@click="revealed = !revealed"
			>
				<template #prefix>
					<component :is="revealed ? EyeOffIcon : EyeIcon" class="size-3.5" />
				</template>
				{{ revealed ? "Hide secrets" : "Reveal secrets" }}
			</Button>
		</template>

		<p class="border-b border-outline-gray-1 px-4 py-2.5 text-2xs text-ink-gray-5">
			The public URL works from anywhere; everything else is reachable only over the VPN.
			Passwords are regenerated on every redeploy.
		</p>

		<ul class="divide-y divide-outline-gray-1">
			<li
				v-for="row in rows"
				:key="row.key"
				class="flex items-center gap-3 px-4 py-2.5"
				:data-test="`detail-${row.key}`"
			>
				<span class="w-32 flex-none text-meta text-ink-gray-7">{{ row.label }}</span>

				<!-- frappe-ui's `Password` keeps its reveal state in a local ref
				     with no prop to drive it, so a single shared toggle cannot
				     control a column of them. This is the same FormControl type
				     swap `Password` performs internally — a real mask, unlike the
				     literal "••••" string this screen used to render while
				     copying the plaintext. -->
				<FormControl
					v-if="row.secret"
					class="min-w-0 flex-1"
					:type="revealed ? 'text' : 'password'"
					:model-value="row.value"
					readonly
					:data-test="`secret-${row.key}`"
				/>
				<code
					v-else
					class="min-w-0 flex-1 truncate rounded bg-surface-gray-1 px-2.5 py-1.5 font-mono text-2xs text-ink-gray-8"
				>
					{{ row.value }}
				</code>

				<Tooltip :text="copiedKey === row.key ? 'Copied' : 'Copy'">
					<Button
						variant="ghost"
						size="sm"
						:aria-label="`Copy ${row.label}`"
						:data-test="`copy-${row.key}`"
						@click="copy(row)"
					>
						<!-- A tooltip closes on the click that opens it, so the
						     icon carries the confirmation too. -->
						<template #icon>
							<component
								:is="copiedKey === row.key ? CheckIcon : CopyIcon"
								class="size-3.5"
								:class="copiedKey === row.key ? 'text-ink-green-3' : ''"
							/>
						</template>
					</Button>
				</Tooltip>
			</li>
		</ul>
	</SectionCard>
</template>

<script setup>
// The §8.8 fix. Every secret is masked until one toggle reveals all of them,
// and the reveal state is local to this component, so navigating away and back
// re-masks. Copy feedback is a tooltip on the button that was pressed, which
// replaces the teleported page-corner alert the old screen used.
import SectionCard from "@/components/SectionCard.vue";
import { ideUrl, privateSiteUrl } from "@/utils/labActions";
import { Button, FormControl, Tooltip } from "frappe-ui";
import { computed, ref } from "vue";

import CheckIcon from "~icons/lucide/check";
import CopyIcon from "~icons/lucide/copy";
import EyeIcon from "~icons/lucide/eye";
import EyeOffIcon from "~icons/lucide/eye-off";

const COPIED_FEEDBACK_MS = 2000;
const MISSING = "—";

const props = defineProps({
	lab: { type: Object, required: true },
	bench: { type: Object, required: true },
	// What `get_bench_credentials` returned; empty until it resolves.
	credentials: { type: Object, default: () => ({}) },
});

const revealed = ref(false);
const copiedKey = ref("");
let copiedTimer = null;

const address = computed(() => props.bench.wg_ip || props.bench.container_ip || "");

const rows = computed(() =>
	[
		// Both addresses, always: the public one for sharing outside the tunnel,
		// the private one for teammates already on the VPN.
		{ key: "public-url", label: "Public URL", value: props.bench.public_url },
		{ key: "private-url", label: "Private URL (VPN)", value: privateSiteUrl(props.bench) },
		{ key: "wg-ip", label: "WireGuard IP", value: props.bench.wg_ip },
		{ key: "runtime", label: "Runtime", value: props.bench.runtime },
		codeServerRow(),
		sshRow(),
		{
			key: "ssh-password",
			label: "SSH password",
			value: secret("ssh_password"),
			secret: true,
		},
		{
			key: "admin-password",
			label: "Admin password",
			value: secret("admin_password"),
			secret: true,
		},
		codeServerPasswordRow(),
	]
		.filter(Boolean)
		// A secret that does not exist yet has nothing to hide: masking the
		// em-dash would render one bullet and read as a one-character password.
		.map((row) => ({
			...row,
			secret: !!(row.secret && row.value),
			value: row.value || MISSING,
		}))
);

function codeServerRow() {
	if (!props.lab.enable_code_server) return null;
	// Through the same helper the IDE button uses, so what is shown is what opens.
	return { key: "code-server", label: "code-server", value: ideUrl(props.bench) };
}

function codeServerPasswordRow() {
	if (!props.lab.enable_code_server) return null;
	return {
		key: "code-server-password",
		label: "code-server password",
		value: secret("code_server_password"),
		secret: true,
	};
}

function sshRow() {
	const user = props.bench.ssh_username;
	return {
		key: "ssh",
		label: "SSH",
		value: user && address.value ? `ssh ${user}@${address.value}` : "",
	};
}

function secret(field) {
	return props.credentials?.[field] || "";
}

async function copy(row) {
	if (row.value === MISSING) return;
	try {
		await navigator.clipboard.writeText(row.value);
	} catch (error) {
		return;
	}
	copiedKey.value = row.key;
	clearTimeout(copiedTimer);
	copiedTimer = setTimeout(() => (copiedKey.value = ""), COPIED_FEEDBACK_MS);
}
</script>

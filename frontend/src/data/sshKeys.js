import { createResource } from "frappe-ui";
import { computed } from "vue";

export const sshKeysResource = createResource({ url: "benchpress.user.list_ssh_keys" });
export const addSshKeyResource = createResource({ url: "benchpress.user.add_ssh_key" });
export const removeSshKeyResource = createResource({ url: "benchpress.user.remove_ssh_key" });

export const sshKeys = computed(() => sshKeysResource.data ?? []);
export const hasSshKey = computed(() => sshKeys.value.length > 0);

export function loadSshKeys() {
	if (!sshKeysResource.fetched && !sshKeysResource.loading) sshKeysResource.fetch();
}

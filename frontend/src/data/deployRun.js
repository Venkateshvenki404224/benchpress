import { reactive } from "vue";

/**
 * The deploy the user is currently watching.
 *
 * A deploy can be started from a template card, from New lab or from Lab
 * detail, and all three show the same dialog, so the run being watched is app
 * state rather than page state. Only the live stream lives here: the dialog
 * follows a run it just started, and the persisted log is what Lab detail
 * reads when someone comes back to a run already in flight.
 */
export const deployRun = reactive({
	open: false,
	labId: "",
	benchName: "",
	log: "",
});

export function openDeployRun({ labId, benchName }) {
	deployRun.labId = labId;
	deployRun.benchName = benchName;
	deployRun.log = "";
	deployRun.open = true;
}

/** A line from `bench_deploy_log`, appended in arrival order. */
export function appendDeployLine(line) {
	deployRun.log += `${line}\n`;
}

/** "Run in background" — the deploy carries on, only the dialog goes away. */
export function closeDeployRun() {
	deployRun.open = false;
}

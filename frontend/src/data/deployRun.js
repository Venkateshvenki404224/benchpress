import { reactive } from "vue";

/**
 * The deploy the user is currently watching.
 *
 * A deploy can be started from a template card, from New lab or from Lab
 * detail, and all three show the same dialog, so the run being watched is app
 * state rather than page state. Only the live stream lives here: the dialog
 * follows a run it just started, and the persisted log is what Lab detail
 * reads when someone comes back to a run already in flight.
 *
 * Two streams feed one run. One click launches one job that builds the image
 * and then deploys from it, so `bench_deploy_log` carries the pipeline and
 * `lab_build_log` carries Docker's own output for the build half. They are
 * buffered apart because the stepper is derived from the deploy log alone —
 * mixing Docker's thousands of lines into it would break the derivation.
 */
export const deployRun = reactive({
	open: false,
	labId: "",
	labTitle: "",
	benchName: "",
	willBuild: false,
	log: "",
	buildLog: "",
});

export function openDeployRun({ labId, labTitle = "", benchName, willBuild = false }) {
	deployRun.labId = labId;
	deployRun.labTitle = labTitle;
	deployRun.benchName = benchName;
	deployRun.willBuild = willBuild;
	deployRun.log = "";
	deployRun.buildLog = "";
	deployRun.open = true;
}

/** A line from `bench_deploy_log`, appended in arrival order. */
export function appendDeployLine(line) {
	deployRun.log += `${line}\n`;
}

/** A line from `lab_build_log` — Docker's own output, not a pipeline step. */
export function appendBuildLine(line) {
	deployRun.buildLog += `${line}\n`;
}

/** "Run in background" — the deploy carries on, only the dialog goes away. */
export function closeDeployRun() {
	deployRun.open = false;
}

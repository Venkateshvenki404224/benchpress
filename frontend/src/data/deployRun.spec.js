import { beforeEach, describe, expect, it } from "vitest";
import {
	appendBuildLine,
	appendDeployLine,
	closeDeployRun,
	deployRun,
	openDeployRun,
} from "./deployRun";

describe("the run the dialog is watching", () => {
	beforeEach(() => {
		openDeployRun({ labId: "crm", labTitle: "Frappe CRM", benchName: "b1", willBuild: true });
	});

	it("carries what the launch handed back", () => {
		expect(deployRun).toMatchObject({
			open: true,
			labId: "crm",
			labTitle: "Frappe CRM",
			benchName: "b1",
			willBuild: true,
		});
	});

	it("defaults the title and the build hint when a caller omits them", () => {
		openDeployRun({ labId: "support", benchName: "b2" });

		expect(deployRun.labTitle).toBe("");
		expect(deployRun.willBuild).toBe(false);
	});

	it("keeps the two streams apart", () => {
		appendDeployLine("=== Deploy started ===");
		appendBuildLine("Step 1/9 : FROM frappe/base");
		appendDeployLine("=== Step 2/11: Preparing the lab image [image @0.0s] ===");

		expect(deployRun.log).toBe(
			"=== Deploy started ===\n=== Step 2/11: Preparing the lab image [image @0.0s] ===\n"
		);
		expect(deployRun.buildLog).toBe("Step 1/9 : FROM frappe/base\n");
	});

	// A second launch must not show the previous run's lines under its stepper.
	it("empties both buffers when the next run opens", () => {
		appendDeployLine("old deploy line");
		appendBuildLine("old build line");

		openDeployRun({ labId: "hr", labTitle: "Frappe HR", benchName: "b3" });

		expect(deployRun.log).toBe("");
		expect(deployRun.buildLog).toBe("");
	});

	it("only hides the dialog when the run goes to the background", () => {
		appendDeployLine("still running");
		closeDeployRun();

		expect(deployRun.open).toBe(false);
		expect(deployRun.log).toBe("still running\n");
		expect(deployRun.benchName).toBe("b1");
	});
});

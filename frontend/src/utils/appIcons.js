/**
 * Official Frappe app marks and their friendly labels.
 *
 * The SVGs are the upstream marks, copied into src/assets/app-icons. India
 * Compliance has no mark upstream and reuses the ERPNext one; anything we do
 * not recognise falls back to the Frappe mark.
 */

import crmIcon from "@/assets/app-icons/crm.svg";
import erpnextIcon from "@/assets/app-icons/erpnext.svg";
import frappeIcon from "@/assets/app-icons/frappe.svg";
import helpdeskIcon from "@/assets/app-icons/helpdesk.svg";
import hrmsIcon from "@/assets/app-icons/hrms.svg";
import lmsIcon from "@/assets/app-icons/lms.svg";

export const APP_LABEL = {
	frappe: "Frappe",
	erpnext: "ERPNext",
	crm: "CRM",
	hrms: "HR",
	helpdesk: "Helpdesk",
	lms: "Learning",
	india_compliance: "India Compliance",
	telephony: "Telephony",
	payments: "Payments",
	vpn_management: "VPN Management",
	benchpress: "BenchPress",
};

const APP_ICON = {
	frappe: frappeIcon,
	erpnext: erpnextIcon,
	crm: crmIcon,
	hrms: hrmsIcon,
	helpdesk: helpdeskIcon,
	lms: lmsIcon,
	india_compliance: erpnextIcon,
};

/** The mark for an app name, falling back to the Frappe mark. */
export function iconFor(appName) {
	return APP_ICON[key(appName)] ?? frappeIcon;
}

/** The friendly label for an app name, falling back to the raw name. */
export function labelFor(appName) {
	return APP_LABEL[key(appName)] ?? appName ?? "";
}

function key(appName) {
	return typeof appName === "string" ? appName.trim().toLowerCase() : "";
}

/**
 * How credits read on screen.
 *
 * The backend keeps six decimals so a minute of a 1 credit/hour instance is not
 * rounded away, but nobody wants to read `39.983333`. Every credit figure in the
 * SPA is formatted here and only here, so the balance chip, the statement and
 * the lab rate cannot disagree about precision.
 */

const PLACES = 2;

// Grouped, because the sidebar meter renders the balance at heading size where `1480` reads as a
// year. Credits are a count rather than rupees, so they group in threes and not in lakhs.
const WHOLE = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const FRACTION = new Intl.NumberFormat("en-US", {
	minimumFractionDigits: PLACES,
	maximumFractionDigits: PLACES,
});

/** `39.983333` → `"39.98"`. A whole number keeps no decimals: `1480` → `"1,480"`. */
export function creditLabel(credits) {
	const value = Number(credits ?? 0);
	if (!Number.isFinite(value)) return "0";
	const rounded = Number(value.toFixed(PLACES));
	return Number.isInteger(rounded) ? WHOLE.format(rounded) : FRACTION.format(rounded);
}

/** A ledger amount, signed the way an account statement signs it. */
export function signedCreditLabel(credits) {
	const value = Number(credits ?? 0);
	if (value > 0) return `+${creditLabel(value)}`;
	if (value < 0) return `−${creditLabel(Math.abs(value))}`;
	return creditLabel(0);
}

/** What one hour of this instance size costs. */
export function rateLabel(creditsPerHour) {
	return `${creditLabel(creditsPerHour)} credits/hr`;
}

/**
 * What the balance is doing right now, or `""` when nothing is running.
 *
 * The burn rate is the sum over a user's running instances, so this is the one
 * number that explains a balance falling while nobody touches anything.
 */
export function burnLabel(burnRate) {
	const rate = Number(burnRate ?? 0);
	return rate > 0 ? `Burning ${rateLabel(rate)}` : "";
}

// Under this share of the allocation the meter stops being informational and starts being a
// warning, which is the same point the backend's low-balance notice fires at.
const LOW_SHARE = 0.2;

/**
 * The sidebar meter, as one object: how full the bar is, what tone it takes, what it says.
 *
 * The denominator is everything ever allocated and the numerator is what is left, so the bar
 * empties as credits are spent rather than filling — a fuel gauge, not a progress bar.
 */
export function creditMeter(balance, allocated, isSuspended = false) {
	const total = positive(allocated);
	const left = positive(balance);
	const share = total ? Math.min(left / total, 1) : 0;
	return {
		value: Math.round(share * 100),
		tone: meterTone(share, total, isSuspended),
		balanceLabel: creditLabel(left),
		allocatedLabel: creditLabel(total),
		label: total
			? `${creditLabel(left)} of ${creditLabel(total)} credits left`
			: "No credits allocated yet",
	};
}

function positive(credits) {
	const value = Number(credits ?? 0);
	return Number.isFinite(value) && value > 0 ? value : 0;
}

/** Green while there is room, amber once the tank is low, grey when there is nothing to gauge. */
function meterTone(share, total, isSuspended) {
	if (!total) return "gray";
	if (isSuspended || share <= 0) return "red";
	return share < LOW_SHARE ? "orange" : "green";
}

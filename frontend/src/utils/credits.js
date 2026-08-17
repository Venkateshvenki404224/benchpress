/**
 * How credits read on screen.
 *
 * The backend keeps six decimals so a minute of a 1 credit/hour instance is not
 * rounded away, but nobody wants to read `39.983333`. Every credit figure in the
 * SPA is formatted here and only here, so the balance chip, the statement and
 * the lab rate cannot disagree about precision.
 */

const PLACES = 2;

/** `39.983333` → `"39.98"`. A whole number keeps no decimals: `40` → `"40"`. */
export function creditLabel(credits) {
	const value = Number(credits ?? 0);
	if (!Number.isFinite(value)) return "0";
	const rounded = Number(value.toFixed(PLACES));
	return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(PLACES);
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

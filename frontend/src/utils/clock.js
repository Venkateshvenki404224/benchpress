/**
 * One skew-corrected clock, and one timer, for every countdown on the page.
 *
 * A browser clock can be minutes wrong, and a countdown read from it either
 * ends a lease early on screen or keeps showing time that is already gone.
 * `recordSkew` anchors against the server, charging only *half* the round trip:
 * `serverNow - Date.now()` alone books the whole response leg as skew and
 * over-reports the time remaining.
 *
 * Subscribers get a recomputed `serverNow()` on every tick, never a decrement.
 * Chrome throttles a hidden tab to one wakeup a minute and a suspended tab
 * fires none at all, so a counter wakes an hour stale while a recomputation is
 * simply right on the first tick back — and a tick that arrives far later than
 * it was scheduled asks for a fresh anchor.
 */

// A tick this far from its schedule means the tab slept or the clock stepped.
export const JUMP_TOLERANCE_MS = 5000;

let skewMs = 0;
let timer = null;
let expectedAt = 0;
const subscribers = new Set();
const resyncHandlers = new Set();

/**
 * Anchor the clock against a server timestamp.
 *
 * @param {number} t0 `Date.now()` immediately before the request went out.
 * @param {number} serverNowMs The server's own clock, in epoch milliseconds.
 * @param {number} t1 `Date.now()` when the response arrived.
 * @returns {number} The new skew.
 */
export function recordSkew(t0, serverNowMs, t1 = Date.now()) {
	skewMs = serverNowMs + (t1 - t0) / 2 - t1;
	return skewMs;
}

export function skew() {
	return skewMs;
}

export function serverNow() {
	return Date.now() + skewMs;
}

/** Register a handler asking for a fresh anchor. Returns an unsubscribe. */
export function onResync(handler) {
	resyncHandlers.add(handler);
	return () => resyncHandlers.delete(handler);
}

/**
 * Tick a subscriber with the corrected time. Returns an unsubscribe.
 *
 * The last unsubscribe clears the timer — a countdown left running behind a
 * closed page is the leak this API exists to make impossible.
 */
export function subscribe(handler, periodMs) {
	const entry = { handler, period: periodMs };
	subscribers.add(entry);
	schedule();
	return () => {
		subscribers.delete(entry);
		if (!subscribers.size) stop();
	};
}

/** Drop every subscriber, handler and timer. The test seam. */
export function resetClock() {
	skewMs = 0;
	subscribers.clear();
	resyncHandlers.clear();
	stop();
}

function schedule() {
	stop();
	if (!subscribers.size) return;
	const period = Math.min(...[...subscribers].map((entry) => entry.period));
	// Aligned to the *corrected* boundary. On the browser's own, a tick lands a few
	// milliseconds before the server's second and `leaseFor` rounds that up to a whole one.
	const delay = period - (serverNow() % period);
	expectedAt = Date.now() + delay;
	timer = setTimeout(fire, delay);
}

function fire() {
	if (Math.abs(Date.now() - expectedAt) > JUMP_TOLERANCE_MS) {
		for (const handler of resyncHandlers) handler();
	}
	const now = serverNow();
	for (const entry of subscribers) entry.handler(now);
	schedule();
}

function stop() {
	if (timer) clearTimeout(timer);
	timer = null;
}

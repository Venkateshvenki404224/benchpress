/**
 * How a lab's resource limits read on screen.
 *
 * `memory_limit` is stored the way Docker takes it ("512m", "2g"); nothing but
 * the display layer should ever reformat it, so the conversion lives here and
 * only here.
 */

const MEMORY_UNITS = { k: "KB", m: "MB", g: "GB", t: "TB" };

/** "512m" → "512 MB". An unrecognised value is shown verbatim. */
export function memoryLabel(memoryLimit) {
	const match = /^(\d+(?:\.\d+)?)\s*([kmgt])b?$/i.exec(String(memoryLimit ?? "").trim());
	if (!match) return memoryLimit || "";
	return `${match[1]} ${MEMORY_UNITS[match[2].toLowerCase()]}`;
}

/** Cores as the design labels them. */
export function cpuLabel(cpuCores) {
	return `${cpuCores || 1} vCPU`;
}

/** The build-and-deploy estimate a template card carries. */
export function etaLabel(etaMinutes) {
	return etaMinutes ? `~${etaMinutes} min to deploy` : "";
}

/**
 * What a bench is called on screen.
 *
 * `Bench Instance.bench_name` is `md5(user + lab)` — a stable key, but nothing
 * a person can read. Every surface shows the lab it belongs to instead.
 */
export function benchLabel(labId) {
	return labId ? `bench-${labId}` : "";
}

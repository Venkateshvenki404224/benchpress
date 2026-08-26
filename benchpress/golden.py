# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

"""A lab's finished site, baked into the lab's own image as a database dump.

A spawn creates 281 tables through the ORM for a CRM lab and 1055 for a seven-app one, every
time, for every tenant — 92% and 97% of the deploy. With a golden in the image, `setup-site.sh`
restores that database instead of installing it.

The dump ships **inside** the image so it can never drift from the code that produced it, and
the layer carrying it is appended over the existing tag: lab images are 5.5-19.7 GB and a
rebuild does not fit on this host.
"""

import hashlib
import io
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import docker
import frappe
from frappe import _

from benchpress import deploy_manager, docker_manager, image_cache, placement
from benchpress.image_cache import clear_cached_tags
from benchpress.mariadb_manager import drop_site_database, ensure_infrastructure

GOLDEN_DIR = "/opt/benchpress/golden"
DUMP_PATH = f"{GOLDEN_DIR}/site.sql.gz"
MANIFEST_PATH = f"{GOLDEN_DIR}/manifest.json"

# The three names this feature owns, and the only ones it ever drops or removes. A tenant's
# database is `_<sha1>` from `mariadb_manager.get_database_name` and stays unreachable from here.
GOLDEN_SITE_PREFIX = "bpgolden-"
GOLDEN_CONTAINER_PREFIX = "bpgolden-"
GOLDEN_DB_PREFIX = "_bpgolden"

BENCH_DIR = "/home/frappe/frappe-bench"
SETUP_SITE_PATH = "/opt/benchpress/scripts/setup-site.sh"

# The dump exec reports itself on one marked line, because a MariaDB client warning on stderr
# lands in the same stream as the output.
META_MARKER = "GOLDEN_META"

# The restore is DDL-bound: a schema-only dump of the same site restores in the same time as
# the full one, because the cost is 281 `CREATE TABLE`s. These three drop the statements that
# are pure overhead against the empty database `bench new-site` has just created.
LEAN_DUMP_FLAGS = "--skip-add-drop-table --skip-add-locks --skip-disable-keys"


def build_golden(lab_doc, log_fn=None) -> dict:
	"""Create this lab's site once and bake its database dump into the lab's image."""
	if not lab_doc.image_tag:
		frappe.throw(_("Lab '{0}' has no image to append a golden to.").format(lab_doc.title))

	db_server = frappe.get_doc("Database Server", ensure_infrastructure())
	site = f"{GOLDEN_SITE_PREFIX}{lab_doc.lab_id}"
	database = golden_database(site)
	container = _start_scratch_container(lab_doc)
	_log(log_fn, f"Scratch container {container.name} from {lab_doc.image_tag}")
	try:
		_create_site(container.id, db_server, site, database, lab_doc, log_fn)
		manifest = _dump_site(container.id, db_server, site, lab_doc, log_fn)
		_append_layer(container.id, lab_doc.image_tag, manifest, log_fn)
		return manifest
	finally:
		# Both outlive a failed run, and a leaked database sits in the server every tenant shares.
		drop_site_database(db_server.name, site, database)
		container.remove(force=True)


def golden_database(site: str) -> str:
	"""The scratch database for a golden site — the one name shape this feature may drop."""
	return GOLDEN_DB_PREFIX + hashlib.sha1(site.encode()).hexdigest()[:16]


def build_golden_job(lab_name: str, user: str | None = None) -> None:
	"""Run the golden build into its own `Build Log`, the way an image build streams."""
	lab = frappe.get_doc("Lab", lab_name)
	append_log, build_log_name = deploy_manager._open_build_log(lab, user or lab.owner)
	try:
		manifest = build_golden(lab, log_fn=append_log)
	except Exception as e:
		append_log(f"=== Build failed: {e!s} ===", "error")
		frappe.db.set_value("Build Log", build_log_name, "log_type", "error")
		frappe.db.commit()  # nosemgrep -- the run's outcome must survive its failure
		frappe.log_error(title=f"Golden build failed: {lab_name}", message=frappe.get_traceback())
		raise

	append_log(json.dumps(manifest))
	append_log(f"=== Build complete: golden in {lab.image_tag} ===", "success")
	frappe.db.set_value("Build Log", build_log_name, "log_type", "success")
	frappe.db.commit()  # nosemgrep -- the log records a finished run


def _start_scratch_container(lab_doc):
	"""Run the lab's existing image with no entrypoint, on the network a bench would get.

	Docker's embedded DNS answers `benchpress-mariadb` only across a shared network, and a
	container on the wrong one fails with a name-resolution error that names neither.
	"""
	client = docker_manager.get_client()
	name = f"{GOLDEN_CONTAINER_PREFIX}{lab_doc.lab_id}"
	_remove_stale(client, name)
	network = docker_manager.ensure_bench_network_for(placement.pick_network(), client)
	return client.containers.run(
		lab_doc.image_tag,
		command=["sleep", "infinity"],
		name=name,
		network=network,
		detach=True,
		mem_limit=lab_doc.memory_limit or "512m",
	)


def _remove_stale(client, name: str) -> None:
	try:
		client.containers.get(name).remove(force=True)
	except docker.errors.NotFound:
		pass


def _create_site(container_id: str, db_server, site: str, database: str, lab_doc, log_fn) -> None:
	"""Create the golden site with the same script a deploy runs, and never from a golden.

	`use_golden=False` because a second run against an image that already carries one would
	otherwise restore the last dump and bake a copy of a copy.
	"""
	config = {
		**db_server.get_connection_config(),
		"redis_cache": "redis://benchpress-redis:6379/0",
		"redis_queue": "redis://benchpress-redis:6379/1",
		"redis_socketio": "redis://benchpress-redis:6379/2",
		"socketio_port": 9000,
		"webserver_port": deploy_manager.SITE_HTTP_PORT,
		"default_site": site,
		"developer_mode": 1,
	}
	docker_manager.write_file_to_container(
		container_id, json.dumps(config, indent=2), f"{BENCH_DIR}/sites/common_site_config.json"
	)
	apps_csv = ",".join(a.app_name for a in lab_doc.apps if a.app_name.lower() != "frappe")
	exit_code, output = deploy_manager.create_site_in_container(
		container_id,
		db_server,
		site,
		frappe.generate_hash(length=16),
		apps_csv,
		database=database,
		use_golden=False,
	)
	if exit_code != 0:
		raise Exception(f"Golden site setup failed (exit {exit_code}): {output}")
	_log(log_fn, f"Golden site {site} created with {apps_csv or 'frappe'}")


def _dump_site(container_id: str, db_server, site: str, lab_doc, log_fn) -> dict:
	"""Dump the golden site's database inside the container; return the manifest describing it."""
	# Emptied, not reused: the image may already carry a golden, and its root-owned dump would
	# both refuse the write and travel into the new layer beside this run's own.
	exit_code, output = docker_manager.exec_in_container(
		container_id,
		f"rm -rf {GOLDEN_DIR} && mkdir -p {GOLDEN_DIR} && chown frappe:frappe {GOLDEN_DIR}",
		user="root",
	)
	if exit_code != 0:
		raise Exception(f"Could not create {GOLDEN_DIR} (exit {exit_code}): {output}")

	exit_code, output = docker_manager.exec_in_container(
		container_id, _dump_command(db_server, site), user="frappe", workdir=BENCH_DIR
	)
	if exit_code != 0:
		raise Exception(f"Golden dump failed (exit {exit_code}): {output}")

	manifest = _manifest(lab_doc, _read_meta(output))
	_log(log_fn, f"Dumped {manifest['dump_bytes']} bytes from MariaDB {manifest['mariadb_version']}")
	return manifest


def _dump_command(db_server, site: str) -> str:
	"""Dump through gzip with the site's own credentials, read out of its site_config.json.

	`pipefail` because gzip succeeds on a truncated stream, and a dump that fails silently is
	the one failure this feature must never ship into an image.
	"""
	connection = db_server.get_connection_config()
	host, port = connection["db_host"], connection["db_port"]
	read_credentials = (
		"python3 -c 'import json; "
		f'c = json.load(open("sites/{site}/site_config.json")); '
		'print(c["db_name"], c.get("db_user") or c["db_name"], c["db_password"])\''
	)
	return "\n".join(
		[
			"set -euo pipefail",
			f'credentials="$({read_credentials})"',
			'read -r db user password <<< "$credentials"',
			'export MYSQL_PWD="$password"',
			f'mariadb-dump -h {host} -P {port} -u "$user" --single-transaction --quick'
			f" --default-character-set=utf8mb4 {LEAN_DUMP_FLAGS}"
			f' "$db" | gzip -c > {DUMP_PATH}',
			f"version=$(mariadb -h {host} -P {port} -u \"$user\" -N -B -e 'SELECT VERSION()')",
			f'echo "{META_MARKER} $(stat -c %s {DUMP_PATH})'
			f' $(sha256sum {DUMP_PATH} | cut -d" " -f1) $version"',
		]
	)


def _read_meta(output: str) -> tuple[int, str, str]:
	"""`(bytes, sha256, mariadb_version)` off the dump exec's one marked line."""
	for line in reversed(output.splitlines()):
		if line.startswith(META_MARKER):
			_marker, size, digest, version = line.split()
			return int(size), digest, version
	raise Exception(f"Golden dump reported no {META_MARKER} line: {output}")


def _manifest(lab_doc, meta: tuple[int, str, str]) -> dict:
	"""What the dump is, and what it was taken from.

	`apps` and `frappe_version` come from `image_cache.build_spec`, so the manifest and the
	image tag describe the same recipe. `mariadb_version` is the one fact whose validity lives
	outside the image: the dump is restored into a different server than it came from.
	"""
	dump_bytes, dump_sha256, mariadb_version = meta
	spec = image_cache.build_spec(lab_doc)
	return {
		"lab_id": lab_doc.lab_id,
		"image_tag": lab_doc.image_tag,
		"frappe_version": spec["frappe_version"],
		"apps": spec["apps"],
		"mariadb_version": mariadb_version,
		"dump_bytes": dump_bytes,
		"dump_sha256": dump_sha256,
		"created_at": datetime.now(UTC).isoformat(timespec="seconds"),
	}


def _append_layer(container_id: str, image_tag: str, manifest: dict, log_fn=None) -> None:
	"""Rebuild `image_tag` from itself with the golden directory copied in.

	`FROM` the tag this build produces is intended: the previous image keeps its layers and
	becomes the parent of the new one, losing only the tag. Nothing below the appended layer
	is rebuilt.
	"""
	context = _build_context(container_id, image_tag, manifest)
	for chunk in docker_manager.get_client().api.build(
		fileobj=context, custom_context=True, tag=image_tag, rm=True, decode=True
	):
		if "error" in chunk:
			raise Exception(f"Golden layer build failed: {chunk['error'].strip()}")
		line = (chunk.get("stream") or "").strip()
		if line:
			_log(log_fn, line)
	clear_cached_tags()


def _build_context(container_id: str, image_tag: str, manifest: dict) -> io.BytesIO:
	"""The build context as an in-memory tar; nothing is written to the worker's filesystem."""
	stream, _stat = docker_manager.get_client().containers.get(container_id).get_archive(GOLDEN_DIR)
	context = io.BytesIO()
	with tarfile.open(fileobj=context, mode="w") as out:
		with tarfile.open(fileobj=io.BytesIO(b"".join(stream))) as golden:
			for member in golden:
				out.addfile(member, golden.extractfile(member) if member.isfile() else None)
		_add_file(out, "golden/manifest.json", json.dumps(manifest, indent=2).encode())
		_add_file(out, "Dockerfile", _dockerfile(image_tag).encode())
		_add_file(out, "setup-site.sh", _setup_site_source().encode(), mode=0o755)
	context.seek(0)
	return context


def _dockerfile(image_tag: str) -> str:
	"""The appended layer: the dump, and the branch of setup-site.sh that reads it.

	The script travels with the dump because every lab image on this host predates the restore
	branch, and this feature never rebuilds one.
	"""
	return f"FROM {image_tag}\nCOPY golden {GOLDEN_DIR}\nCOPY setup-site.sh {SETUP_SITE_PATH}\n"


def _setup_site_source() -> str:
	return (
		Path(frappe.get_app_path("benchpress")) / "lab-templates" / "scripts" / "setup-site.sh"
	).read_text()


def _add_file(tar: tarfile.TarFile, name: str, data: bytes, mode: int = 0o644) -> None:
	info = tarfile.TarInfo(name)
	info.size = len(data)
	info.mode = mode
	tar.addfile(info, io.BytesIO(data))


def _log(log_fn, line: str) -> None:
	if log_fn:
		log_fn(line)

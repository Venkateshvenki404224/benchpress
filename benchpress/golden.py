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
import time
from datetime import UTC, datetime
from pathlib import Path

import docker
import frappe
from frappe import _

from benchpress import deploy_manager, docker_manager, image_cache, placement
from benchpress.image_cache import clear_cached_tags
from benchpress.mariadb_manager import (
	create_mariadb_user,
	drop_mariadb_user,
	drop_site_database,
	ensure_infrastructure,
	execute_sql,
)

GOLDEN_DIR = "/opt/benchpress/golden"
DUMP_PATH = f"{GOLDEN_DIR}/site.sql.gz"
MANIFEST_PATH = f"{GOLDEN_DIR}/manifest.json"

# Whether a tag carries a golden is read from these, never from `Lab.golden_manifest`: the row is
# a claim about an image, and the image is the artefact a deploy actually runs.
GOLDEN_LABEL = "benchpress.golden"
GOLDEN_MARIADB_LABEL = "benchpress.golden.mariadb"

# The three names this feature owns, and the only ones it ever drops or removes. A tenant's
# database is `_<sha1>` from `mariadb_manager.get_database_name` and stays unreachable from here.
GOLDEN_SITE_PREFIX = "bpgolden-"
GOLDEN_CONTAINER_PREFIX = "bpgolden-"
GOLDEN_DB_PREFIX = "_bpgolden"
VERIFY_DB_PREFIX = "_bpgolden_verify_"

BENCH_DIR = "/home/frappe/frappe-bench"
SETUP_SITE_PATH = "/opt/benchpress/scripts/setup-site.sh"

# The dump and the verification restore each report themselves on one marked line, because a
# MariaDB client warning on stderr lands in the same stream as the output.
META_MARKER = "GOLDEN_META"
VERIFY_MARKER = "GOLDEN_VERIFY"

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
		manifest.update(_verify_dump(container.id, db_server, lab_doc, log_fn))
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
	# The row is only ever a record, so it is written the same way whether the golden came from
	# a build or from this action — otherwise the admin screen reads empty for a lab that has one.
	frappe.db.set_value("Lab", lab_name, "golden_manifest", json.dumps(manifest, indent=2))
	frappe.db.commit()  # nosemgrep -- the log records a finished run


def add_golden(lab_doc, log_fn=None) -> dict | None:
	"""Build this lab's golden as part of something larger, and never fail that something.

	Returns the manifest, or None when the setting is off or the golden step failed. A lab whose
	image built and whose golden did not is a working lab with a slow deploy; raising here would
	take a working image away from every tenant of that lab because an optimisation failed.
	"""
	if not golden_images_enabled():
		_log(log_fn, "Golden images are turned off in BenchPress Settings — skipping the golden step")
		return None

	_log(log_fn, f"=== Baking the golden site into {lab_doc.image_tag} ===")
	try:
		manifest = build_golden(lab_doc, log_fn=log_fn)
	except Exception as e:
		_log(log_fn, f"Golden step failed: {e!s} — the image is usable and deploys will be slow")
		frappe.log_error(title=f"Golden step failed: {lab_doc.lab_id}", message=frappe.get_traceback())
		return None

	_log(log_fn, json.dumps(manifest))
	return manifest


def golden_images_enabled() -> bool:
	"""Whether a build also bakes a golden — `BenchPress Settings.enable_golden_images`."""
	return bool(frappe.get_cached_value("BenchPress Settings", "BenchPress Settings", "enable_golden_images"))


def restore_enabled() -> bool:
	"""Whether a deploy restores from a golden — `BenchPress Settings.restore_from_golden`."""
	return bool(frappe.get_cached_value("BenchPress Settings", "BenchPress Settings", "restore_from_golden"))


def image_has_golden(tag: str) -> bool:
	"""Whether this image carries a golden dump, asked of the image and not of the `Lab` row."""
	return _image_labels(tag).get(GOLDEN_LABEL) == "1"


def golden_mariadb_version(tag: str) -> str:
	"""The MariaDB server this image's dump was taken from; empty when it carries no golden."""
	return _image_labels(tag).get(GOLDEN_MARIADB_LABEL, "")


def _image_labels(tag: str) -> dict:
	"""One image's labels, empty on any Docker error — a missing image included.

	Every caller's safe direction is the cold path, and no deploy may fail because an
	optimisation could not be checked for.
	"""
	try:
		return docker_manager.get_client().images.get(tag).labels or {}
	except Exception:
		return {}


def golden_tags() -> set[str]:
	"""Every lab tag on this host carrying a golden, in the one round trip `cached_tags` makes."""
	images = docker_manager.get_client().images.list(name=f"{image_cache.CACHE_REPOSITORY}/*")
	return {
		tag for image in images if (image.labels or {}).get(GOLDEN_LABEL) == "1" for tag in (image.tags or [])
	}


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


def _verify_dump(container_id: str, db_server, lab_doc, log_fn) -> dict:
	"""Restore the dump into a scratch database and report what came back.

	Raises when the restore brings back no tables, or fewer apps than the lab installs. The
	golden is then never appended and the image keeps the cold path, which works.
	"""
	site = f"{GOLDEN_SITE_PREFIX}verify-{lab_doc.lab_id}"
	database = f"{VERIFY_DB_PREFIX}{lab_doc.lab_id}"
	_database, user, password = create_mariadb_user(db_server.name, site, database)
	try:
		exit_code, output = execute_sql(db_server.name, f"CREATE OR REPLACE DATABASE `{database}`;\n")
		if exit_code != 0:
			raise Exception(f"Could not create {database} (exit {exit_code}): {output}")
		started = time.monotonic()
		exit_code, output = docker_manager.exec_in_container(
			container_id,
			_restore_command(db_server, database),
			user="frappe",
			environment={"MYSQL_PWD": password, "GOLDEN_USER": user},
		)
		restore_seconds = round(time.monotonic() - started, 1)
		if exit_code != 0:
			raise Exception(f"Golden dump would not restore (exit {exit_code}): {output}")
		exit_code, output = docker_manager.exec_in_container(
			container_id,
			_restored_command(db_server, database),
			user="frappe",
			environment={"MYSQL_PWD": password, "GOLDEN_USER": user},
		)
		if exit_code != 0:
			raise Exception(f"Could not read the restored database (exit {exit_code}): {output}")
		tables, installed_apps = _read_verified(output)
	finally:
		# The scratch database and its limited user both sit in the server every tenant shares.
		drop_site_database(db_server.name, site, database)
		drop_mariadb_user(db_server.name, site, database)

	_assert_restored(lab_doc, tables, installed_apps)
	_log(log_fn, f"Restored {tables} tables and {', '.join(installed_apps)} in {restore_seconds}s")
	return {"tables": tables, "installed_apps": sorted(installed_apps), "restore_seconds": restore_seconds}


def _restore_command(db_server, database: str) -> str:
	"""Pipe the dump back in through gzip, the way `bench new-site --source-sql` will."""
	connection = db_server.get_connection_config()
	return "\n".join(
		[
			"set -euo pipefail",
			f"gzip -cd {DUMP_PATH} | mariadb -h {connection['db_host']} -P {connection['db_port']}"
			f' -u "$GOLDEN_USER" --default-character-set=utf8mb4 {database}',
		]
	)


def _restored_command(db_server, database: str) -> str:
	"""Count what the restore brought back, on one marked line."""
	connection = db_server.get_connection_config()
	client = f'mariadb -h {connection["db_host"]} -P {connection["db_port"]} -u "$GOLDEN_USER" -N -B'
	tables = (
		f'tables=$({client} -e "SELECT COUNT(*) FROM information_schema.tables'
		f" WHERE table_schema='{database}'\")"
	)
	# `app_name`, not `name`: a row in this child table is named by a hash.
	apps = f"apps=$({client} {database} -e 'SELECT app_name FROM `tabInstalled Application`' | tr '\\n' ' ')"
	return "\n".join(["set -euo pipefail", tables, apps, f'echo "{VERIFY_MARKER} $tables $apps"'])


def _read_verified(output: str) -> tuple[int, list[str]]:
	"""`(tables, apps)` off the read-back exec's one marked line."""
	for line in reversed(output.splitlines()):
		if line.startswith(VERIFY_MARKER):
			_marker, tables, *apps = line.split()
			return int(tables), apps
	raise Exception(f"The restored database reported no {VERIFY_MARKER} line: {output}")


def _assert_restored(lab_doc, tables: int, installed_apps: list[str]) -> None:
	"""Refuse a dump that came back empty or short of the lab's own apps.

	`bench new-site --source-sql` reports success on an empty restore, so the exit code proves
	nothing and this is the only place the dump is ever asked what it contains.
	"""
	if not tables:
		raise Exception("Golden dump restored no tables")
	expected = {row.app_name.strip().lower() for row in lab_doc.apps} | {"frappe"}
	missing = expected - {app.lower() for app in installed_apps}
	if missing:
		raise Exception(f"Golden dump restored without {', '.join(sorted(missing))}")


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
	dump = (
		f'mariadb-dump -h {host} -P {port} -u "$user" --single-transaction --quick'
		f' --default-character-set=utf8mb4 {LEAN_DUMP_FLAGS} "$db" | gzip -c > {DUMP_PATH}'
	)
	version = f"version=$(mariadb -h {host} -P {port} -u \"$user\" -N -B -e 'SELECT VERSION()')"
	meta = f'echo "{META_MARKER} $(stat -c %s {DUMP_PATH}) $(sha256sum {DUMP_PATH} | cut -d" " -f1) $version"'
	return "\n".join(
		[
			"set -euo pipefail",
			f'credentials="$({read_credentials})"',
			'read -r db user password <<< "$credentials"',
			'export MYSQL_PWD="$password"',
			dump,
			version,
			meta,
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
		_add_file(out, "Dockerfile", _dockerfile(image_tag, manifest).encode())
		_add_file(out, "setup-site.sh", _setup_site_source().encode(), mode=0o755)
	context.seek(0)
	return context


def _dockerfile(image_tag: str, manifest: dict) -> str:
	"""The appended layer: the dump, the branch of setup-site.sh that reads it, and the labels.

	The script travels with the dump because every lab image on this host predates the restore
	branch, and this feature never rebuilds one. The labels are how a deploy asks the image
	itself whether it has a golden.
	"""
	return (
		f"FROM {image_tag}\n"
		f"COPY golden {GOLDEN_DIR}\n"
		f"COPY setup-site.sh {SETUP_SITE_PATH}\n"
		f'LABEL {GOLDEN_LABEL}="1" {GOLDEN_MARIADB_LABEL}="{manifest["mariadb_version"]}"\n'
	)


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

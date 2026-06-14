# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

import contextlib
import io
from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from benchpress import install


class TestAfterInstall(IntegrationTestCase):
	def _after_install(self, developer_mode):
		buf = io.StringIO()
		with (
			patch("subprocess.run") as subprocess_run,
			patch.object(install, "create_test_users") as create_test_users,
			patch.object(install.frappe, "conf", {"developer_mode": developer_mode}),
			contextlib.redirect_stdout(buf),
		):
			install.after_install()
		return buf.getvalue(), subprocess_run, create_test_users

	def test_does_not_shell_out_to_setup_sh(self):
		_, subprocess_run, _ = self._after_install(developer_mode=False)
		subprocess_run.assert_not_called()

	def test_prints_explicit_instructions(self):
		output, _, _ = self._after_install(developer_mode=False)
		self.assertIn("No changes were made to the host", output)
		self.assertIn("bench benchpress doctor", output)
		self.assertIn("bench benchpress setup", output)
		self.assertNotIn("setup.sh", output)

	def test_developer_mode_creates_test_users(self):
		_, _, create_test_users = self._after_install(developer_mode=True)
		create_test_users.assert_called_once()

	def test_non_developer_mode_skips_test_users(self):
		_, _, create_test_users = self._after_install(developer_mode=False)
		create_test_users.assert_not_called()

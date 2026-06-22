# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase


def _completed(stdout):
	"""Stand in for a subprocess.CompletedProcess with the given stdout."""
	result = MagicMock()
	result.stdout = stdout
	return result


class TestWgManager(IntegrationTestCase):
	@patch("benchpress.wg_manager.subprocess.run")
	@patch("benchpress.wg_manager._wg_available", return_value=False)
	def test_generate_keypair_throws_when_wg_unavailable(self, _mock_available, mock_run):
		from benchpress.wg_manager import generate_keypair

		with self.assertRaises(frappe.ValidationError):
			generate_keypair()

		# No keypair may be derived (and therefore stored) without the wg binary.
		mock_run.assert_not_called()

	@patch("benchpress.wg_manager._wg_available", return_value=True)
	@patch("benchpress.wg_manager.subprocess.run")
	def test_generate_keypair_returns_distinct_keys_from_wg(self, mock_run, _mock_available):
		from benchpress.wg_manager import generate_keypair

		mock_run.side_effect = [_completed("PRIVATEKEY123\n"), _completed("PUBLICKEY456\n")]

		keys = generate_keypair()

		self.assertEqual(keys["private_key"], "PRIVATEKEY123")
		self.assertEqual(keys["public_key"], "PUBLICKEY456")
		# Guards the original bug where the public key was the private key blob.
		self.assertNotEqual(keys["private_key"], keys["public_key"])

	@patch("benchpress.wg_manager._wg_available", return_value=True)
	@patch("benchpress.wg_manager.subprocess.run")
	def test_generate_keypair_derives_public_from_private(self, mock_run, _mock_available):
		from benchpress.wg_manager import generate_keypair

		mock_run.side_effect = [_completed("PRIV==\n"), _completed("PUB==\n")]

		generate_keypair()

		# pubkey must be derived from the freshly generated private key on stdin.
		pubkey_call = mock_run.call_args_list[1]
		self.assertEqual(pubkey_call.args[0], ["wg", "pubkey"])
		self.assertEqual(pubkey_call.kwargs["input"], "PRIV==")

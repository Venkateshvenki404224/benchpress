# Copyright (c) 2026, Venkatesh and contributors
# For license information, please see license.txt

import frappe


class BenchPressPasswordResetMixin:
	def password_reset_mail(self, link):
		# Not the framework's own mail: `send_login_mail` forces `with_container`, which draws a
		# white masthead from `app_logo_url` and signs the body with whoever was logged in. An
		# operator who named a template in System Settings still gets theirs.
		if frappe.db.get_system_setting("reset_password_template"):
			return super().password_reset_mail(link)

		# Imported here: this mixin is loaded by `get_controller`, which runs before a request has
		# a reason to pull the mail module's own import chain in.
		from benchpress import emails

		emails.send_password_reset(self, link)

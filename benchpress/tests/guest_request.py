# Copyright (c) 2026, Venkatesh and Contributors
# See license.txt

"""The request state the public forms' rate limiter needs: it is a no-op outside a request."""

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

ADDRESS = "127.0.0.1"


class as_request:
	def __init__(self, address: str = ADDRESS, path: str = "/"):
		self.address = address
		self.path = path

	def __enter__(self):
		frappe.local.request = Request(EnvironBuilder(path=self.path, method="POST").get_environ())
		frappe.local.request_ip = self.address
		return self

	def __exit__(self, *exception):
		frappe.local.request = None
		return False

# Copyright (c) 2026, Asyntai and contributors
# For license information, please see license.txt

import frappe

from asyntai import client


def before_uninstall():
	"""Take the webhook off the Asyntai account before the app goes away.

	Without this, Asyntai keeps posting leads at a URL that no longer answers.
	"""
	try:
		settings = frappe.get_single("Asyntai Settings")
	except Exception:
		return

	if not settings.get("webhook_id") or not settings.get("api_key"):
		return

	try:
		client.delete_webhook(settings.webhook_id, settings=settings)
	except Exception:
		frappe.log_error(
			title="Asyntai: could not remove the webhook on uninstall",
			message=frappe.get_traceback(),
		)

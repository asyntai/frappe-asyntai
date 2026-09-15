# Copyright (c) 2026, Asyntai and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AsyntaiSettings(Document):
	def validate(self):
		if self.widget_id:
			self.widget_id = self.widget_id.strip()

		if self.website_id:
			self.website_id = self.website_id.strip()

		if self.enabled and not self.widget_id:
			frappe.throw(_("Add the Widget ID to show the chat widget."))

		if self.sync_enabled and not self.api_key:
			frappe.throw(_("Add the API key to sync content to Asyntai."))

	def on_update(self):
		# Website pages are cached as finished HTML, so switching the widget on
		# would otherwise show up only on pages nobody had opened yet.
		from frappe.website.utils import clear_website_cache

		clear_website_cache()
		frappe.clear_cache()

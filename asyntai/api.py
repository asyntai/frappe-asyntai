# Copyright (c) 2026, Asyntai and contributors
# For license information, please see license.txt

"""Endpoints the desk and Asyntai call."""

import datetime
import hashlib
import hmac
import json
import zoneinfo

import frappe
from frappe import _

from asyntai import client, sync

LEAD_EVENT = "lead.captured"
WEBHOOK_PATH = "/api/method/asyntai.api.lead_webhook"


def _settings():
	return frappe.get_single("Asyntai Settings")


def _check_manager():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only a System Manager can change the Asyntai settings."), frappe.PermissionError)


# --- desk endpoints ---------------------------------------------------------


@frappe.whitelist()
def test_connection():
	"""Ask Asyntai for the websites on this account, so the key is proven."""
	_check_manager()
	websites = client.list_websites(settings=_settings())
	return {"success": True, "websites": websites}


@frappe.whitelist()
def sync_all():
	"""Queue every published Web Page and Blog Post."""
	_check_manager()
	queued = sync.sync_all()
	return {"success": True, "queued": queued}


@frappe.whitelist()
def connect_leads():
	"""Register this site with Asyntai, so chat leads arrive here."""
	_check_manager()
	settings = _settings()

	url = frappe.utils.get_url().rstrip("/") + WEBHOOK_PATH

	if not url.startswith("https://"):
		frappe.msgprint(
			_("This site answers on {0}. Asyntai can only reach a public address.").format(url),
			indicator="orange",
			title=_("Check the address"),
		)

	webhook = client.create_webhook(
		url,
		[LEAD_EVENT],
		website_id=settings.website_id,
		settings=settings,
	)

	settings.webhook_id = webhook.get("id")
	settings.webhook_secret = webhook.get("secret")
	settings.lead_capture_enabled = 1
	settings.flags.ignore_permissions = True
	settings.save()
	frappe.db.commit()

	return {"success": True, "url": url}


@frappe.whitelist()
def disconnect_leads():
	"""Stop the lead webhook and forget the secret."""
	_check_manager()
	settings = _settings()

	if settings.webhook_id:
		try:
			client.delete_webhook(settings.webhook_id, settings=settings)
		except Exception:
			frappe.log_error(
				title="Asyntai: could not delete the webhook",
				message=frappe.get_traceback(),
			)

	settings.webhook_id = None
	settings.webhook_secret = None
	settings.lead_capture_enabled = 0
	settings.flags.ignore_permissions = True
	settings.save()
	frappe.db.commit()

	return {"success": True}


# --- webhook ----------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def lead_webhook():
	"""Asyntai posts here when a visitor leaves contact details in the chat."""
	frappe.set_user("Administrator")

	settings = frappe.get_single("Asyntai Settings")
	if not settings.lead_capture_enabled:
		frappe.local.response["http_status_code"] = 403
		return {"success": False, "error": "Lead capture is off"}

	body = frappe.request.get_data() or b""
	secret = settings.get_password("webhook_secret", raise_exception=False)

	if not _signature_ok(body, secret):
		frappe.local.response["http_status_code"] = 401
		return {"success": False, "error": "Bad signature"}

	try:
		data = json.loads(body.decode("utf-8"))
	except (ValueError, UnicodeDecodeError):
		frappe.local.response["http_status_code"] = 400
		return {"success": False, "error": "Invalid JSON"}

	if data.get("event") != LEAD_EVENT:
		return {"success": True, "ignored": data.get("event")}

	payload = data.get("payload") or {}

	try:
		name = create_lead(payload, settings)
	except Exception:
		# Write the reason down where the customer can read it, instead of
		# letting the caller see a bare stack trace.
		frappe.db.rollback()
		frappe.log_error(
			title="Asyntai: could not create the record for a chat lead",
			message=frappe.get_traceback(),
		)
		frappe.db.commit()
		frappe.local.response["http_status_code"] = 500
		return {"success": False, "error": "Could not create the record. See the Error Log."}

	return {"success": True, "doctype": settings.lead_doctype, "name": name}


def _signature_ok(body, secret):
	"""Compare the HMAC Asyntai sent with the one we compute."""
	if not secret:
		return False

	sent = frappe.get_request_header("X-Webhook-Signature") or ""
	expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
	return hmac.compare_digest(sent, expected)


def create_lead(payload, settings=None):
	"""Make the Lead or the Contact for one captured chat lead."""
	settings = settings or frappe.get_single("Asyntai Settings")

	email = (payload.get("email") or "").strip()
	phone = (payload.get("phone") or "").strip()
	if not email and not phone:
		return None

	target = settings.lead_doctype or "Contact"
	if not frappe.db.exists("DocType", target):
		target = "Contact"

	notes = _build_notes(payload)

	if target == "Lead":
		existing = None
		if email:
			existing = frappe.db.get_value("Lead", {"email_id": email}, "name")
		if existing:
			_add_comment("Lead", existing, notes)
			return existing

		lead = frappe.new_doc("Lead")
		# The name the chatbot has is the email address. Use the part before
		# the "@", so the Lead reads as a person in the list. Never put the
		# website domain in company_name: the site is yours, not the visitor's
		# employer, and a wrong organisation is worse than an empty one.
		lead.first_name = email.split("@")[0] if email else phone
		lead.lead_name = lead.first_name
		if email:
			lead.email_id = email
		if phone:
			lead.mobile_no = phone
		# Lead Source is master data, and a name that is not there stops the
		# insert. Only "Website" describes a chat lead, so set that when the
		# site has it and leave the field empty when it does not. A wrong
		# source sends the sales team down the wrong path.
		if frappe.db.exists("Lead Source", "Website"):
			lead.source = "Website"
		lead.flags.ignore_mandatory = True
		lead.flags.ignore_links = True
		lead.insert(ignore_permissions=True)
		_add_comment("Lead", lead.name, notes)
		frappe.db.commit()
		return lead.name

	existing = None
	if email:
		existing = frappe.db.get_value(
			"Contact Email", {"email_id": email}, "parent"
		)
	if existing:
		_add_comment("Contact", existing, notes)
		return existing

	contact = frappe.new_doc("Contact")
	contact.first_name = email.split("@")[0] if email else phone
	if email:
		contact.append("email_ids", {"email_id": email, "is_primary": 1})
	if phone:
		contact.append("phone_nos", {"phone": phone, "is_primary_mobile_no": 1})
	contact.flags.ignore_mandatory = True
	contact.flags.ignore_links = True
	contact.insert(ignore_permissions=True)
	_add_comment("Contact", contact.name, notes)
	frappe.db.commit()
	return contact.name


def _build_notes(payload):
	lines = ["Captured by the Asyntai chatbot."]
	for label, key in (
		("Page", "page_url"),
		("Country", "country"),
		("Website", "website_domain"),
		("Chat session", "session_id"),
		("Started", "started_at"),
	):
		value = payload.get(key)
		if not value:
			continue
		if key == "started_at":
			value = _readable_time(value) or value
		lines.append(f"{label}: {value}")
	return "<br>".join(frappe.utils.escape_html(line) for line in lines)


def _readable_time(value):
	"""Turn the API timestamp into the date format the site itself uses.

	The raw value carries microseconds and a UTC offset. That belongs in a log,
	not on a record a salesperson reads.
	"""
	try:
		text = str(value).replace("Z", "+00:00")
		moment = datetime.datetime.fromisoformat(text)
		if moment.tzinfo is not None:
			moment = moment.astimezone(
				zoneinfo.ZoneInfo(frappe.utils.get_system_timezone())
			).replace(tzinfo=None)
		return frappe.utils.format_datetime(moment, "medium")
	except Exception:
		return None


def _add_comment(doctype, name, notes):
	if not notes:
		return
	doc = frappe.get_doc(doctype, name)
	doc.add_comment("Comment", notes)

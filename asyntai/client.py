# Copyright (c) 2026, Asyntai and contributors
# For license information, please see license.txt

"""Thin client for the Asyntai public API.

Every call needs an API key from the Asyntai dashboard (Settings, then API).
The key is kept in the Asyntai Settings single doctype as a Password field, so
it is encrypted at rest by Frappe.
"""

import json

import frappe
import requests
from frappe import _

BASE_URL = "https://asyntai.com"
TIMEOUT = 30


class AsyntaiError(frappe.ValidationError):
	pass


def get_settings():
	return frappe.get_single("Asyntai Settings")


def get_api_key(settings=None):
	settings = settings or get_settings()
	key = settings.get_password("api_key", raise_exception=False)
	if not key:
		frappe.throw(_("Add your Asyntai API key in Asyntai Settings first."), AsyntaiError)
	return key


def base_url(settings=None):
	settings = settings or get_settings()
	return (settings.api_url or BASE_URL).rstrip("/")


def request(method, path, settings=None, payload=None, api_key=None):
	"""Call the Asyntai API and return the decoded body.

	Raises AsyntaiError with the message the API sent, so the desk shows the
	real reason instead of a stack trace.
	"""
	settings = settings or get_settings()
	api_key = api_key or get_api_key(settings)
	url = f"{base_url(settings)}{path}"

	try:
		response = requests.request(
			method,
			url,
			headers={
				"Authorization": f"Bearer {api_key}",
				"Content-Type": "application/json",
				"User-Agent": "Asyntai-Frappe/1.0",
			},
			data=json.dumps(payload) if payload is not None else None,
			timeout=TIMEOUT,
		)
	except requests.RequestException as exc:
		frappe.throw(_("Could not reach Asyntai: {0}").format(exc), AsyntaiError)

	if response.status_code == 401:
		frappe.throw(_("Asyntai rejected the API key. Copy it again from Settings, then API."), AsyntaiError)

	if response.status_code == 403:
		frappe.throw(
			_("The Asyntai API needs the Starter plan or higher. See https://asyntai.com/pricing/"),
			AsyntaiError,
		)

	try:
		body = response.json()
	except ValueError:
		body = {}

	if response.status_code >= 400 or body.get("success") is False:
		message = body.get("error") or _("Asyntai returned status {0}").format(response.status_code)
		frappe.throw(message, AsyntaiError)

	return body


def list_websites(settings=None, api_key=None):
	return request("GET", "/api/v1/websites/", settings=settings, api_key=api_key).get("websites", [])


def add_text(title, content, website_id=None, settings=None):
	payload = {"title": title, "content": content}
	if website_id:
		payload["website_id"] = website_id
	return request("POST", "/api/v1/knowledge/text/", settings=settings, payload=payload)


def delete_item(context_id, settings=None):
	return request("DELETE", f"/api/v1/knowledge/{context_id}/", settings=settings)


def create_webhook(url, events, website_id=None, settings=None):
	payload = {"url": url, "events": events}
	if website_id:
		payload["website_id"] = website_id
	return request("POST", "/api/v1/webhooks/", settings=settings, payload=payload).get("webhook", {})


def delete_webhook(webhook_id, settings=None):
	return request("DELETE", f"/api/v1/webhooks/{webhook_id}/", settings=settings)

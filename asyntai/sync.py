# Copyright (c) 2026, Asyntai and contributors
# For license information, please see license.txt

"""Keep the Asyntai knowledge base in step with the website content.

A Web Page or a Blog Post becomes one item in the Asyntai knowledge base. The
chatbot then answers from it, word for word, with a link back to the page.

Asyntai has no update call for a knowledge item, so a changed page is deleted
and sent again. The old content id lives in Asyntai Synced Page.
"""

import hashlib
import re

import frappe
from frappe.utils import now_datetime
from frappe.utils.html_utils import unescape_html

from asyntai import client

SUPPORTED = {
	"Web Page": "sync_web_pages",
	"Blog Post": "sync_blog_posts",
}

QUEUE_TIMEOUT = 300


def get_settings():
	return frappe.get_cached_doc("Asyntai Settings")


def is_enabled(doctype, settings=None):
	settings = settings or get_settings()
	if not settings.sync_enabled or not settings.api_key:
		return False
	flag = SUPPORTED.get(doctype)
	return bool(flag and settings.get(flag))


def html_to_text(html):
	"""Turn stored HTML into readable plain text.

	Block tags become newlines first. Stripping the tags on their own would run
	a heading straight into the paragraph below it, and the chatbot would then
	quote the two as one sentence.
	"""
	if not html:
		return ""

	text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
	text = re.sub(r"(?i)<br\s*/?>", "\n", text)
	text = re.sub(
		r"(?i)</(p|div|h1|h2|h3|h4|h5|h6|li|tr|section|article|blockquote|pre)\s*>",
		"\n",
		text,
	)
	text = re.sub(r"(?i)<li[^>]*>", "- ", text)
	text = re.sub(r"<[^>]+>", " ", text)
	text = unescape_html(text)
	text = re.sub(r"[ \t\r\f\v]+", " ", text)
	text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
	return text.strip()


def get_page_content(doc):
	"""Return (title, body text) for a document we sync."""
	from frappe.website.utils import get_html_content_based_on_type

	if doc.doctype == "Web Page":
		title = doc.get("title") or doc.name
		# A Web Page keeps its text in one of three fields, by content type.
		# Reading only main_section would miss a Markdown or an HTML page.
		body = html_to_text(
			get_html_content_based_on_type(doc, "main_section", doc.get("content_type"))
		)
	elif doc.doctype == "Blog Post":
		title = doc.get("title") or doc.name
		body = html_to_text(
			get_html_content_based_on_type(doc, "content", doc.get("content_type"))
		)
		blurb = (doc.get("blog_intro") or "").strip()
		if blurb and blurb not in body:
			body = f"{blurb}\n\n{body}"
	else:
		return None, None

	return title, body


def should_sync_doc(doc, settings=None):
	"""A page goes to Asyntai when it is published and has real text."""
	settings = settings or get_settings()
	if not is_enabled(doc.doctype, settings):
		return False

	if not doc.get("published"):
		return False

	_title, body = get_page_content(doc)
	return bool(body and len(body) >= 10)


def content_hash(title, body, route):
	digest = hashlib.sha256()
	digest.update((title or "").encode("utf-8"))
	digest.update(b"\x00")
	digest.update((route or "").encode("utf-8"))
	digest.update(b"\x00")
	digest.update((body or "").encode("utf-8"))
	return digest.hexdigest()


def get_record(doctype, name):
	rows = frappe.get_all(
		"Asyntai Synced Page",
		filters={"reference_doctype": doctype, "reference_name": name},
		fields=["name", "context_id", "content_hash"],
		limit=1,
	)
	return rows[0] if rows else None


# --- document hooks ---------------------------------------------------------


def on_document_update(doc, method=None):
	settings = get_settings()
	if not is_enabled(doc.doctype, settings):
		return

	frappe.enqueue(
		"asyntai.sync.sync_document",
		queue="long",
		timeout=QUEUE_TIMEOUT,
		enqueue_after_commit=True,
		# The timestamp is part of the id on purpose. With a fixed id, a second
		# save while the first job is still queued is dropped, and the page
		# keeps the text it had before that save.
		job_id=f"asyntai-sync::{doc.doctype}::{doc.name}::{doc.modified}",
		deduplicate=True,
		doctype=doc.doctype,
		name=doc.name,
	)


def on_document_trash(doc, method=None):
	record = get_record(doc.doctype, doc.name)
	if not record:
		return

	frappe.enqueue(
		"asyntai.sync.remove_document",
		queue="long",
		timeout=QUEUE_TIMEOUT,
		enqueue_after_commit=True,
		doctype=doc.doctype,
		name=doc.name,
	)


# --- background jobs --------------------------------------------------------


def sync_document(doctype, name):
	"""Send one page to Asyntai, or take it back out when it is unpublished."""
	settings = frappe.get_single("Asyntai Settings")
	if not is_enabled(doctype, settings):
		return

	if not frappe.db.exists(doctype, name):
		remove_document(doctype, name)
		return

	doc = frappe.get_doc(doctype, name)
	record = get_record(doctype, name)

	if not should_sync_doc(doc, settings):
		if record:
			remove_document(doctype, name)
		return

	title, body = get_page_content(doc)
	route = doc.get("route") or ""
	digest = content_hash(title, body, route)

	if record and record.get("content_hash") == digest:
		return

	if route:
		site_url = frappe.utils.get_url()
		body = f"{body}\n\nSource: {site_url}/{route.lstrip('/')}"

	# Asyntai has no update call, so the old item goes first.
	if record and record.get("context_id"):
		try:
			client.delete_item(record["context_id"], settings=settings)
		except Exception:
			frappe.log_error(
				title="Asyntai: could not delete the old knowledge item",
				message=frappe.get_traceback(),
			)

	result = client.add_text(title, body, website_id=settings.website_id, settings=settings)
	context_id = result.get("id")

	if record:
		synced = frappe.get_doc("Asyntai Synced Page", record["name"])
	else:
		synced = frappe.new_doc("Asyntai Synced Page")
		synced.reference_doctype = doctype
		synced.reference_name = name

	synced.context_id = context_id
	synced.content_hash = digest
	synced.title = title
	synced.synced_at = now_datetime()
	synced.flags.ignore_permissions = True
	synced.save(ignore_permissions=True)

	update_counters()
	frappe.db.commit()


def remove_document(doctype, name):
	"""Take one page back out of the Asyntai knowledge base."""
	record = get_record(doctype, name)
	if not record:
		return

	settings = frappe.get_single("Asyntai Settings")

	if record.get("context_id") and settings.api_key:
		try:
			client.delete_item(record["context_id"], settings=settings)
		except Exception:
			frappe.log_error(
				title="Asyntai: could not delete the knowledge item",
				message=frappe.get_traceback(),
			)

	frappe.delete_doc("Asyntai Synced Page", record["name"], ignore_permissions=True, force=True)
	update_counters()
	frappe.db.commit()


def sync_all():
	"""Queue every published page. Returns how many went into the queue."""
	settings = frappe.get_single("Asyntai Settings")
	queued = 0

	for doctype in SUPPORTED:
		if not is_enabled(doctype, settings):
			continue
		if not frappe.db.exists("DocType", doctype):
			continue

		for row in frappe.get_all(
			doctype, filters={"published": 1}, fields=["name", "modified"]
		):
			frappe.enqueue(
				"asyntai.sync.sync_document",
				queue="long",
				timeout=QUEUE_TIMEOUT,
				job_id=f"asyntai-sync::{doctype}::{row.name}::{row.modified}",
				deduplicate=True,
				doctype=doctype,
				name=row.name,
			)
			queued += 1

	return queued


def update_counters():
	count = frappe.db.count("Asyntai Synced Page")
	frappe.db.set_single_value("Asyntai Settings", "synced_count", count)
	frappe.db.set_single_value("Asyntai Settings", "last_sync", now_datetime())

# Copyright (c) 2026, Asyntai and contributors
# For license information, please see license.txt

"""Put the Asyntai chat widget into every website page."""

import frappe

# The script tag goes in after the page load event. A plain async tag still
# holds the load event open until its fetch finishes, so a slow network would
# delay the page behind it.
LOADER = (
	'<script data-asyntai-src="{src}" data-asyntai-id="{widget_id}">'
	"(function(){{var c=document.currentScript;"
	'var u=c.getAttribute("data-asyntai-src");'
	'var i=c.getAttribute("data-asyntai-id");'
	'var l=function(){{var s=document.createElement("script");'
	"s.src=u;s.async=true;"
	's.setAttribute("data-asyntai-id",i);'
	"document.head.appendChild(s)}};"
	'if(document.readyState==="complete"){{l()}}'
	'else{{window.addEventListener("load",l)}}}})();'
	"</script>"
)


def get_widget_html():
	"""Return the loader tag, or an empty string when the widget is off."""
	try:
		settings = frappe.get_cached_doc("Asyntai Settings")
	except Exception:
		return ""

	if not settings.enabled or not settings.widget_id:
		return ""

	src = (settings.widget_script_url or "https://asyntai.com/static/js/chat-widget.js").strip()
	return LOADER.format(src=frappe.utils.escape_html(src), widget_id=frappe.utils.escape_html(settings.widget_id.strip()))


def update_website_context(context):
	"""Append the widget to head_include, keeping whatever is already there."""
	html = get_widget_html()
	if not html:
		return

	head_include = context.get("head_include") or ""
	if "data-asyntai-id" in head_include:
		return

	return {"head_include": head_include + html}

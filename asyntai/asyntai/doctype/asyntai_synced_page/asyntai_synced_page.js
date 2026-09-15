// Copyright (c) 2026, Asyntai and contributors
// For license information, please see license.txt

frappe.ui.form.on("Asyntai Synced Page", {
	refresh(frm) {
		// The reference is plain data, so build the link by hand.
		if (!frm.doc.reference_doctype || !frm.doc.reference_name) return;

		const route = frappe.router.slug(frm.doc.reference_doctype);
		const url = `/app/${route}/${encodeURIComponent(frm.doc.reference_name)}`;
		frm.get_field("reference_link").$wrapper.html(
			`<a href="${url}">${frappe.utils.escape_html(frm.doc.reference_name)}</a>`
		);
	},
});

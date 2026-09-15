// Copyright (c) 2026, Asyntai and contributors
// For license information, please see license.txt

frappe.ui.form.on("Asyntai Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: "asyntai.api.test_connection",
				freeze: true,
				freeze_message: __("Talking to Asyntai..."),
				callback(r) {
					if (!r.message) return;
					const names = (r.message.websites || [])
						.map((w) => w.domain)
						.join(", ");
					frappe.msgprint({
						title: __("Connected"),
						indicator: "green",
						message: __("Asyntai answered. Websites on this account: {0}", [
							names || __("none yet"),
						]),
					});
				},
			});
		});

		if (frm.doc.sync_enabled) {
			frm.add_custom_button(__("Send All Pages Now"), () => {
				frappe.confirm(
					__("Send every published Web Page and Blog Post to Asyntai?"),
					() => {
						frappe.call({
							method: "asyntai.api.sync_all",
							freeze: true,
							freeze_message: __("Queueing the pages..."),
							callback(r) {
								if (!r.message) return;
								frappe.msgprint({
									title: __("Queued"),
									indicator: "blue",
									message: __("{0} pages are on their way to Asyntai.", [
										r.message.queued,
									]),
								});
							},
						});
					}
				);
			});
		}

		if (frm.doc.lead_capture_enabled) {
			frm.add_custom_button(__("Stop Lead Capture"), () => {
				frappe.call({
					method: "asyntai.api.disconnect_leads",
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			});
		} else {
			frm.add_custom_button(__("Start Lead Capture"), () => {
				frappe.call({
					method: "asyntai.api.connect_leads",
					freeze: true,
					freeze_message: __("Registering the webhook..."),
					callback(r) {
						if (!r.message) return;
						frappe.show_alert({
							message: __("Asyntai will now send every chat lead to this site."),
							indicator: "green",
						});
						frm.reload_doc();
					},
				});
			});
		}

		frm.dashboard.clear_headline();
		if (!frm.doc.api_key) {
			frm.dashboard.set_headline(
				__(
					"Paste your Asyntai API key to start. You get it in the Asyntai dashboard under Settings, then API."
				)
			);
		}
	},
});

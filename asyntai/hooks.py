app_name = "asyntai"
app_title = "Asyntai AI Chatbot"
app_publisher = "Asyntai"
app_description = "AI chatbot that answers your website visitors and sends every lead into Frappe"
app_email = "hello@asyntai.com"
app_license = "mit"

# Website
# --------
# Put the chat widget into the <head> of every website page.

update_website_context = "asyntai.website.update_website_context"

# Document Events
# ---------------
# Keep the Asyntai knowledge base in step with the website content.

doc_events = {
	"Web Page": {
		"on_update": "asyntai.sync.on_document_update",
		"on_trash": "asyntai.sync.on_document_trash",
	},
	"Blog Post": {
		"on_update": "asyntai.sync.on_document_update",
		"on_trash": "asyntai.sync.on_document_trash",
	},
}

# Uninstall
# ---------

before_uninstall = "asyntai.install.before_uninstall"

# Fixtures
# --------

# Jinja
# -----

# Asyntai AI Chatbot for Frappe and ERPNext

Asyntai is an AI chat agent for your website. It reads your pages, answers your
visitors in their own language, and hands you the people who want to buy.

This app brings all of that into Frappe and ERPNext.

## What it does

**Answers your visitors.** The chat widget sits on every page of your Frappe
website. It replies in seconds, day and night, in the language the visitor
writes in.

**Learns your site.** Every published Web Page and Blog Post goes into the
Asyntai knowledge base. The chatbot answers from your own words and links back
to the page. Edit a page and Asyntai gets the new text; unpublish it and the
old answer stops.

**Creates the lead.** When a visitor leaves an email address or a phone number
in the chat, Asyntai posts it here and the app makes the Lead in ERPNext, or
the Contact on a plain Frappe site. The page, the country and the chat session
go on the record as a comment, so your team opens it and already knows the
story.

## Install

```bash
bench get-app https://github.com/asyntai/frappe-asyntai
bench --site your-site.com install-app asyntai
```

## Set it up

1. Sign in at [asyntai.com](https://asyntai.com/) and add your website.
2. In Asyntai, open **Settings**, then **API**, and copy the API key.
3. In Frappe, open **Asyntai Settings** and paste the key.
4. Tick **Show Chat Widget** and paste the **Widget ID** from the Asyntai
   install page.
5. Tick **Sync Content To Asyntai**, then press **Send All Pages Now**.
6. Press **Start Lead Capture**.

Full guide: [asyntai.com/documentation/integrations/frappe/](https://asyntai.com/documentation/integrations/frappe/)

## Requirements

- Frappe v15, with or without ERPNext
- An Asyntai account on the Starter plan or higher, because the app uses the
  Asyntai API

## Licence

MIT

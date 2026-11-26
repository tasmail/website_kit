/* Website Kit: the contact form of the standard Contact pages (loaded only there).
 * Posts to the stock Frappe method `send_message` through the guard client (frappe_guard, action "contact"). It never posts
 * without the guard client, never before the 3-second minimum and never when the trap field is filled. Texts come from the
 * data attributes of the form, so one script serves both languages. */
(function () {
	"use strict";
	var opened = Date.now();
	var URL = "/api/method/frappe.www.contact.send_message";
	var MINIMUM = 3000;

	function init() {
		var form = document.getElementById("wk-contact-form");
		if (!form) {
			return;
		}
		var status = form.querySelector("[data-wk-status]");
		var button = form.querySelector("button[type=submit]");

		function say(text) {
			status.textContent = text;
			status.hidden = false;
		}

		form.addEventListener("submit", function (event) {
			event.preventDefault();
			if (form.elements.website.value || Date.now() - opened < MINIMUM || !window.FrappeGuard) {
				say(form.dataset.error);
				return;
			}
			if (!form.checkValidity()) {
				form.reportValidity();
				return;
			}
			var name = form.elements.sender_name.value.trim();
			var message = (name ? name + "\n\n" : "") + form.elements.message.value;
			var body = new URLSearchParams({
				sender: form.elements.sender.value,
				subject: form.dataset.subject,
				message: message
			});
			button.disabled = true;
			say(form.dataset.sending);
			window.FrappeGuard.request(URL, { action: form.dataset.guardAction, method: "POST", body: body })
				.then(function (response) {
					if (!response.ok) {
						throw new Error(String(response.status));
					}
					say(form.dataset.success);
					form.reset();
				})
				.catch(function () {
					say(form.dataset.error);
				})
				.then(function () {
					button.disabled = false;
				});
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();

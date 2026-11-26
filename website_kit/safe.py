"""A wrapper for the Jinja functions of the standard pages: an error must never turn a public page into a 500."""

import functools

import frappe


def never_raises(function):
	"""Log the error to the Error Log and return an empty string instead of raising into the page render."""

	@functools.wraps(function)
	def wrapper(*args):
		try:
			return function(*args)
		except Exception:
			frappe.log_error(title=f"Website Kit: {function.__name__} failed")
			return ""

	return wrapper

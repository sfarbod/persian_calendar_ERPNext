"""Register brace-template and Jinja context patches (once per process)."""

from __future__ import annotations

_patches_applied = False


def apply_template_patches() -> None:
	global _patches_applied
	if _patches_applied:
		return
	_patches_applied = True

	_patch_document_title_field()
	_patch_notification_context()
	_patch_external_description_renderers()


def _patch_document_title_field() -> None:
	from frappe.model.document import Document

	from persian_calendar.utils.template_format import doc_as_format_context, render_brace_template

	if getattr(Document.set_title_field, "_jalali_patched", False):
		return

	_original = Document.set_title_field

	def set_title_field(self):
		def get_values():
			values = self.as_dict()
			for key, value in values.items():
				if value is None:
					values[key] = ""
			return values

		if self.meta.get("title_field") != "title":
			return _original(self)

		df = self.meta.get_field(self.meta.title_field)
		if not df:
			return

		if df.options:
			self.set(df.fieldname, render_brace_template(df.options, get_values()))
		elif self.is_new() and not self.get(df.fieldname) and df.default:
			self.set(df.fieldname, render_brace_template(df.default, get_values()))

	set_title_field._jalali_patched = True
	Document.set_title_field = set_title_field


def _patch_notification_context() -> None:
	"""Expose doc fields at top level so ``{{ toshamshi(cheque_due_date) }}`` works in alerts."""
	try:
		from frappe.email.doctype.notification import notification as notification_module
	except ImportError:
		return

	if getattr(notification_module.get_context, "_jalali_patched", False):
		return

	_original = notification_module.get_context

	def get_context(doc):
		ctx = _original(doc)
		doc_obj = ctx.get("doc")
		if doc_obj is not None:
			from persian_calendar.utils.template_format import doc_as_format_context

			flat = doc_as_format_context(doc_obj)
			for key, value in flat.items():
				ctx.setdefault(key, value)
		return ctx

	get_context._jalali_patched = True
	notification_module.get_context = get_context


def _patch_external_description_renderers() -> None:
	"""ERPNext Extensions PDC JE / description templates use ``format_map``."""
	try:
		import erpnext_extensions.cheque_management.utils.descriptions as descriptions
	except ImportError:
		return

	if getattr(descriptions.render_description_template, "_jalali_patched", False):
		return

	from persian_calendar.utils.template_format import render_brace_template

	_original = descriptions.render_description_template

	def render_description_template(template, context):
		return render_brace_template(template, context)

	render_description_template._jalali_patched = True
	descriptions.render_description_template = render_description_template

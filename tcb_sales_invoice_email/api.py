import frappe
from frappe import _


@frappe.whitelist()
def uncheck_invoice_mail(invoice_name):
    """
    Uncheck the custom_send_due_invoice_email flag for a submitted Sales Invoice

    Args:
        invoice_name (str): The name of the Sales Invoice document

    Returns:
        dict: Status and message of the operation
    """
    try:
        # Verify the document exists and is submitted
        doc = frappe.get_doc("Sales Invoice", invoice_name)

        if doc.docstatus != 1:
            return {
                "success": False,
                "error": _("Invoice must be submitted to uncheck mail flag")
            }

        if not doc.custom_send_due_invoice_email:
            return {
                "success": False,
                "error": _("Invoice mail flag is already unchecked")
            }

        # Use db.set_value since we're modifying a submitted document
        frappe.db.set_value(
            "Sales Invoice",
            invoice_name,
            "custom_send_due_invoice_email",
            0,
            update_modified=False
        )

        frappe.db.commit()

        return {
            "success": True,
            "message": _("Invoice mail flag unchecked successfully")
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Failed to uncheck invoice mail flag: {e}")
        return {
            "success": False,
            "error": _("Error unchecking invoice mail flag: {0}").format(str(e))
        }

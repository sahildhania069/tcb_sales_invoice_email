from datetime import datetime

import frappe
from frappe import _
from frappe.email.doctype.email_template.email_template import get_email_template
from frappe.utils import add_days, date_diff, flt, get_url_to_form, getdate, today


def send_delivery_emails():
    """
    Scheduled task to send delivery emails for sales invoices.
    Runs at midnight to check for invoices that need delivery emails sent.
    """
    frappe.logger().info("Starting delivery email process for sales invoices")

    # Find qualifying invoices
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,  # Submitted invoices
            "custom_send_delivery_mail": 1,  # Send delivery mail flag is set
            "custom_mail_sent_to_customer": 0,  # Email not yet sent
        },
        fields=["name", "customer", "customer_name"],
    )

    frappe.logger().info(
        f"Found {len(invoices)} invoices for delivery email processing"
    )

    # Process each invoice
    for invoice in invoices:
        try:
            process_invoice_email(invoice.name)
        except Exception as e:
            frappe.logger().error(f"Error processing invoice {invoice.name}: {e!s}")
            continue


def process_invoice_email(invoice_name):
    """
    Process email sending for a single invoice.

    Args:
        invoice_name: The name/ID of the Sales Invoice
    """
    doc = frappe.get_doc("Sales Invoice", invoice_name)

    # Skip if no email recipients defined
    if (
        not doc.get("custom_dispatch_email_to")
        or len(doc.custom_dispatch_email_to) == 0
    ):
        frappe.logger().info(
            f"No email recipients defined for {invoice_name}, skipping"
        )
        return

    # Get email recipients by type (TO, CC, BCC)
    recipients = {"to": [], "cc": [], "bcc": []}

    for recipient in doc.custom_dispatch_email_to:
        if recipient.contact and recipient.send_as:
            # Get contact's email directly from email_id field
            contact_data = frappe.db.get_value(
                "Contact", recipient.contact, "email_id", as_dict=1
            )

            if contact_data and contact_data.email_id:
                send_as = recipient.send_as.lower()
                if send_as in recipients:
                    recipients[send_as].append(contact_data.email_id)

    # Check if we have any recipients
    if not recipients["to"]:
        frappe.logger().warning(
            f"No 'TO' recipients found for {invoice_name}, skipping"
        )
        return

    try:
        # Prepare email content
        subject = f"Material Shipment Notification - {doc.name}"

        # Get invoice details for email
        invoice_url = get_url_to_form("Sales Invoice", doc.name)
        invoice_data = {
            "invoice_no": doc.name,
            "invoice_date": doc.get("posting_date", ""),
            "po_number": doc.get("po_no", "N/A"),
            "po_date": doc.get("po_date", "N/A"),
            "transporter": doc.get("transporter", ""),
            "transport_receipt_no": doc.get("lr_no", ""),
            "transport_receipt_date": doc.get("lr_date", ""),
            "customer_name": doc.customer_name,
            "invoice_url": invoice_url,
        }

        # Try to get email template
        template_name = "Sales Invoice Delivery Notification"
        template_args = invoice_data

        try:
            email_content = get_email_template(template_name, template_args)
            message = email_content.message
        except Exception:
            # Fallback to default email content if template not found
            message = get_default_email_content(invoice_data)

        # Send email
        frappe.sendmail(
            recipients=recipients["to"],
            cc=recipients["cc"] if recipients["cc"] else None,
            bcc=recipients["bcc"] if recipients["bcc"] else None,
            subject=subject,
            message=message,
            attachments=[get_invoice_attachment(doc)],
            reference_doctype="Sales Invoice",
            reference_name=doc.name,
        )

        # Update invoice status using db.set_value since document is submitted
        frappe.db.set_value(
            "Sales Invoice",
            doc.name,
            "custom_mail_sent_to_customer",
            1,
            update_modified=False,
        )

        frappe.db.commit()
        frappe.logger().info(f"Delivery email sent successfully for {invoice_name}")

    except Exception as e:
        frappe.db.rollback()
        frappe.logger().error(
            f"Failed to send delivery email for {invoice_name}: {e!s}"
        )
        raise


def get_invoice_attachment(doc):
    """Get the sales invoice as an attachment"""
    invoice_print = frappe.attach_print(
        "Sales Invoice",
        doc.name,
        file_name=f"{doc.name}.pdf",
        print_format="Standard",  # Use your preferred print format
    )
    return invoice_print


def get_default_email_content(invoice_data):
    """Generate default email content if template is not found"""
    return f"""
    <p>Dear {invoice_data.get('customer_name', '')},</p>

    <p>Greetings of the day,</p>
    <p>We thought you would be happy to know that we have Shipped your material. The details are as follows:</p>

    <p>PO Number: {invoice_data.get('po_number', 'N/A')}<br>
    PO Date: {invoice_data.get('po_date', 'N/A')}<br>
    Invoice Date: {invoice_data.get('invoice_date', '')}<br>
    Transporter: {invoice_data.get('transporter', '')}<br>
    Transport Receipt No: {invoice_data.get('transport_receipt_no', '')}<br>
    Transport Receipt Date: {invoice_data.get('transport_receipt_date', '')}</p>

    <p>Please find attached your Sales Invoice {invoice_data.get('invoice_no', '')}.</p>

    <p>Thank you for giving us an opportunity to serve you.Kindly Note that this is an auto-generated email.</p>
    <p>If you have any concerns you can reply to this email and we will promptly look into it.
    Alternatively, you can reach out to us at +91 0000000000</p>

    <p>Regards,<br>
    Stores and Logistics Dept,<br>
    Felix Tools</p>
    """


def send_overdue_invoice_emails():
    """
    Scheduled task to send overdue invoice reminder emails.
    Runs every 4 days to check for invoices that are overdue and need reminder emails sent.
    """
    frappe.logger().info("Starting overdue invoice email process")

    # Find qualifying invoices that are overdue
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,  # Submitted invoices
            "custom_send_due_invoice_email": 1,  # Send overdue invoice email flag is set
            "outstanding_amount": [">", 0],  # Has outstanding amount
            "due_date": ["<", today()],  # Due date has passed
        },
        fields=[
            "name",
            "customer",
            "customer_name",
            "po_no",
            "posting_date",
            "rounded_total",
            "grand_total",
            "outstanding_amount",
            "due_date",
        ],
    )

    frappe.logger().info(f"Found {len(invoices)} overdue invoices for email processing")

    # Group invoices by customer
    customer_invoices = {}
    for invoice in invoices:
        if invoice.customer not in customer_invoices:
            customer_invoices[invoice.customer] = {
                "name": invoice.customer_name,
                "invoices": [],
            }

        # Calculate days overdue
        days_overdue = date_diff(today(), getdate(invoice.due_date))

        # Add invoice to customer's list
        customer_invoices[invoice.customer]["invoices"].append(
            {
                "name": invoice.name,
                "po_no": invoice.po_no or "",
                "posting_date": invoice.posting_date,
                "due_date": invoice.due_date,
                "rounded_total": invoice.rounded_total,
                "grand_total": invoice.grand_total,
                "outstanding_amount": invoice.outstanding_amount,
                "days_overdue": days_overdue,
            }
        )

    # Process each customer's invoices
    for customer, data in customer_invoices.items():
        try:
            process_overdue_invoice_email(customer, data)
        except Exception as e:
            frappe.logger().error(
                f"Error processing overdue invoices for customer {customer}: {e!s}"
            )
            continue


def process_overdue_invoice_email(customer_id, customer_data):
    """
    Process email sending for a customer's overdue invoices.

    Args:
        customer_id: The customer ID
        customer_data: Dict containing customer name and list of overdue invoices
    """
    # Fetch the first invoice to get email recipients
    first_invoice_name = customer_data["invoices"][0]["name"]

    # Try to get email recipients from the custom overdue_invoice_email_to child table
    recipients = {"to": [], "cc": [], "bcc": []}
    email_recipients = frappe.get_all(
        "Overdue Invoice Mail To",
        filters={"parent": first_invoice_name},
        fields=["contact", "send_as"],
    )

    # If no recipients are defined, log and skip
    if not email_recipients or len(email_recipients) == 0:
        frappe.logger().info(
            f"No email recipients defined for customer {customer_id}, skipping"
        )
        return

    # Collect email addresses from contacts
    for recipient in email_recipients:
        if recipient.contact and recipient.send_as:
            contact_data = frappe.db.get_value(
                "Contact", recipient.contact, "email_id", as_dict=1
            )

            if contact_data and contact_data.email_id:
                send_as = recipient.send_as.lower()
                if send_as in recipients:
                    recipients[send_as].append(contact_data.email_id)

    # Check if we have any recipients
    if not recipients["to"]:
        frappe.logger().warning(
            f"No 'TO' recipients found for customer {customer_id}, skipping"
        )
        return

    try:
        # Prepare email content
        subject = f"Outstanding Invoice Reminder - {customer_data['name']}"

        # Generate HTML table for invoices
        invoice_table = get_overdue_invoice_table(customer_data["invoices"])

        # Try to get email template
        template_name = "Overdue Invoice Reminder"
        template_args = {
            "customer_name": customer_data["name"],
            "invoice_table": invoice_table,
            "total_outstanding": sum(
                inv["outstanding_amount"] for inv in customer_data["invoices"]
            ),
        }

        try:
            email_content = get_email_template(template_name, template_args)
            message = email_content.message
        except Exception:
            # Fallback to default overdue invoice email content
            message = get_default_overdue_email_content(
                customer_data["name"], invoice_table
            )

        # Send email
        frappe.sendmail(
            recipients=recipients["to"],
            cc=recipients["cc"] if recipients["cc"] else None,
            bcc=recipients["bcc"] if recipients["bcc"] else None,
            subject=subject,
            message=message,
            reference_doctype="Sales Invoice",
            reference_name=first_invoice_name,
        )

        # Update status for all invoices
        for invoice in customer_data["invoices"]:
            frappe.db.set_value(
                "Sales Invoice",
                invoice["name"],
                "custom_overdue_mail_sent",  # Assuming this field exists or needs to be created
                1,
                update_modified=False,
            )

        frappe.db.commit()
        frappe.logger().info(
            f"Overdue invoice email sent successfully for {customer_id}"
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.logger().error(
            f"Failed to send overdue invoice email for {customer_id}: {e!s}"
        )
        raise


def get_overdue_invoice_table(invoices):
    """
    Generate HTML table for overdue invoices.
    Highlight invoices overdue by more than 20 days.
    """
    table_header = """
    <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f2f2f2;">
            <th>S. No</th>
            <th>Invoice Number</th>
            <th>Invoice Date</th>
            <th>PO Number</th>
            <th>Due Date</th>
            <th>Invoiced Amount</th>
            <th>Outstanding Amount</th>
            <th>Overdue By</th>
        </tr>
    """

    table_rows = ""
    total_outstanding = 0

    for idx, invoice in enumerate(invoices, 1):
        # Highlight rows that are overdue by more than 20 days
        row_style = (
            "" if invoice["days_overdue"] <= 20 else "background-color: #ffcccc;"
        )

        table_rows += f"""
        <tr style="{row_style}">
            <td align="center">{idx}</td>
            <td>{invoice['name']}</td>
            <td align="center">{invoice['posting_date']}</td>
            <td>{invoice['po_no']}</td>
            <td align="center">{invoice['due_date']}</td>
            <td align="right">{frappe.format(invoice['grand_total'], {'fieldtype': 'Currency'})}</td>
            <td align="right">{frappe.format(invoice['outstanding_amount'], {'fieldtype': 'Currency'})}</td>
            <td align="center">{invoice['days_overdue']} days</td>
        </tr>
        """

        total_outstanding += flt(invoice["outstanding_amount"])

    # Add total row
    table_footer = f"""
        <tr style="background-color: #f2f2f2; font-weight: bold;">
            <td colspan="6" align="right">Total</td>
            <td align="right">{frappe.format(total_outstanding, {'fieldtype': 'Currency'})}</td>
            <td></td>
        </tr>
    </table>
    """

    return table_header + table_rows + table_footer


def get_default_overdue_email_content(customer_name, invoice_table):
    """Generate default email content for overdue invoice reminder"""
    return f"""
    <p>Dear {customer_name},</p>

    <p>Greetings of the day</p>

    <p>The following invoices are currently outstanding as per our records:</p>

    {invoice_table}

    <p>Please review them at your convenience and arrange for payment at the earliest.</p>

    <p>Please note that this is an automated, system-generated payment reminder sent at regular intervals of every 3 days. However, if you have already made the payment or have any queries, feel free to reply to this email—our team will promptly look into it.</p>

    <p>Regards,<br>
    Felix Tools Private Limited</p>
    """

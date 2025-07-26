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
    frappe.log_error(
        message=f"Starting process_invoice_email for {invoice_name}",
        title="Sales Invoice Email Process",
    )
    doc = frappe.get_doc("Sales Invoice", invoice_name)

    # Skip if no email recipients defined
    frappe.log_error(
        message=f"Checking email recipients for {invoice_name}",
        title="Sales Invoice Email Recipients",
    )
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
    frappe.log_error(
        message=f"Processing email recipients for {invoice_name}",
        title="Sales Invoice Email Recipients",
    )

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
        frappe.log_error(
            message=f"Getting email template '{template_name}' for {invoice_name}",
            title="Sales Invoice Email Template",
        )

        try:
            email_content = get_email_template(template_name, template_args)
            message = email_content.message
        except Exception:
            # Fallback to default email content if template not found
            message = get_default_email_content(invoice_data)

        # Send email
        frappe.log_error(
            message=f"Preparing email sending for {invoice_name} with recipients: to={recipients['to']}, cc={recipients['cc']}, bcc={recipients['bcc']}",
            title="Sales Invoice Email Send",
        )

        # Attachment will be handled during email sending

        # Send email with PDF attachment using Communication.make
        try:
            from frappe.core.doctype.communication.email import make

            frappe.log_error(
                message=f"Using Communication.make to send email for {invoice_name} with PDF attachment",
                title="Sales Invoice Email - Using Communication.make",
            )

            # This will both generate the PDF using the specified print format
            # and send it as an attachment in a single call
            # Get default outgoing email account
            from frappe.email.doctype.email_account.email_account import EmailAccount

            # Find the default outgoing email account
            email_account_dict = EmailAccount.find_outgoing()
            email_account = email_account_dict.get("default") if email_account_dict else None

            make(
                doctype=doc.doctype,
                name=doc.name,
                content=message,
                subject=subject,
                sent_or_received="Sent",
                sender=(
                    email_account.email_id if email_account else None
                ),  # Use system default outgoing email
                sender_full_name=(
                    email_account.name if email_account else None
                ),  # Use account name
                recipients=recipients["to"],
                communication_medium="Email",
                send_email=1,
                print_html=None,
                print_format="Felix Sales Invoice",  # Use the specific print format
                attachments=None,  # No additional attachments needed
                send_me_a_copy=False,
                cc=recipients["cc"] if recipients["cc"] else None,
                bcc=recipients["bcc"] if recipients["bcc"] else None,
                read_receipt=None,
                print_letterhead=True,
                email_template=None,
                communication_type=None,
                send_after=None,
                now=True,  # Send immediately
            )

            frappe.log_error(
                message=f"Email with PDF sent successfully for {invoice_name} using Communication.make",
                title="Sales Invoice Email Send Success",
            )
        except Exception as e:
            frappe.log_error(
                message=f"Failed to send email with PDF for {invoice_name}: {str(e)}\n\nTraceback: {frappe.get_traceback()}",
                title="Sales Invoice Email Send Error",
            )
            raise  # Re-raise to ensure proper error handling

        frappe.log_error(
            message=f"Email sent successfully for {invoice_name}, updating status",
            title="Sales Invoice Email Success",
        )

        # Update invoice status using db.set_value since document is submitted
        frappe.db.set_value(
            "Sales Invoice",
            doc.name,
            "custom_mail_sent_to_customer",
            1,
            update_modified=False,
        )

        frappe.log_error(
            message=f"Status updated for {invoice_name}, committing transaction",
            title="Sales Invoice Email DB Update",
        )
        frappe.db.commit()
        frappe.logger().info(f"Delivery email sent successfully for {invoice_name}")
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            message=f"FAILED process_invoice_email for {invoice_name}: {e!s}\n\nTraceback: {frappe.get_traceback()}",
            title="Sales Invoice Email Error",
        )
        frappe.logger().error(
            f"Failed to send delivery email for {invoice_name}: {e!s}"
        )
        raise


def get_invoice_attachment(doc):
    frappe.log_error(
        message=f"Starting attachment process for invoice {doc.name}",
        title="Sales Invoice Email Attachment Start",
    )

    # First, check if this invoice already has an attachment we can use directly
    try:
        # Look for existing PDF attachments
        attachments = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "Sales Invoice",
                "attached_to_name": doc.name,
                "file_name": ["like", "%.pdf"],
            },
            fields=["name", "file_url", "file_name"],
            order_by="creation desc",  # Get the most recent first
        )

        if attachments:
            # Found an existing attachment, use it
            frappe.log_error(
                message=f"Found existing PDF attachment for {doc.name}: {attachments[0].name}",
                title="Sales Invoice Email Attachment Found",
            )

            file_doc = frappe.get_doc("File", attachments[0].name)
            file_content = file_doc.get_content()

            if file_content:
                return {"fname": file_doc.file_name, "fcontent": file_content}

        # No usable existing attachment, create a simple text attachment with invoice details and link
        frappe.log_error(
            message=f"Creating text attachment with invoice details for {doc.name}",
            title="Sales Invoice Email Text Fallback",
        )

        # Create a detailed text file with invoice information
        content = f"""INVOICE DETAILS: {doc.name}

Date: {doc.posting_date}
Customer: {doc.customer_name}
Grand Total: {doc.get_formatted('grand_total')}

"""

        # Add line items
        content += "Items:\n"
        for idx, item in enumerate(doc.items, 1):
            content += f"{idx}. {item.item_name} - {item.qty} {item.uom} @ {item.get_formatted('rate')} = {item.get_formatted('amount')}\n"

        content += f"\nTotal: {doc.get_formatted('grand_total')}\n"
        content += f"\nView invoice online at: {frappe.utils.get_url()}/app/sales-invoice/{doc.name}\n"

        return {"fname": f"{doc.name}.txt", "fcontent": content}

    except Exception as e:
        frappe.log_error(
            message=f"Failed to get attachment for {doc.name}: {str(e)}\n\nTraceback: {frappe.get_traceback()}",
            title="Sales Invoice Email Attachment Error",
        )
        # Create a minimal fallback attachment with just the invoice link
        content = f"Invoice: {doc.name}\nView at: {frappe.utils.get_url()}/app/sales-invoice/{doc.name}"
        return {"fname": f"{doc.name}.txt", "fcontent": content}


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
    frappe.log_error(
        message="Starting overdue invoice email process",
        title="Sales Invoice Email Overdue Process",
    )

    # Find qualifying invoices that are overdue
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,  # Submitted invoices
            "custom_send_due_invoice_email": 1,  # Send overdue invoice email flag is set
            "outstanding_amount": [">", 0],  # Has outstanding amount
            "custom_expected_payment_due_date": ["<", today()],  # Due date has passed
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
            "custom_expected_payment_due_date",
        ],
    )

    frappe.logger().info(f"Found {len(invoices)} overdue invoices for email processing")
    frappe.log_error(
        message=f"Found {len(invoices)} overdue invoices for email processing",
        title="Sales Invoice Email Overdue Process",
    )

    # Group invoices by customer
    customer_invoices = {}
    for invoice in invoices:
        if invoice.customer not in customer_invoices:
            customer_invoices[invoice.customer] = {
                "name": invoice.customer_name,
                "invoices": [],
            }

        # Calculate days overdue
        days_overdue = date_diff(today(), getdate(invoice.custom_expected_payment_due_date))

        # Add invoice to customer's list
        customer_invoices[invoice.customer]["invoices"].append(
            {
                "name": invoice.name,
                "po_no": invoice.po_no or "",
                "posting_date": invoice.posting_date,
                "custom_expected_payment_due_date": invoice.custom_expected_payment_due_date,
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
            frappe.log_error(
                message=f"Error processing overdue invoices for customer {customer}: {e!s}\n\nTraceback: {frappe.get_traceback()}",
                title="Sales Invoice Email Overdue Process Error",
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
        "Overdue Mail Detail",
        filters={"parent": first_invoice_name},
        fields=["contact", "send_as"],
    )

    # If no recipients are defined, log and skip
    if not email_recipients or len(email_recipients) == 0:
        frappe.log_error(
            message=f"No email recipients defined for customer {customer_id}, skipping",
            title="Sales Invoice Email Overdue Process",
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
        frappe.log_error(
            message=f"No 'TO' recipients found for customer {customer_id}, skipping",
            title="Sales Invoice Email Overdue Process",
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
        # for invoice in customer_data["invoices"]:
        #     frappe.db.set_value(
        #         "Sales Invoice",
        #         invoice["name"],
        #         "custom_overdue_mail_sent",  # Assuming this field exists or needs to be created
        #         1,
        #         update_modified=False,
        #     )

        frappe.db.commit()
        frappe.log_error(
            message=f"Overdue invoice email sent successfully for {customer_id}",
            title="Sales Invoice Email Overdue Process",
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            message=f"Failed to send overdue invoice email for {customer_id}: {e!s}\n\nTraceback: {frappe.get_traceback()}",
            title="Sales Invoice Email Overdue Process Error",
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
            <td align="center">{invoice['custom_expected_payment_due_date']}</td>
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

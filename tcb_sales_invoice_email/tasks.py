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
            email_account = (
                email_account_dict.get("default") if email_account_dict else None
            )

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
        frappe.log_error(
            message=f"Delivery email sent successfully for {invoice_name}",
            title="Sales Invoice Email Success",
        )
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
        title="Sales Invoice Email Overdue Process START",
    )

    # Find qualifying invoices that are overdue
    current_date = today()
    overdue_invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,
            "custom_send_due_invoice_email":1,
            "outstanding_amount": [">", 0],  # Has outstanding amount
            "custom_expected_payment_due_date": ["<", current_date],  # Past due date
            "status": ["not in", ["Paid", "Closed", "Cancelled"]],
        },
        fields=[
            "name",
            "customer",
            "customer_name",
            "po_no",
            "posting_date",
            "custom_expected_payment_due_date",
            "rounded_total",
            "grand_total",
            "outstanding_amount",
        ],
    )

    # Debug: Print raw SQL query for manual verification
    last_query = frappe.db.last_query
    frappe.log_error(
        message=f"SQL Query for overdue invoices:\n{last_query}",
        title="Overdue Invoice Query",
    )

    if not overdue_invoices:
        frappe.logger().info("No overdue invoices found")
        frappe.log_error(
            message="No overdue invoices found",
            title="Sales Invoice Email Overdue Process",
        )
        return

    frappe.log_error(
        message=f"Found {len(overdue_invoices)} overdue invoices",
        title="Sales Invoice Email Overdue Process",
    )

    # Create a contact-based structure instead of customer-based
    # This way each contact only gets invoices they're associated with
    contact_invoices = {}

    if not overdue_invoices:
        frappe.log_error(
            message="No overdue invoices found in query result",
            title="Sales Invoice Email Overdue Process Empty",
        )

    for invoice in overdue_invoices:
        # Log each invoice we're processing
        frappe.log_error(
            message=f"Processing invoice {invoice.name} for customer {invoice.customer_name}",
            title="Processing Individual Invoice",
        )

        # Calculate days overdue
        days_overdue = date_diff(current_date, getdate(invoice.custom_expected_payment_due_date))

        # Get all contacts for this invoice
        try:
            dispatch_emails = frappe.get_all(
                "Overdue Mail Detail",
                filters={"parent": invoice.name},
                fields=["contact", "send_as"],
            )

            # Log what we found
            frappe.log_error(
                message=f"Found {len(dispatch_emails)} contacts for invoice {invoice.name}",
                title="Invoice Contacts",
            )
        except Exception as dispatch_error:
            frappe.log_error(
                message=f"Error getting dispatch emails for invoice {invoice.name}: {str(dispatch_error)}\n\nTraceback: {frappe.get_traceback()}",
                title="Dispatch Email Query Error",
            )
            dispatch_emails = []

        if not dispatch_emails:
            frappe.logger().info(
                f"No contacts found for invoice {invoice.name}, skipping"
            )
            frappe.log_error(
                message=f"No contacts found for invoice {invoice.name}, skipping this invoice",
                title="Missing Contacts for Invoice",
            )
            continue

        # Create invoice data to store
        invoice_data = {
            "name": invoice.name,
            "po_no": invoice.po_no or "",
            "posting_date": invoice.posting_date,
            "custom_expected_payment_due_date": invoice.custom_expected_payment_due_date,
            "rounded_total": invoice.rounded_total,
            "grand_total": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "days_overdue": days_overdue,
            "customer": invoice.customer,
            "customer_name": invoice.customer_name,
        }

        # Add this invoice to each contact's list
        frappe.log_error(
            message=f"Starting to process {len(dispatch_emails)} contacts for invoice {invoice.name}",
            title="Processing Invoice Contacts",
        )

        for dispatch in dispatch_emails:
            # Log each dispatch processing
            frappe.log_error(
                message=f"Processing dispatch entry for invoice {invoice.name}: {dispatch.name if hasattr(dispatch, 'name') else 'No Name'}",
                title="Processing Dispatch Entry",
            )

            if not dispatch.contact:
                frappe.log_error(
                    message=f"Dispatch entry for invoice {invoice.name} has no contact, skipping",
                    title="Missing Contact in Dispatch",
                )
                continue

            contact_id = dispatch.contact

            # Log the contact we're processing
            frappe.log_error(
                message=f"Adding invoice {invoice.name} to contact {contact_id}",
                title="Adding Invoice To Contact",
            )

            # Initialize contact entry if it doesn't exist
            if contact_id not in contact_invoices:
                contact_invoices[contact_id] = {
                    "send_as": (
                        dispatch.send_as if hasattr(dispatch, "send_as") else "to"
                    ),
                    "invoices": [],
                    # We'll get email and other details later
                }
                frappe.log_error(
                    message=f"Created new contact entry for contact {contact_id}",
                    title="New Contact Entry",
                )

            # Add this invoice to the contact's list
            contact_invoices[contact_id]["invoices"].append(invoice_data)

    frappe.log_error(
        message=f"Found {len(contact_invoices)} contacts with overdue invoices",
        title="Sales Invoice Email Overdue Process",
    )
    # Detailed log of the final contact_invoices structure
    for contact_id, data in contact_invoices.items():
        invoice_list = ", ".join([inv["name"] for inv in data["invoices"]])
        frappe.log_error(
            message=f"Contact {contact_id} has {len(data['invoices'])} invoices: {invoice_list}",
            title="Contact Invoice Summary",
        )

    # Process each contact's invoices
    for contact_id, data in contact_invoices.items():
        frappe.log_error(
            message=f"Starting to process contact {contact_id} with {len(data['invoices'])} invoices",
            title="Processing Contact Invoices",
        )
        try:
            process_contact_overdue_invoice_email(contact_id, data)
        except Exception as e:
            frappe.logger().error(
                f"Error processing overdue invoices for contact {contact_id}: {e!s}"
            )
            frappe.log_error(
                message=f"Error processing overdue invoices for contact {contact_id}: {e!s}\n\nTraceback: {frappe.get_traceback()}",
                title="Sales Invoice Email Overdue Process Error",
            )
            continue


def process_contact_overdue_invoice_email(contact_id, contact_data):
    """Process overdue invoice email for a specific contact - only sending invoices relevant to this contact"""
    frappe.logger().info(f"Processing overdue invoices for contact {contact_id}")
    frappe.log_error(
        message=f"Processing overdue invoices for contact {contact_id}",
        title="Sales Invoice Email Overdue Process",
    )

    try:
        # Get contact email
        contact_email = frappe.db.get_value("Contact", contact_id, "email_id")
        if not contact_email:
            frappe.logger().info(f"No email found for contact {contact_id}, skipping")
            frappe.log_error(
                message=f"No email found for contact {contact_id}",
                title="Sales Invoice Email Overdue Process Error",
            )
            return

        # Get customer name from the first invoice
        if not contact_data["invoices"]:
            frappe.logger().info(f"No invoices for contact {contact_id}, skipping")
            frappe.log_error(
                message=f"No invoices found for contact {contact_id}",
                title="Sales Invoice Email Overdue Process Error",
            )
            return

        customer_name = contact_data["invoices"][0]["customer_name"]

        # Set up recipients based on the contact's send_as setting
        recipients = {"to": [], "cc": [], "bcc": []}
        send_as = contact_data["send_as"].lower() if contact_data["send_as"] else "to"
        if send_as in recipients:
            recipients[send_as].append(contact_email)
        else:
            # Default to TO if send_as is invalid
            recipients["to"].append(contact_email)

      
        # Build invoice table for only this contact's invoices
        invoice_table = get_overdue_invoice_table(contact_data["invoices"])

        # Calculate total outstanding for this contact's invoices
        total_outstanding = sum(
            inv["outstanding_amount"] for inv in contact_data["invoices"]
        )

        # Try to get email template
        template_name = "Overdue Invoice Reminder"
        template_args = {
            "customer_name": customer_name,
            "invoice_table": invoice_table,
            "total_outstanding": total_outstanding,
        }

        try:
            message = frappe.get_template(template_name).render(template_args)
        except Exception:
            # Fallback to default overdue invoice email content
            message = get_default_overdue_email_content(customer_name, invoice_table)

        # Send email
        subject = "Payment Reminder - Overdue Invoices"

        # Get default outgoing email account
        from frappe.email.doctype.email_account.email_account import EmailAccount

        email_account_dict = EmailAccount.find_outgoing()
        email_account = (
            email_account_dict.get("default") if email_account_dict else None
        )

        # Log the email we're about to send for debugging
        frappe.log_error(
            message=f"Preparing to send email to {contact_email} with {len(contact_data['invoices'])} invoices\n"
            f"Subject: {subject}\n"
            f"Recipients: {recipients['to']}",
            title="Email Sending Preparation",
        )

        try:
            # Send email with this contact's invoices
            # Send immediately with now=True
            frappe.sendmail(
                recipients=recipients["to"],
                subject=subject,
                message=message,
                sender=email_account.email_id if email_account else None,
                cc=recipients["cc"] if recipients["cc"] else None,
                bcc=recipients["bcc"] if recipients["bcc"] else None,
                reference_doctype="Contact",
                reference_name=contact_id,
            )

            # Log successful email sending
            frappe.log_error(
                message=f"Successfully sent email to {contact_email}",
                title="Email Sent Successfully",
            )
        except Exception as email_error:
            # Catch and log any errors during email sending
            frappe.log_error(
                message=f"Error sending email to {contact_email}: {str(email_error)}\n\nTraceback: {frappe.get_traceback()}",
                title="Email Sending Error",
            )

        # Add additional logging
        frappe.log_error(
            message=f"Completed overdue email process for contact {contact_id}. Committing transaction.",
            title="Overdue Invoice Email Process Complete",
        )

        # Ensure we commit the transaction
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            message=f"Failed to send overdue invoice email to contact {contact_id}: {e!s}\n\nTraceback: {frappe.get_traceback()}",
            title="Sales Invoice Email Overdue Process Error",
        )
        raise


def process_overdue_invoice_email(customer_id, customer_data):
    """Legacy function kept for backward compatibility"""
    frappe.logger().info(
        f"Legacy process_overdue_invoice_email called for {customer_id} - using new contact-based method"
    )
    # This function is now deprecated, but kept for backward compatibility
    # The actual processing is now done by process_contact_overdue_invoice_email


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

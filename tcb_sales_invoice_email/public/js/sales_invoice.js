frappe.ui.form.on('Sales Invoice', {
	refresh: function(frm) {
		setup_contact_filters(frm);
		
		// Add custom button to uncheck invoice mail for submitted docs with checkbox enabled
		if (frm.doc.docstatus === 1 && frm.doc.custom_send_due_invoice_email === 1) {
			frm.add_custom_button(__('Uncheck Invoice Mail'), function() {
				frappe.call({
					method: 'tcb_sales_invoice_email.api.uncheck_invoice_mail',
					args: {
						invoice_name: frm.doc.name
					},
					callback: function(response) {
						if (response.message && response.message.success) {
							frappe.show_alert({
								message: __('Invoice Mail flag unchecked successfully'),
								indicator: 'green'
							});
							frm.reload_doc();
						} else {
							frappe.msgprint(__(response.message.error || 'Error unchecking invoice mail flag'));
						}
					},
					freezing: true
				});
			}, __('Actions'));
		}
	},
	customer: function(frm) {
		setup_contact_filters(frm);
	}
});

frappe.ui.form.on('Dispatch Email To', {
	contact: function(frm, cdt, cdn) {
		validate_customer_set(frm, cdt, cdn);
	}
});

frappe.ui.form.on('Overdue Invoice Email To', {
	contact: function(frm, cdt, cdn) {
		validate_customer_set(frm, cdt, cdn);
	}
});

// Common function to set up contact filters for both tables
function setup_contact_filters(frm) {
	const tables = ['custom_dispatch_email_to', 'custom_overdue_invoice_email_to'];
	
	tables.forEach(table_field => {
		frm.set_query('contact', table_field, function() {
			if (!frm.doc.customer) {
				frappe.msgprint(__('Please select a Customer first'));
				return {
					filters: {
						name: null // No contacts if customer not set
					}
				};
			}
			return {
				query: 'frappe.contacts.doctype.contact.contact.contact_query',
				filters: {
					link_doctype: 'Customer',
					link_name: frm.doc.customer
				}
			};
		});
	});
}

// Validate that customer is set when contact is selected
function validate_customer_set(frm, cdt, cdn) {
	if (!frm.doc.customer) {
		frappe.model.set_value(cdt, cdn, 'contact', null);
		frappe.throw(__('Please select a Customer before adding contacts'));
		return false;
	}
	return true;
}
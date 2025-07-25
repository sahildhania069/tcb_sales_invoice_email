frappe.ui.form.on('Sales Order', {
	refresh: function(frm) {
		setup_contact_filters(frm);
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
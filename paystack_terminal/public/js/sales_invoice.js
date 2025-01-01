frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        if(frm.doc.docstatus === 1 && frm.doc.status !== 'Paid') {
            frm.add_custom_button(__('Pay with Paystack Terminal'), function() {
                frappe.call({
                    method: 'paystack_terminal.api.process_payment',
                    args: {
                        'amount': frm.doc.grand_total,  // This will be converted in Python
                        'reference': frm.doc.name,      // Added missing reference
                        'patient': frm.doc.patient || null,
                        'invoice': frm.doc.name
                    },
                    callback: function(r) {
                        if(r.message) {
                            frappe.msgprint(__('Payment initiated. Reference: ' + r.message.reference));
                        }
                    }
                });
            });
        }
    }
});
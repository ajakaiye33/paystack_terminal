frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        if(frm.doc.docstatus === 1 && frm.doc.status !== 'Paid') {
            frm.add_custom_button(__('Pay with Paystack Terminal'), function() {
                // Show processing message
                frappe.show_alert({
                    message: __('Initializing terminal payment...'),
                    indicator: 'blue'
                });
                
                // Call payment processing
                paystack_terminal.process_payment({
                    amount: frm.doc.grand_total,
                    reference: frm.doc.name,
                    invoice: frm.doc.name,
                    patient: frm.doc.patient
                }, function(r) {
                    if(r.reference) {
                        frappe.show_alert({
                            message: __('Payment initiated. Please complete payment on terminal. Reference: ' + r.reference),
                            indicator: 'green'
                        });
                    }
                });
            });
        }
    }
});
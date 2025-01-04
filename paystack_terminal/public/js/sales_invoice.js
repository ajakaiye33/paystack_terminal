frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        if(frm.doc.docstatus === 1 && frm.doc.status !== 'Paid') {
            frm.add_custom_button(__('Process Payment with Paystack Terminal'), function() {
                frappe.call({
                    method: 'paystack_terminal.api.process_terminal_payment',
                    args: {
                        invoice: frm.doc.name,
                        amount: frm.doc.grand_total,
                        customer: frm.doc.customer
                    },
                    freeze: true,
                    freeze_message: __('Sending payment request to terminal...'),
                    callback: function(r) {
                        if(r.message && r.message.success) {
                            frappe.show_alert({
                                message: __('Payment request sent to terminal. Please complete payment on the device.'),
                                indicator: 'green'
                            });
                        }
                    }
                });
            });
        }
    }
});
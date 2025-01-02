frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        if(frm.doc.docstatus === 1 && frm.doc.status !== 'Paid') {
            frm.add_custom_button(__('Link Paystack Terminal Payment'), function() {
                let d = new frappe.ui.Dialog({
                    title: 'Link Terminal Payment',
                    fields: [
                        {
                            label: 'Amount',
                            fieldname: 'amount',
                            fieldtype: 'Currency',
                            default: frm.doc.grand_total,
                            read_only: 1
                        },
                        {
                            label: 'Terminal Reference',
                            fieldname: 'terminal_reference',
                            fieldtype: 'Data',
                            reqd: 1,
                            description: 'Enter the reference number from POS receipt'
                        }
                    ],
                    primary_action_label: 'Verify & Link Payment',
                    primary_action(values) {
                        paystack_terminal.verify_payment({
                            amount: values.amount,
                            reference: values.terminal_reference,
                            invoice: frm.doc.name
                        }, function(r) {
                            if(r.success) {
                                frappe.show_alert({
                                    message: __('Payment verified and linked successfully'),
                                    indicator: 'green'
                                });
                                frm.reload_doc();
                            }
                            d.hide();
                        });
                    }
                });
                d.show();
            });
        }
    }
});
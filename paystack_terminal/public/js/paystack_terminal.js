frappe.provide('paystack_terminal');

paystack_terminal.process_payment = function(amount, reference, invoice, callback) {
    frappe.call({
        method: 'paystack_terminal.api.process_payment',
        args: {
            amount: amount,
            reference: reference,
            invoice: invoice
        },
        callback: function(r) {
            if (r.message && r.message.reference) {
                if (callback) callback(r.message);
            }
        }
    });
}
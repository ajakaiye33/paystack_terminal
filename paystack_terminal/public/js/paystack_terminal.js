frappe.provide('paystack_terminal');

paystack_terminal.process_payment = function(amount, callback) {
    frappe.call({
        method: 'paystack_terminal.api.process_payment',
        args: {
            amount: amount
        },
        callback: function(r) {
            if (r.message && r.message.reference) {
                frappe.show_alert({
                    message: __('Payment initiated. Reference: ' + r.message.reference),
                    indicator: 'green'
                });
                if (callback) callback(r.message);
            }
        }
    });
} 
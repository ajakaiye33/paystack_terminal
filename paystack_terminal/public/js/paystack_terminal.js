frappe.provide('paystack_terminal');

paystack_terminal.verify_payment = function(args, callback) {
    frappe.call({
        method: 'paystack_terminal.api.verify_payment',
        args: args,
        freeze: true,
        freeze_message: __('Verifying payment...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                if (callback) callback(r.message);
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Verification Failed'),
                message: __('Could not verify payment. Please check the reference number and try again.'),
                indicator: 'red'
            });
        }
    });
}
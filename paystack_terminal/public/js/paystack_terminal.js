frappe.provide('paystack_terminal');

paystack_terminal.process_payment = function(args, callback) {
    // Check if terminal settings exist
    frappe.call({
        method: 'paystack_terminal.api.process_payment',
        args: args,
        freeze: true,
        freeze_message: __('Connecting to terminal...'),
        callback: function(r) {
            if (r.message) {
                if (callback) callback(r.message);
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Payment Failed'),
                message: __('Failed to process payment. Please check terminal connection and try again.'),
                indicator: 'red'
            });
        }
    });
}
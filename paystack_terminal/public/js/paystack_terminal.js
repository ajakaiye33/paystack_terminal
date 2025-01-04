frappe.provide('paystack_terminal');

paystack_terminal.process_payment = function(args, callback) {
    frappe.call({
        method: 'paystack_terminal.api.process_terminal_payment',
        args: args,
        freeze: true,
        freeze_message: __('Processing payment on terminal...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                if (callback) callback(r.message);
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Payment Failed'),
                message: __('Could not process payment. Please try again.'),
                indicator: 'red'
            });
        }
    });
}
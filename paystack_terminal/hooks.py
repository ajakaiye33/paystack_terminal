app_name = "paystack_terminal"
app_title = "Paystack Terminal"
app_publisher = "Gemutanalytics"
app_description = "Paystack Terminal Integration for ERPNext Healthcare"
app_email = "dev@gemutanalytics.com"
app_license = "MIT"

# DocTypes to be registered
doctype_list = ["Paystack Settings"]

# Module configuration
modules = {
    "Paystack Terminal": {
        "color": "#25c16f",
        "icon": "octicon octicon-credit-card",
        "type": "module",
        "label": "Paystack Terminal",
        "category": "Modules"
    }
}

# include js, css files in header of desk.html
app_include_js = [
    "/assets/paystack_terminal/js/paystack_terminal.js"
]

# Doc Events
doc_events = {
    "Payment Entry": {
        "on_submit": "paystack_terminal.api.update_payment_status"
    }
}

# Custom fields to be created
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "Payment Entry-paystack_reference",
                "Sales Invoice-terminal_reference",
                "Sales Invoice-paystack_status"
            ]]
        ]
    },
    {
        "dt": "DocType",
        "filters": [["name", "in", ["Paystack Settings"]]]
    },
    {
        "dt": "Mode of Payment",
        "filters": [["name", "=", "Paystack Terminal"]]
    }
]

# DocType JS
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice.js"
}

# Webhooks
webhooks = [
    {
        "webhook": "Paystack Terminal Webhook",
        "url": "/api/method/paystack_terminal.api.handle_webhook",
        "request_method": "POST"
    }
]

# Schedule Tasks for reconciliation
scheduler_events = {
    "daily": [
        "paystack_terminal.api.reconcile_pending_payments"
    ]
}
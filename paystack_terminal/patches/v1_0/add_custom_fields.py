import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    """Add custom fields for Paystack Terminal"""
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "terminal_reference",
                "label": "Terminal Reference",
                "fieldtype": "Data",
                "insert_after": "payment_schedule",
                "read_only": 1,
                "no_copy": 1,
                "print_hide": 1
            },
            {
                "fieldname": "paystack_status",
                "label": "Paystack Status",
                "fieldtype": "Data",
                "insert_after": "terminal_reference",
                "read_only": 1,
                "no_copy": 1,
                "print_hide": 1
            }
        ],
        "Customer": [
            {
                "fieldname": "paystack_customer_code",
                "label": "Paystack Customer Code",
                "fieldtype": "Data",
                "insert_after": "customer_details",
                "read_only": 1,
                "no_copy": 1,
                "print_hide": 1
            }
        ],
        "Payment Entry": [
            {
                "fieldname": "paystack_reference",
                "label": "Paystack Reference",
                "fieldtype": "Data",
                "insert_after": "reference_no",
                "read_only": 1,
                "no_copy": 1,
                "print_hide": 1
            }
        ]
    }
    
    create_custom_fields(custom_fields)
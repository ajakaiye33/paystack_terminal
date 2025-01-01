import frappe
import requests
import json
from frappe import _

@frappe.whitelist()
def process_payment(amount, reference, patient=None, invoice=None):
    """Process payment from Paystack Terminal"""
    try:  # Add try-catch for better error handling
        settings = frappe.get_single("Paystack Settings")
        
        if not settings.enabled:
            frappe.throw(_("Paystack Terminal integration is disabled"))
            
        headers = {
            "Authorization": f"Bearer {settings.get_password('secret_key')}",
            "Content-Type": "application/json"
        }
        
        # Convert amount to kobo (Add this line)
        amount_in_kobo = int(float(amount) * 100)
        
        # Create payment request first
        payment_data = {
            "customer": patient if patient else "WALK_IN_CUSTOMER",
            "description": f"Payment for Invoice {invoice}" if invoice else "Direct Payment",
            "line_items": [
                {
                    "name": "Invoice Payment",
                    "amount": str(amount_in_kobo),  # Use converted amount
                    "quantity": 1
                }
            ]
        }
        
        # Add debug logging
        frappe.logger().debug(f"Paystack Request Data: {payment_data}")
        
        create_request_url = "https://api.paystack.co/paymentrequest"
        request_response = requests.post(create_request_url, headers=headers, json=payment_data)
        
        # Log response for debugging
        frappe.logger().debug(f"Paystack Response: {request_response.text}")
        
        if request_response.status_code != 200:
            frappe.throw(_(f"Failed to create payment request: {request_response.text}"))
            
        request_data = request_response.json()["data"]
        
        # Rest of your code remains the same...
        terminal_data = {
            "type": "invoice",
            "action": "process",
            "data": {
                "id": request_data["id"],
                "reference": request_data["offline_reference"]
            }
        }
        
        terminal_url = f"https://api.paystack.co/terminal/{settings.terminal_id}/event"
        terminal_response = requests.post(terminal_url, headers=headers, json=terminal_data)
        
        if terminal_response.status_code != 200:
            frappe.throw(_("Failed to push payment to terminal"))
            
        return {
            "status": "pending",
            "payment_request_id": request_data["id"],
            "reference": request_data["offline_reference"]
        }
        
    except Exception as e:
        frappe.logger().error(f"Paystack Process Error: {str(e)}")
        frappe.throw(_("Failed to create payment request"))
        
def get_or_create_customer(payment_data, patient=None):
    """Get existing customer or create new one from payment data"""
    email = payment_data.get("customer", {}).get("email")
    if not email:
        return None
        
    customer_name = frappe.db.get_value("Customer", {"email_id": email}, "name")
    
    if customer_name:
        return customer_name
        
    # Create new customer
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": payment_data["customer"].get("name", email),
        "customer_type": "Individual",
        "customer_group": frappe.db.get_single_value("Selling Settings", "customer_group"),
        "territory": frappe.db.get_single_value("Selling Settings", "territory"),
        "email_id": email,
        "mobile_no": payment_data["customer"].get("phone", ""),
    })
    
    if patient:
        customer.patient = patient
        
    customer.insert(ignore_permissions=True)
    return customer.name

@frappe.whitelist(allow_guest=True)
def handle_webhook():
    """Handle Paystack webhook notifications"""
    if frappe.request.data:
        data = json.loads(frappe.request.data)
        
        if data.get("event") == "charge.success":
            handle_successful_charge(data["data"])
        elif data.get("event") == "paymentrequest.success":
            handle_successful_payment_request(data["data"])
            
def handle_successful_charge(data):
    """Handle successful charge notification"""
    reference = data.get("reference")
    amount = float(data.get("amount", 0)) / 100  # Convert from kobo to naira
    
    # Create payment entry
    create_payment_entry(reference, amount)
    
def handle_successful_payment_request(data):
    """Handle successful payment request notification"""
    reference = data.get("offline_reference")
    amount = float(data.get("amount", 0)) / 100
    
    # Create payment entry
    create_payment_entry(reference, amount)

def create_payment_entry(reference, amount):
    """Create a Payment Entry for successful Paystack payments"""
    payment = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "posting_date": frappe.utils.today(),
        "company": frappe.defaults.get_user_default("Company"),
        "mode_of_payment": "Paystack Terminal",
        "paid_amount": amount,
        "received_amount": amount,
        "reference_no": reference,
        "reference_date": frappe.utils.today(),
        "party_type": "Customer",
        "party": "Walk-in Customer"  # You might want to update this based on your needs
    })
    
    payment.insert(ignore_permissions=True)
    payment.submit()
    return payment

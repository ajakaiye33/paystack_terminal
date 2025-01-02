import frappe
import requests
import json
from frappe import _

@frappe.whitelist()
def process_payment(amount, reference, invoice=None, patient=None):
    """Process payment from Paystack Terminal"""
    try:
        settings = frappe.get_single("Paystack Settings")
        
        if not settings.enabled:
            frappe.throw(_("Paystack Terminal integration is disabled"))
            
        headers = {
            "Authorization": f"Bearer {settings.get_password('secret_key')}",
            "Content-Type": "application/json"
        }
        
        # Get customer email from Sales Invoice
        customer_email = None
        customer_name = None
        if invoice:
            sales_invoice = frappe.get_doc('Sales Invoice', invoice)
            customer_email = frappe.db.get_value('Customer', sales_invoice.customer, 'email_id')
            customer_name = sales_invoice.customer_name
        
        # Convert amount to kobo for Paystack (amount comes as string)
        amount_in_kobo = int(float(amount))  # Already in kobo from frontend
        
        # First create a payment request
        payment_data = {
            "amount": amount_in_kobo,
            "description": f"Payment for Invoice {invoice}",
            "line_items": [{
                "name": "Invoice Payment",
                "amount": str(amount_in_kobo),
                "quantity": 1
            }],
            "customer": {
                "email": customer_email or "customer@example.com",
                "name": customer_name or patient or "Customer"
            }
        }
        
        # Log the payment request data
        frappe.logger().debug(f"Payment Request Data: {payment_data}")
        
        # Create payment request
        create_request_url = "https://api.paystack.co/paymentrequest"
        request_response = requests.post(create_request_url, headers=headers, json=payment_data)
        
        # Log the complete response
        frappe.logger().debug(f"Payment Request Response: {request_response.text}")
        
        if request_response.status_code != 200:
            frappe.logger().error(f"Payment Request Error: {request_response.text}")
            frappe.throw(_(f"Failed to create payment request: {request_response.text}"))
            
        request_data = request_response.json()["data"]
        
        # Now push to terminal with the received id and reference
        terminal_data = {
            "type": "invoice",
            "action": "process",
            "data": {
                "id": request_data["id"],
                "reference": request_data["offline_reference"]
            }
        }
        
        # Send to physical POS terminal
        terminal_url = f"https://api.paystack.co/terminal/{settings.terminal_id}/event"
        
        # Log what we're sending to terminal
        frappe.logger().debug(f"Terminal Request: {terminal_data}")
        
        terminal_response = requests.post(terminal_url, headers=headers, json=terminal_data)
        
        # Log terminal response
        frappe.logger().debug(f"Terminal Response: {terminal_response.text}")
        
        if terminal_response.status_code != 200:
            frappe.throw(_(f"Failed to push payment to terminal: {terminal_response.text}"))
            
        return {
            "status": "pending",
            "reference": request_data["offline_reference"]
        }
        
    except Exception as e:
        frappe.logger().error(f"Paystack Process Error: {str(e)}")
        frappe.throw(_("Failed to create payment request"))


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
    
    create_payment_entry(reference, amount)

def handle_successful_payment_request(data):
    """Handle successful payment request notification"""
    reference = data.get("offline_reference")
    amount = float(data.get("amount", 0)) / 100  # Convert from kobo to naira
    
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
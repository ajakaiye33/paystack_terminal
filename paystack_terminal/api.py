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
        
        # Convert amount to kobo
        amount_in_kobo = int(float(amount) * 100)
        
        # Get customer email from Sales Invoice
        customer_email = None
        if invoice:
            sales_invoice = frappe.get_doc('Sales Invoice', invoice)
            customer_email = frappe.db.get_value('Customer', sales_invoice.customer, 'email_id')
        
        # Create payment request
        payment_data = {
            "amount": amount_in_kobo,  # Total amount in kobo
            "email": customer_email or "customer@example.com",
            "metadata": {
                "invoice_id": invoice,
                "reference": reference,
                "patient": patient
            }
        }
        
        frappe.logger().debug(f"Paystack Request Data: {payment_data}")
        
        create_request_url = "https://api.paystack.co/transaction/initialize"
        request_response = requests.post(create_request_url, headers=headers, json=payment_data)
        
        if request_response.status_code != 200:
            frappe.logger().error(f"Paystack Error: {request_response.text}")
            frappe.throw(_(f"Failed to create payment request: {request_response.text}"))
            
        response_data = request_response.json()["data"]
        
        # Push to terminal
        terminal_data = {
            "type": "process",
            "action": "process_payment",
            "data": {
                "amount": amount_in_kobo,
                "reference": response_data["reference"],
                "email": customer_email or "customer@example.com"
            }
        }
        
        # Log terminal request
        terminal_url = f"https://api.paystack.co/terminal/{settings.terminal_id}/event"
        frappe.logger().debug(f"Terminal Request URL: {terminal_url}")
        frappe.logger().debug(f"Terminal Request Data: {terminal_data}")
        
        terminal_response = requests.post(terminal_url, headers=headers, json=terminal_data)
        
        # Log terminal response
        frappe.logger().debug(f"Terminal Response Status: {terminal_response.status_code}")
        frappe.logger().debug(f"Terminal Response: {terminal_response.text}")
        
        if terminal_response.status_code != 200:
            frappe.logger().error(f"Terminal Error: {terminal_response.text}")
            frappe.throw(_("Failed to push payment to terminal. Error: {0}").format(terminal_response.text))
            
        return {
            "status": "pending",
            "reference": response_data["reference"]
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
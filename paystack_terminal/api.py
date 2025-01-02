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
            
        # Check terminal status before proceeding
        settings.check_terminal_status()
        if settings.terminal_status != "Connected":
            frappe.throw(_("Terminal is not connected or busy. Status: {0}").format(settings.terminal_status))
            
        headers = {
            "Authorization": f"Bearer {settings.get_password('secret_key')}",
            "Content-Type": "application/json"
        }
        
        # Convert amount to kobo for Paystack
        amount_in_kobo = int(float(amount) * 100)
        
        # Direct terminal payment request
        terminal_data = {
            "type": "pos_payment",
            "action": "process",
            "data": {
                "amount": amount_in_kobo,
                "description": f"Payment for Invoice {invoice}" if invoice else "Direct Payment",
                "metadata": {
                    "invoice_id": invoice,
                    "reference": reference,
                    "patient": patient
                }
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
            
        response_data = terminal_response.json()["data"]
            
        return {
            "status": "pending",
            "reference": response_data.get("reference") or reference
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
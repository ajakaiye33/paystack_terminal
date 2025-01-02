import frappe
import requests
import json
from frappe import _

@frappe.whitelist()
def verify_payment(amount, reference, invoice):
    """Verify and link Paystack terminal payment"""
    try:
        settings = frappe.get_single("Paystack Settings")
        
        if not settings.enabled:
            frappe.throw(_("Paystack Terminal integration is disabled"))
            
        headers = {
            "Authorization": f"Bearer {settings.get_password('secret_key')}",
            "Content-Type": "application/json"
        }
        
        # Get invoice and customer details
        sales_invoice = frappe.get_doc("Sales Invoice", invoice)
        customer = frappe.get_doc("Customer", sales_invoice.customer)
        
        # Prepare metadata
        metadata = {
            "invoice_no": invoice,
            "customer_name": customer.customer_name,
            "customer_email": customer.email_id or "customer@example.com",
            "patient": sales_invoice.patient if hasattr(sales_invoice, 'patient') else None,
            "company": sales_invoice.company,
            "source": "ERPNext Healthcare"
        }
        
        # Update transaction with metadata
        update_url = f"https://api.paystack.co/transaction/{reference}"
        update_data = {"metadata": metadata}
        
        requests.put(update_url, headers=headers, json=update_data)
        
        # Verify transaction with Paystack
        verify_url = f"https://api.paystack.co/transaction/verify/{reference}"
        verify_response = requests.get(verify_url, headers=headers)
        
        if verify_response.status_code != 200:
            frappe.throw(_("Could not verify payment"))
            
        response_data = verify_response.json()["data"]
        
        if response_data["status"] != "success":
            frappe.throw(_("Payment was not successful"))
            
        return create_payment_entry(reference, amount, invoice, metadata)
        
    except Exception as e:
        frappe.logger().error(f"Paystack Payment Verification Error: {str(e)}")
        frappe.throw(_("Failed to verify payment"))

@frappe.whitelist(allow_guest=True)
def handle_webhook():
    """Handle Paystack webhook notifications"""
    if frappe.request.data:
        try:
            data = json.loads(frappe.request.data)
            
            # Log webhook data for debugging
            frappe.logger().debug(f"Paystack Webhook Data: {data}")
            
            if data.get("event") == "charge.success":
                handle_successful_charge(data["data"])
            elif data.get("event") == "paymentrequest.success":
                handle_successful_payment_request(data["data"])
                
            return {"status": "success"}
            
        except Exception as e:
            frappe.logger().error(f"Webhook Processing Error: {str(e)}")
            return {"status": "error", "message": str(e)}

def handle_successful_charge(data):
    """Handle successful charge notification"""
    try:
        reference = data.get("reference")
        amount = float(data.get("amount", 0)) / 100  # Convert from kobo to naira
        metadata = data.get("metadata", {})
        
        # Check if payment entry already exists
        if not frappe.db.exists("Payment Entry", {"reference_no": reference}):
            create_payment_entry(reference, amount, metadata.get("invoice_no"), metadata)
            
    except Exception as e:
        frappe.logger().error(f"Charge Processing Error: {str(e)}")

def handle_successful_payment_request(data):
    """Handle successful payment request notification"""
    try:
        reference = data.get("offline_reference")
        amount = float(data.get("amount", 0)) / 100  # Convert from kobo to naira
        metadata = data.get("metadata", {})
        
        # Check if payment entry already exists
        if not frappe.db.exists("Payment Entry", {"reference_no": reference}):
            create_payment_entry(reference, amount, metadata.get("invoice_no"), metadata)
            
    except Exception as e:
        frappe.logger().error(f"Payment Request Processing Error: {str(e)}")

def create_payment_entry(reference, amount, invoice=None, metadata=None):
    """Create a Payment Entry for successful Paystack payments"""
    try:
        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": frappe.utils.today(),
            "company": metadata.get("company") if metadata else frappe.defaults.get_user_default("Company"),
            "mode_of_payment": "Paystack Terminal",
            "paid_amount": amount,
            "received_amount": amount,
            "reference_no": reference,
            "reference_date": frappe.utils.today(),
            "party_type": "Customer",
            "remarks": f"Patient: {metadata.get('patient')}" if metadata and metadata.get('patient') else None
        })
        
        # If invoice is provided, link it
        if invoice:
            payment_entry.party = frappe.get_value("Sales Invoice", invoice, "customer")
            payment_entry.append("references", {
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice,
                "allocated_amount": amount
            })
        else:
            payment_entry.party = "Walk-in Customer"
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        return {
            "success": True,
            "payment_entry": payment_entry.name
        }
        
    except Exception as e:
        frappe.logger().error(f"Payment Entry Creation Error: {str(e)}")
        frappe.throw(_("Failed to create payment entry"))
import frappe
import requests
import json
from frappe import _

@frappe.whitelist()
def verify_payment(amount, reference, invoice):
    """Verify and link Paystack terminal payment"""
    try:
        # Convert amount to float
        amount = float(amount)
        
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
        
        # Create/Update customer in Paystack
        name_parts = customer.customer_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        customer_data = {
            "email": customer.email_id or f"customer_{customer.name.lower()}@example.com",
            "first_name": first_name,
            "last_name": last_name,
            "phone": customer.mobile_no,
            "metadata": {
                "erp_customer_id": customer.name,
                "patient": sales_invoice.patient if hasattr(sales_invoice, 'patient') else None
            }
        }
        
        # Check if customer exists in Paystack
        if not customer.get("paystack_customer_code"):
            # Create new customer
            customer_response = requests.post(
                "https://api.paystack.co/customer",
                headers=headers,
                json=customer_data
            )
            
            if customer_response.status_code == 200:
                customer_result = customer_response.json()
                if customer_result.get("status"):
                    customer.db_set(
                        "paystack_customer_code",
                        customer_result["data"]["customer_code"],
                        update_modified=False
                    )
        
        # Prepare metadata
        metadata = {
            "invoice_no": invoice,
            "customer_name": customer.customer_name,
            "customer_email": customer.email_id,
            "patient": sales_invoice.patient if hasattr(sales_invoice, 'patient') else None,
            "company": sales_invoice.company,
            "source": "ERPNext Healthcare"
        }
        
        # Update transaction with metadata and customer
        update_url = f"https://api.paystack.co/transaction/{reference}"
        update_data = {
            "metadata": metadata,
            "customer": customer.get("paystack_customer_code")
        }
        
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
    try:
        # Get the signature from headers
        signature = frappe.get_request_header('x-paystack-signature')
        
        if not signature:
            frappe.logger().warning("No Paystack signature in webhook")
            return {'status': 'error', 'message': 'No signature'}
            
        # Get request data
        if frappe.request.data:
            data = json.loads(frappe.request.data)
            
            # Log webhook data for debugging
            frappe.logger().debug(f"Paystack Webhook Data: {data}")
            
            # Process based on event type
            event = data.get('event')
            if event == "charge.success":
                # Process immediately but don't wait
                frappe.enqueue(
                    'paystack_terminal.api.handle_successful_charge',
                    data=data.get('data'),
                    queue='short'
                )
            elif event == "paymentrequest.success":
                frappe.enqueue(
                    'paystack_terminal.api.handle_successful_payment_request',
                    data=data.get('data'),
                    queue='short'
                )
                
            # Return 200 OK immediately
            return {'status': 'success'}
            
    except Exception as e:
        frappe.logger().error(f"Webhook Processing Error: {str(e)}")
        # Still return 200 OK to prevent retries
        return {'status': 'success'}

def handle_successful_charge(data):
    """Handle successful charge notification"""
    try:
        if not isinstance(data, dict):
            frappe.logger().error(f"Invalid data type received: {type(data)}")
            return
            
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
        # Ensure amount is float
        amount = float(amount) if isinstance(amount, str) else amount
        
        # Ensure Mode of Payment exists
        if not frappe.db.exists("Mode of Payment", "Paystack Terminal"):
            frappe.get_doc({
                "doctype": "Mode of Payment",
                "mode_of_payment": "Paystack Terminal",
                "type": "Bank",
                "enabled": 1
            }).insert(ignore_permissions=True)
        
        # Get company currency
        company = metadata.get("company") if metadata else frappe.defaults.get_user_default("Company")
        company_currency = frappe.get_value("Company", company, "default_currency")
        
        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": frappe.utils.today(),
            "company": company,
            "mode_of_payment": "Paystack Terminal",
            "paid_amount": amount,
            "received_amount": amount,
            "target_exchange_rate": 1,
            "paid_to_account_currency": company_currency,
            "paid_from_account_currency": company_currency,
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
        
        # Set accounts
        payment_entry.paid_to = frappe.get_value("Mode of Payment Account",
            {"parent": "Paystack Terminal", "company": company}, "default_account")
            
        if not payment_entry.paid_to:
            payment_entry.paid_to = frappe.get_value("Company", company, "default_bank_account")
            
        if not payment_entry.paid_to:
            frappe.throw(_("Please set default bank account in Company or Mode of Payment"))
            
        payment_entry.paid_from = frappe.get_value("Company", company, "default_receivable_account")
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        return {
            "success": True,
            "payment_entry": payment_entry.name
        }
        
    except Exception as e:
        frappe.logger().error(f"Payment Entry Creation Error: {str(e)}")
        frappe.throw(_("Failed to create payment entry"))


def reconcile_pending_payments():
    """Daily reconciliation of pending payments"""
    try:
        settings = frappe.get_single("Paystack Settings")
        
        if not settings.enabled:
            return
            
        headers = {
            "Authorization": f"Bearer {settings.get_password('secret_key')}",
            "Content-Type": "application/json"
        }
        
        # Get pending payments from the last 24 hours
        yesterday = frappe.utils.add_days(frappe.utils.nowdate(), -1)
        
        # Get all Sales Invoices with terminal_reference but no payment entry
        pending_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "terminal_reference": ["!=", ""],
                "status": "Unpaid",
                "creation": [">=", yesterday]
            },
            fields=["name", "terminal_reference", "grand_total"]
        )
        
        for invoice in pending_invoices:
            try:
                # Verify payment status with Paystack
                verify_url = f"https://api.paystack.co/transaction/verify/{invoice.terminal_reference}"
                verify_response = requests.get(verify_url, headers=headers)
                
                if verify_response.status_code == 200:
                    response_data = verify_response.json()["data"]
                    
                    if response_data["status"] == "success":
                        # Create payment entry if payment was successful
                        if not frappe.db.exists("Payment Entry", {"reference_no": invoice.terminal_reference}):
                            create_payment_entry(
                                reference=invoice.terminal_reference,
                                amount=invoice.grand_total,
                                invoice=invoice.name
                            )
                            
                        frappe.logger().info(f"Reconciled payment for invoice {invoice.name}")
                        
            except Exception as e:
                frappe.logger().error(f"Error reconciling invoice {invoice.name}: {str(e)}")
                continue
                
    except Exception as e:
        frappe.logger().error(f"Reconciliation Error: {str(e)}")


def update_payment_status(doc, method):
    """Update payment status in Sales Invoice when Payment Entry is submitted"""
    try:
        # Only process if it's a Paystack Terminal payment
        if doc.mode_of_payment != "Paystack Terminal":
            return
            
        # Get linked Sales Invoice
        for ref in doc.references:
            if ref.reference_doctype == "Sales Invoice":
                sales_invoice = frappe.get_doc("Sales Invoice", ref.reference_name)
                
                # Update custom field
                sales_invoice.db_set("paystack_status", "Paid")
                sales_invoice.db_set("terminal_reference", doc.reference_no)
                
                # Add comment to Sales Invoice
                frappe.get_doc({
                    "doctype": "Comment",
                    "comment_type": "Info",
                    "reference_doctype": "Sales Invoice",
                    "reference_name": sales_invoice.name,
                    "content": f"Payment processed via Paystack Terminal (Reference: {doc.reference_no})"
                }).insert(ignore_permissions=True)
                
                frappe.db.commit()
                
    except Exception as e:
        frappe.logger().error(f"Payment Status Update Error: {str(e)}")
        # Don't throw error to avoid interrupting payment entry submission
        pass
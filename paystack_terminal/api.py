"""
Author:Hedgar Ajakaiye
Date: January 02, 2025
Description: A custom module for integrating Paystack Terminal with ERPNext
"""


import frappe
import requests
import json
from frappe import _

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
            
            # Ensure data is a dictionary
            if not isinstance(data, dict):
                frappe.logger().error("Invalid webhook data format")
                return {'status': 'error', 'message': 'Invalid data format'}
            
            # Process based on event type
            event = data.get('event')
            webhook_data = data.get('data', {})
            
            # Extract references for deduplication
            reference = None
            offline_reference = None
            
            if event == "charge.success":
                reference = webhook_data.get("reference")
            elif event == "paymentrequest.success":
                offline_reference = webhook_data.get("offline_reference")
            
            # Check for existing payment entries with either reference
            if reference and frappe.db.exists("Payment Entry", {"reference_no": reference}):
                frappe.logger().info(f"Payment already processed for reference: {reference}")
                return {'status': 'success'}
                
            if offline_reference and frappe.db.exists("Payment Entry", {"reference_no": offline_reference}):
                frappe.logger().info(f"Payment already processed for offline_reference: {offline_reference}")
                return {'status': 'success'}
            
            # Process the event
            if event == "charge.success" and reference:
                frappe.enqueue(
                    'paystack_terminal.api.handle_successful_charge',
                    data=webhook_data,
                    queue='short'
                )
            elif event == "paymentrequest.success" and offline_reference:
                frappe.enqueue(
                    'paystack_terminal.api.handle_successful_payment_request',
                    data=webhook_data,
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
        
        # Check if payment entry already exists with either reference or offline_reference
        if frappe.db.exists("Payment Entry", {"reference_no": reference}):
            frappe.logger().info(f"Payment already processed for reference: {reference}")
            return
            
        # Also check if there's an entry with offline_reference from metadata
        offline_reference = metadata.get("offline_reference")
        if offline_reference and frappe.db.exists("Payment Entry", {"reference_no": offline_reference}):
            frappe.logger().info(f"Payment already processed for offline_reference: {offline_reference}")
            return
            
        create_payment_entry(reference, amount, metadata.get("invoice_no"), metadata)
            
    except Exception as e:
        frappe.logger().error(f"Charge Processing Error: {str(e)}")

def handle_successful_payment_request(data):
    """Handle successful payment request notification"""
    try:
        offline_reference = data.get("offline_reference")
        amount = float(data.get("amount", 0)) / 100  # Convert from kobo to naira
        metadata = data.get("metadata", {})
        
        # Check if payment entry already exists with offline_reference
        if frappe.db.exists("Payment Entry", {"reference_no": offline_reference}):
            frappe.logger().info(f"Payment already processed for offline_reference: {offline_reference}")
            return
            
        # Also check if there's an entry with the transaction reference
        transaction_reference = data.get("reference") or metadata.get("reference")
        if transaction_reference and frappe.db.exists("Payment Entry", {"reference_no": transaction_reference}):
            frappe.logger().info(f"Payment already processed for transaction reference: {transaction_reference}")
            return
            
        create_payment_entry(offline_reference, amount, metadata.get("invoice_no"), metadata)
            
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

@frappe.whitelist()
def process_terminal_payment(invoice, amount, customer):
    """Process payment through Paystack Terminal"""
    try:
        # Convert amount to float
        amount = float(amount)
        
        settings = frappe.get_single("Paystack Settings")
        if not settings.enabled:
            frappe.throw(_("Paystack Terminal integration is disabled"))
            
        # Check terminal status before proceeding
        headers = {
            "Authorization": f"Bearer {settings.get_password('secret_key')}",
            "Content-Type": "application/json"
        }
        
        # Check if terminal is online and available
        terminal_url = f"https://api.paystack.co/terminal/{settings.terminal_id}/presence"
        terminal_response = requests.get(terminal_url, headers=headers)
        
        if terminal_response.status_code != 200:
            frappe.throw(_("Could not check terminal status"))
            
        terminal_data = terminal_response.json().get("data", {})
        if not (terminal_data.get("online") and terminal_data.get("available")):
            frappe.throw(_("Terminal is not available for payment processing"))
            
        # Get invoice, customer, and patient details
        sales_invoice = frappe.get_doc("Sales Invoice", invoice)
        customer = frappe.get_doc("Customer", sales_invoice.customer)
        
        # Get patient details if available
        patient = None
        if hasattr(sales_invoice, 'patient') and sales_invoice.patient:
            patient = frappe.get_doc("Patient", sales_invoice.patient)
        
        # Prepare customer data using patient info if available
        customer_data = {
            "email": (patient.email if patient else customer.email_id) or f"customer_{customer.name.lower()}@example.com",
            "first_name": patient.first_name if patient else customer.customer_name,
            "last_name": patient.last_name if patient else "",
            "phone": patient.mobile if patient else customer.mobile_no,
            "metadata": {
                "erp_customer_id": customer.name,
                "patient_id": patient.name if patient else None
            }
        }
        
        # Check if customer exists in Paystack
        paystack_customer_code = customer.get("paystack_customer_code")
        if not paystack_customer_code:
            # Create new customer in Paystack
            customer_response = requests.post(
                "https://api.paystack.co/customer",
                headers=headers,
                json=customer_data
            )
            
            if customer_response.status_code == 200:
                customer_result = customer_response.json()
                if customer_result.get("status"):
                    paystack_customer_code = customer_result["data"]["customer_code"]
                    customer.db_set(
                        "paystack_customer_code",
                        customer_result["data"]["customer_code"],
                        update_modified=False
                    )
            else:
                frappe.logger().error(f"Failed to create customer in Paystack: {customer_response.text}")
                frappe.throw(_("Failed to create customer in Paystack"))
        
        # Create payment request
        payment_data = {
            "customer": paystack_customer_code,
            "amount": str(float(amount) * 100),  # Convert to kobo
            "metadata": {
                "invoice_no": invoice,
                "customer_name": customer.customer_name,
                "customer_email": customer.email_id,
                "patient": sales_invoice.patient if hasattr(sales_invoice, 'patient') else None,
                "company": sales_invoice.company,
                "source": "ERPNext Healthcare"
            }
        }
        
        create_request_url = "https://api.paystack.co/paymentrequest"
        request_response = requests.post(create_request_url, headers=headers, json=payment_data)
        
        if request_response.status_code != 200:
            frappe.throw(_("Failed to create payment request"))
            
        request_data = request_response.json()["data"]
        
        # Push to terminal
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
            
        # Store reference in invoice
        frappe.db.set_value("Sales Invoice", invoice, {
            "terminal_reference": request_data["offline_reference"],
            "paystack_status": "Pending"
        })
        
        return {
            "success": True,
            "message": "Payment request sent to terminal",
            "reference": request_data["offline_reference"]
        }
        
    except Exception as e:
        frappe.logger().error(f"Terminal Payment Error: {str(e)}")
        frappe.throw(_("Failed to process terminal payment"))

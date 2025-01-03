import frappe
from frappe import _
from frappe.model.document import Document
import requests

class PaystackSettings(Document):
    def validate(self):
        if self.enabled:
            if not self.secret_key:
                frappe.throw(_("Secret Key is required"))
            if not self.terminal_id:
                frappe.throw(_("Terminal ID is required"))
            if not self.public_key:
                frappe.throw(_("Public Key is required"))
            
            # Check terminal status
            self.check_terminal_status()
            
            # Set webhook URL
            self.webhook_url = f"{frappe.utils.get_url()}/api/method/paystack_terminal.api.handle_webhook"
    
    def check_terminal_status(self):
        """Check if terminal is available"""
        try:
            headers = {
                "Authorization": f"Bearer {self.get_password('secret_key')}",
                "Content-Type": "application/json"
            }
            
            # Check terminal presence instead of just status
            terminal_url = f"https://api.paystack.co/terminal/{self.terminal_id}/presence"
            response = requests.get(terminal_url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()["data"]
                if data.get("online") and data.get("available"):
                    self.terminal_status = "Connected"
                else:
                    self.terminal_status = "Busy"
                    frappe.msgprint(_("Terminal is online but busy processing another payment"))
            else:
                self.terminal_status = "Disconnected"
                frappe.msgprint(_("Could not connect to Paystack Terminal"))
        except Exception as e:
            self.terminal_status = "Error"
            frappe.log_error(str(e), "Paystack Terminal Status Check Failed")
            frappe.msgprint(_("Error connecting to Paystack Terminal"))

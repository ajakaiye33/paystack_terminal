"""
Configuration for docs
"""

source_link = "https://github.com/[org_name]/paystack_terminal"
headline = "Paystack Terminal Integration"
sub_heading = "Process payments via Paystack Terminal"

def get_context(context):
	context.brand_html = "Paystack Terminal"
	context.app_title = "Paystack Terminal"
	context.app_publisher = "[Your Company]"
	context.app_description = "Integrate Paystack Terminal with ERPNext"
	context.app_email = "your.email@example.com"
	context.app_license = "MIT"  # or your preferred license

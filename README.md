# Paystack Terminal Integration for ERPNext

A Frappe app that integrates Paystack Terminal with ERPNext for seamless in-person payments.

## Features

- Process payments directly through Paystack Terminal within ERPNext
- Automatic payment entry creation and invoice linking
- Real-time payment verification
- Secure API key management
- Terminal status monitoring

## Installation

1. Install the app using bench:
```bash
bench get-app paystack_terminal https://github.com/your-repo/paystack_terminal
bench --site your-site.com install-app paystack_terminal
```

2. After installation, configure your Paystack settings:
   - Go to Paystack Settings
   - Enable Paystack Terminal
   - Enter your Secret Key, Public Key, and Terminal ID

## Usage

1. Create a Sales Invoice as usual
2. After submitting the invoice, click on "Pay with Paystack Terminal"
3. Enter the reference number shown on your Paystack Terminal
4. Confirm the payment
5. The system will automatically:
   - Verify the payment
   - Create a Payment Entry
   - Link it to your Sales Invoice
   - Update the payment status

## Configuration

### Required Settings
- Paystack Secret Key
- Paystack Public Key
- Terminal ID

These can be configured in the Paystack Settings page.

## Support

For support and issues, please create an issue in the GitHub repository or contact support@gemutanalytics.com

## License

MIT License. See license.txt for more information.

## Contributors

- GemutAnalytics (dev@gemutanalytics.com)

## Version History

- 1.0.0: Initial release
  - Basic payment processing
  - Terminal integration
  - Payment verification
  - Invoice linking

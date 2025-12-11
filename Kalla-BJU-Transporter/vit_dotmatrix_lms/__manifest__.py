{
	"name": "Direct Print to Dot Matrix Printer",
	'summary': 'This is modul is used to print PO, Picking, SO, Customer Invoice directly to dot matrix printers',
	"description": """
Version
======================================================================
1.6 product , uom no data

Manage
======================================================================

* this is modul is used to print PO, Picking, SO, Invoice directly to dot matrix printer
* no special hardware needed
* using printer proxy script (apache/ngnix+php)
* add printer_data field on account.invoice, sale.order, purchase.order
* printer template data from mail.template named "Dot Matrix *"

Windows Installation
======================================================================
* install this addon on the database
* download the print.php script from this <a href="https://drive.google.com/open?id=17aHbikQMjYq7A6AhWoUHsNF4fLomTy4E">link</a> and install it to your local client thats connected to the printer directly.
* install apache+php or nginx+php on the local computer and copy print.php script to the htdocs
* follow the INSTALL.TXT instruction on how to install the script
* print Invoice, SO, PO directly to local dotmatrix printer

""",
	"version": "1.6",
	"depends": [
		"sale",
		"jst_demo_kalla_bju_transporter",
		"mail"
	],
	"author": "Akhmad D. Sembiring [vitraining.com]",
	"category": "Utilities",
	'website': 'http://www.vitraining.com',
	'images': ['static/description/images/main_screenshot.jpg'],
	'price': '60',
	'currency': 'USD',
	'license': 'OPL-1',
	'data': [
		"view/so.xml",
		# "data/parameters.xml",
		"data/templates.xml",
		"data/default.xml",
	],
    'assets': {
        'web.assets_backend': [
            # 'vit_dotmatrix_lms/static/src/js/print_button.js',
            'vit_dotmatrix_lms/static/src/xml/print_button.xml',
        ],
    },
	
	"installable": True,
	"auto_install": False,
    "application": True,
}
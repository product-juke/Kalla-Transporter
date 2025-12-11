from odoo import http
from odoo.http import request
import json
import logging
import base64
import hashlib
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import secrets

_logger = logging.getLogger(__name__)


class OracleSyncController(http.Controller):
    # **HIGHLIGHTED: Secure token constants**
    PLAIN_TOKEN = "JST2025"
    # Salt untuk konsistensi enkripsi (dalam production, simpan di environment variable)
    ENCRYPTION_SALT = b'oracle_sync_salt_2025_secure'

    def _generate_encryption_key(self):
        """
        Generate encryption key dari salt dan secret phrase
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.ENCRYPTION_SALT,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(b"JST2025_ORACLE_SECURE_KEY"))
        return key

    def _encrypt_token(self, token):
        """
        Encrypt token menggunakan Fernet (AES 128)
        """
        try:
            key = self._generate_encryption_key()
            f = Fernet(key)
            encrypted_token = f.encrypt(token.encode())
            # Encode ke base64 untuk transport yang aman
            return base64.b64encode(encrypted_token).decode()
        except Exception as e:
            _logger.error(f"Error encrypting token: {str(e)}")
            return None

    def _decrypt_token(self, encrypted_token):
        """
        Decrypt token dan return plain text
        """
        try:
            key = self._generate_encryption_key()
            f = Fernet(key)
            # Decode dari base64
            encrypted_data = base64.b64decode(encrypted_token.encode())
            decrypted_token = f.decrypt(encrypted_data)
            return decrypted_token.decode()
        except Exception as e:
            _logger.error(f"Error decrypting token: {str(e)}")
            return None

    def _validate_token(self):
        """
        **HIGHLIGHTED: Enhanced token validation with decryption**
        Validate API token from Authorization header dengan dekripsi
        """
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header:
            return False, "Missing Authorization header"

        if not auth_header.startswith('Bearer '):
            return False, "Invalid Authorization format. Use: Bearer <encrypted_token>"

        encrypted_token = auth_header.replace('Bearer ', '')

        # Decrypt token
        decrypted_token = self._decrypt_token(encrypted_token)

        if not decrypted_token:
            return False, "Invalid encrypted token format"

        # Validasi apakah hasil dekripsi sama dengan PLAIN_TOKEN
        if decrypted_token != self.PLAIN_TOKEN:
            return False, "Invalid token"

        return True, "Valid token"

    def _get_encrypted_token_for_docs(self):
        """
        Generate encrypted token untuk dokumentasi
        """
        return self._encrypt_token(self.PLAIN_TOKEN)

    @http.route('/api/docs', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def swagger_docs(self, **kwargs):
        """
        Endpoint untuk menampilkan dokumentasi Swagger UI
        """
        swagger_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Oracle Sync API Documentation</title>
            <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@3.25.0/swagger-ui.css" />
            <style>
                html {
                    box-sizing: border-box;
                    overflow: -moz-scrollbars-vertical;
                    overflow-y: scroll;
                }
                *, *:before, *:after {
                    box-sizing: inherit;
                }
                body {
                    margin:0;
                    background: #fafafa;
                }
            </style>
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@3.25.0/swagger-ui-bundle.js"></script>
            <script src="https://unpkg.com/swagger-ui-dist@3.25.0/swagger-ui-standalone-preset.js"></script>
            <script>
                window.onload = function() {
                    const ui = SwaggerUIBundle({
                        url: '/api/openapi.json',
                        dom_id: '#swagger-ui',
                        deepLinking: true,
                        presets: [
                            SwaggerUIBundle.presets.apis,
                            SwaggerUIStandalonePreset
                        ],
                        plugins: [
                            SwaggerUIBundle.plugins.DownloadUrl
                        ],
                        layout: "StandaloneLayout"
                    });
                };
            </script>
        </body>
        </html>
        """
        return request.make_response(
            swagger_html,
            headers=[('Content-Type', 'text/html')],
            status=200
        )

    @http.route('/api/openapi.json', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def openapi_spec(self, **kwargs):
        """
        OpenAPI/Swagger specification untuk API
        """
        # Generate encrypted token untuk contoh di dokumentasi
        sample_encrypted_token = 'SAMPLE_ENCRYPTED_TOKEN'

        openapi_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Oracle Sync API",
                "description": f"API untuk sinkronisasi data dengan Oracle system. <br /><br /> <b>Account Move</b>: model untuk menampung data invoice dan vendor bill. <br /> <b>Res Partner</b>: model untuk menampung data Customer dan Vendor. <br /><br /> <b>Authentication:</b> All endpoints require Bearer token authentication with ENCRYPTED token. <br/><br/> <b>Sample Encrypted Token:</b> <code>{sample_encrypted_token}</code>",
                "version": "1.0.0",
                # "contact": {
                #     "name": "API Support",
                #     "email": "support@company.com"
                # }
            },
            # **HIGHLIGHTED: Added security schemes for token authentication**
            "components": {
                "securitySchemes": {
                    "BearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "ENCRYPTED",
                        "description": f"Enter ENCRYPTED token. Sample: {sample_encrypted_token}"
                    }
                },
                "schemas": {
                    "AccountMoveFeedback": {
                        "type": "object",
                        "required": ["invoice_number", "invoice_date", "flag", "message", "status_code"],
                        "properties": {
                            "invoice_number": {
                                "type": "string",
                                "description": "Nomor invoice",
                                "example": "INV/2024/0001"
                            },
                            "invoice_date": {
                                "type": "string",
                                "format": "date",
                                "description": "Tanggal invoice",
                                "example": "2024-01-15"
                            },
                            "flag": {
                                "type": "string",
                                "enum": ["success", "failed"],
                                "description": "Status flag dari Oracle"
                            },
                            "message": {
                                "type": "string",
                                "description": "Pesan dari Oracle system",
                                "example": "Invoice synced successfully"
                            },
                            "status_code": {
                                "type": "integer",
                                "description": "Status code dari Oracle",
                                "example": 200
                            }
                        }
                    },
                    "CustomerFeedback": {
                        "type": "object",
                        "required": ["vat_or_ktp", "create_date", "flag", "message", "status_code"],
                        "properties": {
                            "vat_or_ktp": {
                                "type": "string",
                                "description": "VAT or KTP number customer",
                                "example": "123456789012345"
                            },
                            "create_date": {
                                "type": "string",
                                "format": "date",
                                "description": "Tanggal pembuatan customer (YYYY-MM-DD)",
                                "example": "2024-01-15"
                            },
                            "flag": {
                                "type": "string",
                                "enum": ["success", "failed"],
                                "description": "Status flag dari Oracle"
                            },
                            "message": {
                                "type": "string",
                                "description": "Pesan dari Oracle system",
                                "example": "Partner synced successfully"
                            },
                            "status_code": {
                                "type": "integer",
                                "description": "Status code dari Oracle",
                                "example": 200
                            }
                        }
                    },
                    "SupplierFeedback": {
                        "type": "object",
                        "required": ["supplier_site", "name", "flag", "message", "status_code"],
                        "properties": {
                            "supplier_site": {
                                "type": "string",
                                "description": "Supplier site dari supplier",
                                "example": "123456789012345"
                            },
                            "name": {
                                "type": "string",
                                "description": "Nama dari supplier",
                                "example": "2024-01-15"
                            },
                            "flag": {
                                "type": "string",
                                "enum": ["success", "failed"],
                                "description": "Status flag dari Oracle"
                            },
                            "message": {
                                "type": "string",
                                "description": "Pesan dari Oracle system",
                                "example": "Partner synced successfully"
                            },
                            "status_code": {
                                "type": "integer",
                                "description": "Status code dari Oracle",
                                "example": 200
                            }
                        }
                    },
                    "AccountMoveSuccessResponse": {
                        "type": "object",
                        "properties": {
                            "success": {
                                "type": "boolean",
                                "example": True
                            },
                            "message": {
                                "type": "string",
                                "example": "Sync feedback created successfully"
                            },
                            "data": {
                                "type": "object",
                                "properties": {
                                    "invoice_id": {
                                        "type": "integer",
                                        "example": 1
                                    },
                                    "invoice_number": {
                                        "type": "string",
                                        "example": "INV/2024/0001"
                                    },
                                    "sync_log_id": {
                                        "type": "integer",
                                        "example": 1
                                    },
                                    "status_code": {
                                        "type": "integer",
                                        "example": 200
                                    }
                                }
                            }
                        }
                    },
                    "CustomerSuccessResponse": {
                        "type": "object",
                        "properties": {
                            "success": {
                                "type": "boolean",
                                "example": True
                            },
                            "message": {
                                "type": "string",
                                "example": "Sync feedback created successfully"
                            },
                            "data": {
                                "type": "object",
                                "properties": {
                                    "vat_or_ktp": {
                                        "type": "string",
                                        "example": "123456789012345"
                                    },
                                    "create_date": {
                                        "type": "string",
                                        "example": "2024-01-15 10:30:45"
                                    },
                                    "sync_log_id": {
                                        "type": "integer",
                                        "example": 1
                                    },
                                    "status_code": {
                                        "type": "integer",
                                        "example": 200
                                    }
                                }
                            }
                        }
                    },
                    "SupplierSuccessResponse": {
                        "type": "object",
                        "properties": {
                            "success": {
                                "type": "boolean",
                                "example": True
                            },
                            "message": {
                                "type": "string",
                                "example": "Sync feedback created successfully"
                            },
                            "data": {
                                "type": "object",
                                "properties": {
                                    "supplier_site": {
                                        "type": "string",
                                        "example": "john_doe"
                                    },
                                    "name": {
                                        "type": "string",
                                        "example": "John Doe"
                                    },
                                    "sync_log_id": {
                                        "type": "integer",
                                        "example": 1
                                    },
                                    "status_code": {
                                        "type": "integer",
                                        "example": 200
                                    }
                                }
                            }
                        }
                    },
                    "ErrorResponse": {
                        "type": "object",
                        "properties": {
                            "success": {
                                "type": "boolean",
                                "example": False
                            },
                            "message": {
                                "type": "string",
                                "example": "Error message description"
                            },
                            "status_code": {
                                "type": "integer",
                                "example": 400
                            }
                        }
                    },
                    # **HIGHLIGHTED: Added unauthorized response schema**
                    "UnauthorizedResponse": {
                        "type": "object",
                        "properties": {
                            "success": {
                                "type": "boolean",
                                "example": False
                            },
                            "message": {
                                "type": "string",
                                "example": "Invalid token"
                            },
                            "status_code": {
                                "type": "integer",
                                "example": 401
                            }
                        }
                    }
                }
            },
            # **HIGHLIGHTED: Added global security requirement**
            "security": [
                {
                    "BearerAuth": []
                }
            ],
            "servers": [
                {
                    "url": request.httprequest.host_url.rstrip('/'),
                    "description": "Current server"
                }
            ],
            "paths": {
                "/api/oracle/sync/feedback/account-move": {
                    "post": {
                        "tags": ["Account Move"],
                        "summary": "Sync feedback untuk Invoice & Vendor Bill",
                        "description": "Endpoint untuk menerima feedback dari Oracle system untuk Invoice dan Vendor Bill",
                        # **HIGHLIGHTED: Added security requirement for this endpoint**
                        "security": [
                            {
                                "BearerAuth": []
                            }
                        ],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/AccountMoveFeedback"
                                    },
                                    "example": {
                                        "invoice_number": "INV/2024/0001",
                                        "invoice_date": "2024-01-15",
                                        "flag": "failed",
                                        "message": "Invoice gagal masuk ke Oracle. Nomor Invoice sudah ada.",
                                        "status_code": 200
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Sync feedback berhasil dibuat",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/AccountMoveSuccessResponse"
                                        },
                                        "example": {
                                            "success": True,
                                            "message": "Sync feedback created successfully",
                                            "data": {
                                                "invoice_id": 1,
                                                "invoice_number": "INV/2024/0001",
                                                "sync_log_id": 1,
                                                "status_code": 200
                                            }
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "(400) Bad Request - Missing fields atau flag tidak valid",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                }
                            },
                            # **HIGHLIGHTED: Added 401 Unauthorized response**
                            "401": {
                                "description": "(401) Unauthorized - Invalid or missing token",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/UnauthorizedResponse"
                                        }
                                    }
                                }
                            },
                            "404": {
                                "description": "(404) Invoice tidak ditemukan",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                }
                            },
                            "500": {
                                "description": "(500) Internal Server Error",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/api/oracle/sync/feedback/customer": {
                    "post": {
                        "tags": ["Customer"],
                        "summary": "Sync feedback untuk Customer",
                        "description": "Endpoint untuk menerima feedback dari Oracle system untuk Customer",
                        # **HIGHLIGHTED: Added security requirement for this endpoint**
                        "security": [
                            {
                                "BearerAuth": []
                            }
                        ],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/CustomerFeedback"
                                    },
                                    "example": {
                                        "vat_or_ktp": "123456789012345",
                                        "create_date": "2024-01-15",
                                        "flag": "success",
                                        "message": "Data Customer gagal masuk ke Oracle.",
                                        "status_code": 200
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "(200) Sync feedback berhasil dibuat",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/CustomerSuccessResponse"
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "(400) Bad Request - Missing fields atau flag tidak valid",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                }
                            },
                            # **HIGHLIGHTED: Added 401 Unauthorized response**
                            "401": {
                                "description": "(401) Unauthorized - Invalid or missing token",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/UnauthorizedResponse"
                                        }
                                    }
                                }
                            },
                            "404": {
                                "description": "(404) Partner tidak ditemukan",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                }
                            },
                            "500": {
                                "description": "(500) Internal Server Error",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/api/oracle/sync/feedback/supplier": {
                    "post": {
                        "tags": ["Supplier"],
                        "summary": "Sync feedback untuk Supplier",
                        "description": "Endpoint untuk menerima feedback dari Oracle system untuk Supplier",
                        # **HIGHLIGHTED: Added security requirement for this endpoint**
                        "security": [
                            {
                                "BearerAuth": []
                            }
                        ],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/SupplierFeedback"
                                    },
                                    "example": {
                                        "supplier_site": "john_doe",
                                        "name": "John Doe",
                                        "flag": "failed",
                                        "message": "Data supplier gagal masuk ke Oracle.",
                                        "status_code": 200
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "(200) Sync feedback berhasil dibuat",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/SupplierSuccessResponse"
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "(400) Bad Request - Missing fields atau flag tidak valid",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                }
                            },
                            # **HIGHLIGHTED: Added 401 Unauthorized response**
                            "401": {
                                "description": "(401) Unauthorized - Invalid or missing token",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/UnauthorizedResponse"
                                        }
                                    }
                                }
                            },
                            "404": {
                                "description": "(404) Partner tidak ditemukan",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                }
                            },
                            "500": {
                                "description": "(500) Internal Server Error",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                # "/api/oracle/sync/invoice/status/{invoice_id}": {
                #     "get": {
                #         "tags": ["Account Move"],
                #         "summary": "Get status sync invoice",
                #         "description": "Endpoint untuk mengecek status sinkronisasi invoice",
                #         "parameters": [
                #             {
                #                 "name": "invoice_id",
                #                 "in": "path",
                #                 "required": True,
                #                 "schema": {
                #                     "type": "integer"
                #                 },
                #                 "description": "ID invoice yang akan dicek statusnya"
                #             }
                #         ],
                #         "responses": {
                #             "200": {
                #                 "description": "Status sync berhasil diambil",
                #                 "content": {
                #                     "application/json": {
                #                         "schema": {
                #                             "$ref": "#/components/schemas/InvoiceStatusResponse"
                #                         }
                #                     }
                #                 }
                #             },
                #             "404": {
                #                 "description": "Sync log tidak ditemukan",
                #                 "content": {
                #                     "application/json": {
                #                         "schema": {
                #                             "$ref": "#/components/schemas/ErrorResponse"
                #                         }
                #                     }
                #                 }
                #             },
                #             "500": {
                #                 "description": "Internal Server Error",
                #                 "content": {
                #                     "application/json": {
                #                         "schema": {
                #                             "$ref": "#/components/schemas/ErrorResponse"
                #                         }
                #                     }
                #                 }
                #             }
                #         }
                #     }
                # }
            }
        }

        return request.make_response(
            json.dumps(openapi_spec, indent=2),
            headers=[('Content-Type', 'application/json')],
            status=200
        )

    # For Invoice & Vendor Bill
    @http.route('/api/oracle/sync/feedback/account-move', type='http', auth='none', methods=['POST'], csrf=False,
                cors='*')
    def account_move_sync_feedback_http(self, **kwargs):
        try:
            # **HIGHLIGHTED: Added token validation**
            is_valid, message = self._validate_token()
            if not is_valid:
                response_data = {
                    'success': False,
                    'message': message,
                    'status_code': 401
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=401
                )

            # Parse JSON dari request body
            data = {}

            if request.httprequest.content_type and 'application/json' in request.httprequest.content_type:
                try:
                    body_data = request.httprequest.get_data(as_text=True)
                    if body_data:
                        data = json.loads(body_data)
                except Exception as e:
                    _logger.error(f"Error parsing JSON: {str(e)}")
                    return request.make_response(
                        json.dumps({
                            'success': False,
                            'message': 'Invalid JSON format',
                            'status_code': 400
                        }),
                        headers=[('Content-Type', 'application/json')],
                        status=400
                    )
            else:
                # Dari form data atau URL params
                data = dict(request.httprequest.form) or dict(request.httprequest.args)

            required_fields = ['invoice_number', 'invoice_date', 'flag', 'message', 'status_code']
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                response_data = {
                    'success': False,
                    'message': f'Missing required fields: {", ".join(missing_fields)}',
                    'status_code': 400
                }
                _logger.error('Failed to send feedback: ', response_data)
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            # Extract data
            invoice_number = data.get('invoice_number')
            invoice_date = data.get('invoice_date')
            flag = data.get('flag')
            message = data.get('message')
            status_code = int(data.get('status_code')) if data.get('status_code') else 0

            flag_rules = ['failed', 'success', 'error']
            if flag not in flag_rules:
                response_data = {
                    'success': False,
                    'message': f'Incorrect flag value: {flag}',
                    'status_code': 400
                }
                _logger.error('Failed to send feedback: ', flag)
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            # Cari Invoice / Vendor Bills berdasarkan invoice number
            query_result = None
            invoice = request.env['account.move'].sudo().search([
                ('name', '=', invoice_number.strip()),
                ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice'])
            ], limit=1)
            records = request.env['account.move'].sudo().search([('id', '=', '229364'),])

            _logger.warning(f"Invoice: {invoice} {records}")

            if not invoice:
                query_get_inv = """
                    SELECT id, invoice_date, name FROM account_move am WHERE am.name = %s
                """
                print('self', self, query_get_inv)
                request.env.cr.execute(query_get_inv, (str(invoice_number.strip()),))
                query_result = request.env.cr.dictfetchone()

                _logger.warning(f"Invoice from Query DB: {query_result}")

            if not invoice and not query_result:
                _logger.warning(f"Invoice not found: {invoice_number}")
                response_data = {
                    'success': False,
                    'message': f'Invoice {invoice_number} not found',
                    'status_code': 404
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )

            # Buat log sync
            sync_log_vals = {
                'flag': flag,
                'related_id': invoice.id if invoice else query_result['id'],
                'res_model': 'account.move',
                'status_code': status_code,
                'message': message
            }

            sync_log = request.env['oracle.sync.log'].sudo().create(sync_log_vals)

            _logger.info(f"Oracle sync feedback created for invoice {invoice_number}, status: {status_code}")

            response_data = {
                'success': True,
                'message': 'Sync feedback created successfully',
                'data': {
                    'invoice_id': invoice.id if invoice else query_result['id'],
                    'invoice_number': invoice_number,
                    'sync_log_id': sync_log.id,
                    'status_code': status_code
                }
            }

            if not invoice:
                query_update_invoice = """
                    UPDATE account_move
                    SET is_failed_sync_to_oracle = %s, oracle_sync_log_status_code = %s, oracle_sync_log_message = %s, oracle_sync_log_date = %s
                    WHERE id = %s
                """
                request.env.cr.execute(query_update_invoice, (
                    str(flag).lower() == 'failed' or str(flag).lower() == 'error',
                    status_code,
                    message,
                    datetime.now(),
                    query_result['id'],
                ))
            else:
                invoice.is_failed_sync_to_oracle = str(flag).lower() == 'failed' or str(flag).lower() == 'error'
                invoice.oracle_sync_log_status_code = status_code
                invoice.oracle_sync_log_message = message
                invoice.oracle_sync_log_date = datetime.now()

            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.error(f"Error processing Oracle sync feedback: {str(e)}")
            response_data = {
                'success': False,
                'message': f'Internal server error: {str(e)}',
                'status_code': 500
            }
            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    # For Customer
    @http.route('/api/oracle/sync/feedback/customer', type='http', auth='none', methods=['POST'], csrf=False,
                cors='*')
    def customer_sync_feedback_http(self, **kwargs):
        try:
            # **HIGHLIGHTED: Added token validation**
            is_valid, message = self._validate_token()
            if not is_valid:
                response_data = {
                    'success': False,
                    'message': message,
                    'status_code': 401
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=401
                )

            # Parse JSON dari request body
            data = {}

            if request.httprequest.content_type and 'application/json' in request.httprequest.content_type:
                try:
                    body_data = request.httprequest.get_data(as_text=True)
                    if body_data:
                        data = json.loads(body_data)
                except Exception as e:
                    _logger.error(f"Error parsing JSON: {str(e)}")
                    return request.make_response(
                        json.dumps({
                            'success': False,
                            'message': 'Invalid JSON format',
                            'status_code': 400
                        }),
                        headers=[('Content-Type', 'application/json')],
                        status=400
                    )
            else:
                # Dari form data atau URL params
                data = dict(request.httprequest.form) or dict(request.httprequest.args)

            required_fields = ['vat_or_ktp', 'create_date', 'flag', 'message', 'status_code']
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                response_data = {
                    'success': False,
                    'message': f'Missing required fields: {", ".join(missing_fields)}',
                    'status_code': 400
                }
                _logger.error('Failed to send feedback: ', response_data)
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            # Extract data
            vat_or_ktp = data.get('vat_or_ktp')
            create_date = data.get('create_date')
            flag = data.get('flag')
            message = data.get('message')
            status_code = int(data.get('status_code')) if data.get('status_code') else 0

            # **Validate create_date format YYYY-MM-DD**
            try:
                from datetime import datetime
                # Validate date format YYYY-MM-DD
                datetime.strptime(create_date, '%Y-%m-%d')
            except ValueError:
                response_data = {
                    'success': False,
                    'message': f'Invalid create_date format. Expected format: YYYY-MM-DD, received: {create_date}',
                    'status_code': 400
                }
                _logger.error(f'Invalid date format: {create_date}')
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            flag_rules = ['failed', 'success', 'error']
            if flag not in flag_rules:
                response_data = {
                    'success': False,
                    'message': f'Incorrect flag value: {flag}',
                    'status_code': 400
                }
                _logger.error('Failed to send feedback: ', flag)
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            # Cari Partner berdasarkan VAT
            partner = request.env['res.partner'].sudo().search([
                ('name', '!=', False),
                ('vat', '=', vat_or_ktp),
            ], limit=1)
            _logger.info(f"Hasil Pencarian Customer by VAT: ", partner)
            not_found_message = f'Partner with vat: {vat_or_ktp} not found'

            if not partner:
                partner = request.env['res.partner'].sudo().search([
                    ('name', '!=', False),
                    ('ktp', '=', vat_or_ktp),
                ], limit=1)
                _logger.info(f"Hasil Pencarian Customer by KTP: ", partner)
                not_found_message = f'Partner with ktp: {vat_or_ktp} not found'

            _logger.warning(f"Partner: {partner}")

            if not partner:
                _logger.warning(f"Partner not found: {vat_or_ktp}")
                response_data = {
                    'success': False,
                    'message': not_found_message,
                    'status_code': 404
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )

            partner.is_failed_sync_to_oracle = str(flag).lower() == 'failed' or str(flag).lower() == 'error'

            # Buat log sync
            sync_log_vals = {
                'flag': flag,
                'related_id': partner.id,
                'res_model': 'res.partner',
                'status_code': status_code,
                'message': message
            }

            sync_log = request.env['oracle.sync.log'].sudo().create(sync_log_vals)

            _logger.info(f"Oracle sync feedback created for partner {partner.name}, status: {status_code}")

            response_data = {
                'success': True,
                'message': 'Sync feedback created successfully',
                'data': {
                    'vat': partner.vat,
                    'ktp': partner.ktp,
                    'create_date': f"{partner.create_date}",
                    'sync_log_id': sync_log.id,
                    'status_code': status_code
                }
            }

            partner.oracle_sync_log_status_code = status_code
            partner.oracle_sync_log_message = message
            partner.oracle_sync_log_date = datetime.now()

            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.error(f"Error processing Oracle sync feedback: {str(e)}")
            response_data = {
                'success': False,
                'message': f'Internal server error: {str(e)}',
                'status_code': 500
            }
            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    # For Vendor/Supplier
    @http.route('/api/oracle/sync/feedback/supplier', type='http', auth='none', methods=['POST'], csrf=False,
                cors='*')
    def vendor_sync_feedback_http(self, **kwargs):
        try:
            # **HIGHLIGHTED: Added token validation**
            is_valid, message = self._validate_token()
            if not is_valid:
                response_data = {
                    'success': False,
                    'message': message,
                    'status_code': 401
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=401
                )

            # Parse JSON dari request body
            data = {}

            if request.httprequest.content_type and 'application/json' in request.httprequest.content_type:
                try:
                    body_data = request.httprequest.get_data(as_text=True)
                    if body_data:
                        data = json.loads(body_data)
                except Exception as e:
                    _logger.error(f"Error parsing JSON: {str(e)}")
                    return request.make_response(
                        json.dumps({
                            'success': False,
                            'message': 'Invalid JSON format',
                            'status_code': 400
                        }),
                        headers=[('Content-Type', 'application/json')],
                        status=400
                    )
            else:
                # Dari form data atau URL params
                data = dict(request.httprequest.form) or dict(request.httprequest.args)

            required_fields = ['supplier_site', 'name', 'flag', 'message', 'status_code']
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                response_data = {
                    'success': False,
                    'message': f'Missing required fields: {", ".join(missing_fields)}',
                    'status_code': 400
                }
                _logger.error('Failed to send feedback: ', response_data)
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            # Extract data
            supplier_site = data.get('supplier_site')
            name = data.get('name')
            flag = data.get('flag')
            message = data.get('message')
            status_code = int(data.get('status_code')) if data.get('status_code') else 0

            flag_rules = ['failed', 'success', 'error']
            if flag not in flag_rules:
                response_data = {
                    'success': False,
                    'message': f'Incorrect flag value: {flag}',
                    'status_code': 400
                }
                _logger.error('Failed to send feedback: ', flag)
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            # Cari Partner berdasarkan Name & Supplier Site
            partner = request.env['res.partner'].sudo().search([
                ('is_vendor', '=', True),
                ('name', '=', name),
                ('supplier_site', '=', supplier_site),
            ], limit=1)

            _logger.warning(f"Partner: {partner}")

            if not partner:
                _logger.warning(f"Partner not found: {supplier_site}")
                response_data = {
                    'success': False,
                    'message': f'Partner with supplier_site: {supplier_site} and name: {name} not found',
                    'status_code': 404
                }
                return request.make_response(
                    json.dumps(response_data),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )

            partner.is_failed_sync_to_oracle = str(flag).lower() == 'failed' or str(flag).lower() == 'error'

            # Buat log sync
            sync_log_vals = {
                'flag': flag,
                'related_id': partner.id,
                'res_model': 'res.partner',
                'status_code': status_code,
                'message': message
            }

            sync_log = request.env['oracle.sync.log'].sudo().create(sync_log_vals)

            _logger.info(f"Oracle sync feedback created for partner {partner.name}, status: {status_code}")

            response_data = {
                'success': True,
                'message': 'Sync feedback created successfully',
                'data': {
                    'name': f"{partner.name}",
                    'supplier_site': partner.supplier_site,
                    'sync_log_id': sync_log.id,
                    'status_code': status_code
                }
            }

            partner.oracle_sync_log_status_code = status_code
            partner.oracle_sync_log_message = message
            partner.oracle_sync_log_date = datetime.now()

            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.error(f"Error processing Oracle sync feedback: {str(e)}")
            response_data = {
                'success': False,
                'message': f'Internal server error: {str(e)}',
                'status_code': 500
            }
            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

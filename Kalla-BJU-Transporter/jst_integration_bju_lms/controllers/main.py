from fastapi import FastAPI
import odoorpc
from pydantic import BaseModel

app = FastAPI()

# Connect to Odoo
odoo = odoorpc.ODOO('localhost', port=8069)  # Replace with your Odoo server details
odoo.login('odoo17_rnd', 'odoo17', 'odoo17')  # Replace with your credentials

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI-Odoo integration!"}

@app.get("/partners")
def get_partners():
    partners = odoo.env['res.partner'].search_read([], ['name', 'email'])
    return {"partners": partners}

class Partner(BaseModel):
    name: str
    email: str

@app.post("/partners")
def create_partner(partner: Partner):
    partner_id = odoo.env['res.partner'].create({'name': partner.name, 'email': partner.email})
    return {"partner_id": partner_id}

from datetime import date
from odoo import _, fields, models
from fastapi import APIRouter, Depends
from typing import Annotated, Union
from pydantic import BaseModel
from odoo.api import Environment
from odoo.addons.fastapi.dependencies import odoo_env


class FastapiEndpoint(models.Model):
    _inherit = "fastapi.endpoint"

    app = fields.Selection(selection_add=[("odoo_endpoint", "Odoo Endpoint")],
                           ondelete={"odoo_endpoint": "cascade"})

    def _get_fastapi_routers(self):
        if self.app == "odoo_endpoint":
            return [router]
        return super()._get_fastapi_routers()

router = APIRouter()

class PartnerInfo(BaseModel):
    name: str
    email: str

class JournalEntryItems(BaseModel):
    account_id: str
    name: str
    debit: float
    credit: float

class JournalEntryInfo(BaseModel):
    id: int
    name: str
    date: date
    partner_id: str
    journal_id: str
    line_ids: list[JournalEntryItems]


@router.get("/partners", response_model=list[PartnerInfo])
def get_partners(env: Annotated[Environment, Depends(odoo_env)]) -> list[PartnerInfo]:
    return [
        PartnerInfo(name=partner.name,
                    email=partner.email if partner.email else '')
        for partner in env["res.partner"].search([])
    ]

@router.get("/journal_entry", response_model=list[JournalEntryInfo])
def get_journal_entry(env: Annotated[Environment, Depends(odoo_env)]) -> list[JournalEntryInfo]:
    return [
        JournalEntryInfo(
            id=journal_entry.id,
            name=journal_entry.name,
            date=journal_entry.date,
            partner_id=journal_entry.partner_id.name if journal_entry.partner_id else '',
            journal_id=journal_entry.journal_id.name if journal_entry.journal_id else '',
            line_ids=[JournalEntryItems(
                account_id=line_id.account_id.name if line_id.account_id else '',
                name=line_id.name if line_id.name else '',
                debit=line_id.debit,
                credit=line_id.credit,
            ) for line_id in journal_entry.line_ids]) for journal_entry in env["account.move"].search([])
    ]

@router.get("/journal_entry/id/{id}", response_model=list[JournalEntryInfo])
def get_journal_entry(env: Annotated[Environment, Depends(odoo_env)], id: int) -> list[JournalEntryInfo]:
    return [
        JournalEntryInfo(
            id=journal_entry.id,
            name=journal_entry.name,
            date=journal_entry.date,
            partner_id=journal_entry.partner_id.name if journal_entry.partner_id else '',
            journal_id=journal_entry.journal_id.name if journal_entry.journal_id else '',
            line_ids=[JournalEntryItems(
                account_id=line_id.account_id.name if line_id.account_id else '',
                name=line_id.name if line_id.name else '',
                debit=line_id.debit,
                credit=line_id.credit,
            ) for line_id in journal_entry.line_ids]) for journal_entry in env["account.move"].browse(id)
    ]



# from odoo import _, fields, models
# from ..routers import odoo_auth_endpoint
#
#
# class FastapiEndpoint(models.Model):
#     _inherit = "fastapi.endpoint"
#
#     app = fields.Selection(selection_add=[("odoo_endpoint", "Odoo Endpoint")],
#                            ondelete={"odoo_endpoint": "cascade"})
#
#     def _get_fastapi_routers(self):
#         if self.app == "odoo_endpoint":
#             return [odoo_auth_endpoint]
#         return super()._get_fastapi_routers()


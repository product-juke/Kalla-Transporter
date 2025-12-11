from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    businessUnit = fields.Char('Business Unit')
    transactionSource = fields.Char('Transaction Source')
    transactionType = fields.Char('Transaction Type')
    conversionRateType = fields.Char('Conversion Rate Type')
    org = fields.Char()
    ar_lines = fields.One2many('oracle.ar.line', 'company_id', 'AR Lines')
    ap_lines = fields.One2many('oracle.ap.line', 'company_id', 'AP Lines')
    transaction_types = fields.One2many('oracle.program.transaction.type', 'company_id', 'Transaction Type by Program')


class OracleArLine(models.Model):
    _name = 'oracle.ar.line'

    company_id = fields.Many2one('res.company')
    memoLineName = fields.Char('Memo Line Name')
    description = fields.Char()
    account_id = fields.Many2one('account.account')
    taxClassificationCode = fields.Char('Tax Classification Code')
    program_category_id = fields.Many2one('program.category')


class OracleApLine(models.Model):
    _name = 'oracle.ap.line'

    company_id = fields.Many2one('res.company')
    DistributionSet = fields.Char('Distribution Set')
    description = fields.Char()
    account_id = fields.Many2one('account.account')
    taxClassification = fields.Char('Tax Classification')
    program_category_id = fields.Many2one('program.category')

class OracleProgramTransactionType(models.Model):
    _name = 'oracle.program.transaction.type'

    company_id = fields.Many2one('res.company')
    program_category_id = fields.Many2one('program.category')
    transaction_type = fields.Char()

    _sql_constraints = [
        ('unique_program_company', 'UNIQUE(program_category_id, company_id)',
         'Program Category cannot have duplicate entries for the same Company!')
    ]

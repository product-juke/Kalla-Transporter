from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    message_main_attachment_id = fields.Many2one(groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    permit_no = fields.Char('Work Permit No', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    # private info
    private_street = fields.Char(string="Private Street", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    private_street2 = fields.Char(string="Private Street2", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    private_city = fields.Char(string="Private City", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    private_state_id = fields.Many2one(
        "res.country.state", string="Private State",
        domain="[('country_id', '=?', private_country_id)]",
        groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    private_zip = fields.Char(string="Private Zip", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    private_country_id = fields.Many2one("res.country", string="Private Country", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    private_phone = fields.Char(string="Private Phone", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    private_email = fields.Char(string="Private Email", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    country_id = fields.Many2one(
        'res.country', 'Nationality (Country)', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    marital = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married'),
        ('cohabitant', 'Legal Cohabitant'),
        ('widower', 'Widower'),
        ('divorced', 'Divorced')
    ], string='Marital Status', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", default='single', tracking=True)
    spouse_complete_name = fields.Char(string="Spouse Complete Name", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    spouse_birthdate = fields.Date(string="Spouse Birthdate", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    children = fields.Integer(string='Number of Dependent Children', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    place_of_birth = fields.Char('Place of Birth', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    country_of_birth = fields.Many2one('res.country', string="Country of Birth", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    birthday = fields.Date('Date of Birth', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    ssnid = fields.Char('SSN No', help='Social Security Number', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    sinid = fields.Char('SIN No', help='Social Insurance Number', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    identification_id = fields.Char(string='Identification No', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    passport_id = fields.Char('Passport No', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    bank_account_id = fields.Many2one(
        'res.partner.bank', 'Bank Account Number',
        domain="[('partner_id', '=', work_contact_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv",
        tracking=True,
        help='Employee bank account to pay salaries')
    visa_no = fields.Char('Visa No', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    visa_expire = fields.Date('Visa Expiration Date', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    work_permit_expiration_date = fields.Date('Work Permit Expiration Date', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    has_work_permit = fields.Binary(string="Work Permit", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    work_permit_scheduled_activity = fields.Boolean(default=False, groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv")
    work_permit_name = fields.Char('work_permit_name', compute='_compute_work_permit_name')
    additional_note = fields.Text(string='Additional Note', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    certificate = fields.Selection([
        ('graduate', 'Graduate'),
        ('bachelor', 'Bachelor'),
        ('master', 'Master'),
        ('doctor', 'Doctor'),
        ('other', 'Other'),
    ], 'Certificate Level', default='other', groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    study_field = fields.Char("Field of Study", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    study_school = fields.Char("School", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    emergency_contact = fields.Char("Contact Name", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    emergency_phone = fields.Char("Contact Phone", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    km_home_work = fields.Integer(string="Home-Work Distance", groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv", tracking=True)
    employee_type = fields.Selection([
            ('employee', 'Employee'),
            ('student', 'Student'),
            ('trainee', 'Trainee'),
            ('contractor', 'Contractor'),
            ('freelance', 'Freelancer'),
        ], string='Employee Type', default='employee', required=True, groups="hr.group_hr_user,jst_lms_group.group_logistic_lms_plan_armada,jst_lms_group.group_logistic_lms_adh,jst_lms_group.group_logistic_lms_kacab,jst_lms_group.group_logistic_lms_spv",
        help="The employee type. Although the primary purpose may seem to categorize employees, this field has also an impact in the Contract History. Only Employee type is supposed to be under contract and will have a Contract History.")

    job_id = fields.Many2one(tracking=True)

    @api.depends('emp_child_ids')
    def _compute_children(self):
        for rec in self:
            rec.children = len(rec.emp_child_ids)

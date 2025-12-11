from odoo import fields, models, api, _
from datetime import date
from odoo.exceptions import ValidationError
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    ktp = fields.Char('KTP')
    no_sim = fields.Char(string='No Driver License')
    admission_year = fields.Integer(string='Admission Year')
    graduate_year = fields.Integer(string='Graduate Year')
    emp_child_ids = fields.One2many(comodel_name="employee.child.line", inverse_name="employee_id", string="Children Data", tracking=True)
    emp_violation_ids = fields.One2many(comodel_name="disicplinary.line", inverse_name="employee_id")
    emp_insurance_ids = fields.One2many(comodel_name="insurance.line", inverse_name="employee_id")
    emergency_contact_ids = fields.One2many(comodel_name="emergency.contact", inverse_name="driver_id")
    license_expiry_date = fields.Date(string="Driver's License Expiry Date")
    diciplinary_count = fields.Integer(compute="compute_diciplinary_count", string="Diciplinary Count", store=False)
    partner_id = fields.Many2one('res.partner', string="Related Partner")
    recruitment_type = fields.Selection([('bju', 'BJU Recruitment'),
                                       ('outsourced', 'Outsourced'),('driver_recomended', 'Driver Recomended')], string='Recruitment Type', default=False)
    driver_id = fields.Many2one('res.partner', string="Driver Recomanded Name")
    ownership_driver_id = fields.Many2one('res.partner', string="Ownership Driver", domain=[('is_driver', '=', False)])
    employee_id_tms = fields.Char(string='Employee ID TMS', help='ID dari sistem TMS')
    license_type = fields.Char('Jenis SIM')
    children = fields.Integer(string='Number of Dependent Children', tracking=True, compute='_compute_children')

    @api.depends('emp_child_ids')
    def _compute_children(self):
        for rec in self:
            rec.children = len(rec.emp_child_ids)

    @api.onchange('no_sim')
    def onchange_no_sim(self):
        for rec in self:
            rec.partner_id.no_driving_license = rec.no_sim

    @api.onchange('license_type')
    def onchange_license_type(self):
        for rec in self:
            rec.partner_id.license_type = rec.license_type

    def sync_data_tms(self):
        is_from_view_form = self.env.context.get('is_from_view_form')
        if is_from_view_form:
            self.ensure_one()
        """
        Fungsi untuk sync data employee dengan TMS
        """
        try:
            # URL endpoint TMS
            url = "https://vtsapi.easygo-gps.co.id/api/HRManagement/Employee/list"

            # Header - ganti dengan token yang sesuai
            headers = {
                'Content-Type': 'application/json',
                'Token': '55AEED3BF70241F8BD95EAB1DB2DEF67'  # Ganti dengan token yang valid
            }

            # Body request - bisa disesuaikan sesuai kebutuhan
            payload = {
                'code': '',  # kosong untuk mendapatkan semua data
                'name': '',  # kosong untuk mendapatkan semua data
                'encrypted': 0
            }

            if is_from_view_form:
                payload = {
                    'code': self.partner_id.nid,  # kosong untuk mendapatkan semua data
                    'name': '',  # kosong untuk mendapatkan semua data
                    'encrypted': 0
                }

            # Hit endpoint TMS
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                _logger.info(f'Driver TMS => {result}')

                if result.get('ResponseCode') == 1:
                    tms_employees = result.get('Data', [])
                    updated_count = 0

                    # Loop setiap data employee dari TMS
                    for tms_emp in tms_employees:
                        tms_code = tms_emp.get('code')
                        tms_autoid = tms_emp.get('autoid')

                        if tms_code and tms_autoid:
                            # Cari employee di Odoo berdasarkan NID yang sama dengan code TMS
                            odoo_employee = self.search([('partner_id.nid', '=', tms_code)], limit=1)

                            if odoo_employee:
                                # Update field employee_id_tms dengan autoid dari TMS
                                odoo_employee.write({
                                    'employee_id_tms': str(tms_autoid)
                                })
                                updated_count += 1
                                _logger.info(f"Updated employee {odoo_employee.name} with TMS ID: {tms_autoid}")

                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Sync Berhasil',
                            'message': f'Berhasil sync {updated_count} data employee dengan TMS',
                            'type': 'success',
                            'sticky': False
                        }
                    }
                else:
                    error_msg = result.get('ResponseMsg', 'Unknown error')
                    _logger.error(f"TMS API Error: {error_msg}")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Sync Gagal',
                            'message': f'Error dari TMS: {error_msg}',
                            'type': 'danger',
                            'sticky': True
                        }
                    }
            else:
                _logger.error(f"HTTP Error: {response.status_code}")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Sync Gagal',
                        'message': f'HTTP Error: {response.status_code}',
                        'type': 'danger',
                        'sticky': True
                    }
                }

        except requests.exceptions.RequestException as e:
            _logger.error(f"Request Exception: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Gagal',
                    'message': f'Connection Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True
                }
            }
        except Exception as e:
            _logger.error(f"General Exception: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Gagal',
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        ktps = {vals.get('ktp') for vals in vals_list if vals.get('ktp')}
        if ktps:
            dup_partner = self.env['res.partner'].search([('ktp', 'in', list(ktps))], limit=1)
            if dup_partner:
                raise ValidationError(_("Nomor KTP %s sudah dipakai oleh kontak '%s'.")
                                      % (dup_partner.ktp, dup_partner.display_name))

        employees = super().create(vals_list)

        for emp, raw in zip(employees, vals_list):
            partner = emp.work_contact_id
            if not partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': emp.name or _('Employee'),
                    'company_id': emp.company_id.id if emp.company_id else False,
                    'is_company': False,
                })
                emp.work_contact_id = partner.id

            job_name = ((emp.job_id.name or '') or (emp.job_title or '')).strip().lower()
            if job_name in ('driver', 'drivers'):
                partner.sudo().write({'is_driver': True, 'is_vendor': True})

            if getattr(emp, 'ktp', False):
                other = self.env['res.partner'].search([
                    ('ktp', '=', emp.ktp),
                    ('id', '!=', partner.id)
                ], limit=1)
                if other:
                    raise ValidationError(_("Nomor KTP %s sudah dipakai oleh kontak '%s'.")
                                          % (emp.ktp, other.display_name))
                partner.sudo().write({'ktp': emp.ktp})

            copy_map = {
                'mobile_phone': 'mobile',
                'work_phone': 'phone',
                'work_email': 'email',
                'private_street': 'street',
            }
            vals_to_write = {}
            for emp_f, partner_f in copy_map.items():
                if emp._fields.get(emp_f):
                    val = emp[emp_f]
                    if val:
                        vals_to_write[partner_f] = val.id if emp_f.endswith('_id') else val
            if vals_to_write:
                partner.sudo().write(vals_to_write)

        return employees

    def write(self, vals):
        res = super().write(vals)

        # include job triggers so driver flag updates when job changes
        wc_triggers = {'ktp', 'work_email', 'work_phone', 'mobile_phone', 'job_id', 'job_title'}
        if wc_triggers.intersection(vals.keys()):
            for emp in self:
                partner = emp.work_contact_id
                if not partner:
                    continue

                updates = {}

                job_name = ((emp.job_id.name or '') or (emp.job_title or '')).strip().lower()
                if job_name in ('driver', 'drivers'):
                    updates.update({'is_driver': True, 'is_vendor': True})

                if 'ktp' in vals and emp.ktp:
                    dup = self.env['res.partner'].search(
                        [('ktp', '=', emp.ktp), ('id', '!=', partner.id)], limit=1
                    )
                    if dup:
                        raise ValidationError(
                            _("Nomor KTP %s sudah dipakai oleh kontak '%s'.")
                            % (emp.ktp, dup.display_name)
                        )
                    updates['ktp'] = emp.ktp

                mapping = {
                    'mobile_phone': 'mobile',
                    'work_phone': 'phone',
                    'work_email': 'email',
                }
                for emp_f, partner_f in mapping.items():
                    if emp_f in vals:
                        v = emp[emp_f]
                        if v:
                            updates[partner_f] = v

                if updates:
                    partner.sudo().write(updates)

        # --- NO address_home_id usage; write private_street to work contact directly ---
        if 'private_street' in vals:
            for emp in self:
                partner = emp.work_contact_id
                if not partner:
                    # keep current behavior: do nothing if no work contact
                    continue
                if emp.private_street:
                    partner.sudo().write({'street': emp.private_street})

        return res

    @api.model
    def notify_expired_licenses(self):
        today = date.today()
        expired_employees = self.search([('license_expiry_date', '<=', today)])

        for employee in expired_employees:
            if employee.user_id:
                self.env['bus.bus']._sendone(
                    f'res.partner',
                    employee.user_id.partner_id.id,
                    {
                        'type': 'simple_notification',
                        'title': 'License Expired!',
                        'message': f'Your driver’s license expired on {employee.license_expiry_date}.',
                        'sticky': True
                    }
                )

    # @api.depends('partner_id', 'driver_id', 'emp_violation_ids', 'partner_id.emp_violation_ids')
    def compute_diciplinary_count(self):
        for record in self:
            diciplinary_total = len(record.emp_violation_ids)
            record.diciplinary_count = diciplinary_total

    def action_view_diciplinaries(self):
        """Action triggered when smart button is clicked."""
        return {
            'name': 'Diciplinary',
            'type': 'ir.actions.act_window',
            'res_model': 'disicplinary.line',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.emp_violation_ids.ids)],
            'context': {
                'default_employee_id': self.id,
            },
        }

class EmployeeChildsLine(models.Model):

    _name = 'employee.child.line'

    employee_id = fields.Many2one(comodel_name="hr.employee")
    name = fields.Char(string="Name")
    birth_place = fields.Char(string="Birth Place")
    birth_date = fields.Date(string="Birth Date")

class DisicplinaryLine(models.Model):

    _name = 'disicplinary.line'

    employee_id = fields.Many2one(comodel_name="hr.employee")
    partner_id = fields.Many2one('res.partner', string="Driver", compute='_compute_partner_id', store=True)

    @api.depends('employee_id.partner_id')
    def _compute_partner_id(self):
        for rec in self:
            rec.partner_id = rec.employee_id.partner_id

    current_employee_id = fields.Integer(compute="_compute_current_employee_id")
    type_violation = fields.Selection([('behavior', 'Behavior'), ('performance', 'Performance')], string='Tipe Pelanggaran')
    violation_id = fields.Many2one('hr.violation', string="Nama Pelanggaran", domain="[('type_violation','=',type_violation)]")
    date = fields.Date(string="Tanggal Pelanggaran")
    file_bukti_pelanggaran = fields.Binary("Upload File Pelanggaran")
    file_bukti_pelanggaran_name = fields.Char("Nama File Pelanggaran")
    action_plan = fields.Char("Action Plan")
    information = fields.Char("Keterangan")
    status_id = fields.Many2one(
        'disciplinary.status',
        string='Status',
        required=True,
        help='Status pelanggaran (SP1, SP2, dll)'
    )
    action_plan_id = fields.Many2one(
        'disciplinary.action.plan',
        string='Action Plan',
        help='Rencana tindakan yang akan dilakukan'
    )

    @api.depends('partner_id', 'employee_id')
    def _compute_current_employee_id(self):
        for rec in self:
            context_id = self.env.context.get('default_employee_id')
            rec.current_employee_id = context_id
            
    # @api.model_create_multi
    # def create(self, vals_list):
    #     res = super().create(vals_list)
    #     for vals in vals_list:
    #         current_employee = self.env['hr.employee'].search([
    #             ('id', '=', vals['employee_id']),
    #         ], limit=1)
    #         total_diciplinary = self.env['disicplinary.line'].search_count([('employee_id', '=', vals['employee_id'])])
    #         current_employee.sudo().write({
    #             'diciplinary_count': total_diciplinary
    #         })
    #     return res

    # def write(self, vals):
    #     res = super(DisicplinaryLine, self).write(vals)
    #     if 'employee_id' in vals:
    #         current_employee = self.env['hr.employee'].search([
    #             ('id', '=', vals['employee_id']),
    #         ], limit=1)
    #         total_diciplinary = self.env['disicplinary.line'].search_count([('employee_id', '=', vals['employee_id'])])
    #         current_employee.sudo().write({
    #             'diciplinary_count': total_diciplinary
    #         })
    #     return res
    
    # def unlink(self):
    #     # Simpan employee_id sebelum record dihapus
    #     employee_ids = self.env['disicplinary.line'].mapped('employee_id').ids
    #     res = super(DisicplinaryLine, self).unlink()
        
    #     # Update diciplinary_count setelah record dihapus
    #     employees = self.env['hr.employee'].browse(employee_ids)
    #     for employee in employees:
    #         total_disciplinary = self.env['disicplinary.line'].search_count([('employee_id', '=', employee.id)])
    #         employee.sudo().write({
    #             'diciplinary_count': total_disciplinary
    #         })
    #     return res

class InsuranceLine(models.Model):

    _name = 'insurance.line'

    employee_id = fields.Many2one(comodel_name="hr.employee",default=lambda self: self.env.employee.id)
    type_insurance = fields.Selection([('kesehatan', 'Kesehatan'), ('ketenagakerjaan', 'Ketenagakerjaan'),('kendaraan', 'Kendaraan')], string='Tipe Asuransi')
    insurance_id = fields.Many2one('hr.insurance', string="Nama Asuransi", domain="[('type_insurance','=',type_insurance)]")
    no_insurance = fields.Char("No Asuransi")
    date_start_insurance = fields.Date(string="Tanggal Mulai Asuransi")
    date_end_insurance = fields.Date(string="Tanggal Berakhir Asuransi")


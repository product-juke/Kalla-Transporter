from odoo import fields, models, api, _
from datetime import date
from odoo.tools import UserError


class HrEmployeeBase(models.AbstractModel):
    _name = 'hr.employee.base'
    _inherit = ['hr.employee.base', 'portfolio.view.mixin']

    def _create_work_contacts(self):
        if self.is_lms(self.env.company.portfolio_id.name):
            if any(employee.work_contact_id for employee in self):
                raise UserError(_('Some employee already have a work contact'))

            driver_labels = ('Driver', 'Drivers', 'driver', 'drivers')
            contact_data = []
            for employee in self:
                contact_data.append({
                    'email': employee.work_email,
                    'no_driving_license': employee.no_sim or None,
                    'license_type': employee.license_type or None,
                    'mobile': employee.mobile_phone,
                    'name': employee.name,
                    'image_1920': employee.image_1920,
                    'company_id': employee.company_id.id,
                    'city': employee.private_city or None,
                    'state_id': employee.private_state_id.id or None,
                    'zip': employee.private_zip or None,
                    'country_id': employee.private_country_id.id or None,
                    'is_driver': True if employee.job_title in driver_labels else False,
                    'is_vendor': True if employee.job_title in driver_labels else False,
                })

            work_contacts = self.env['res.partner'].create(contact_data)
            for employee, work_contact in zip(self, work_contacts):
                employee.work_contact_id = work_contact
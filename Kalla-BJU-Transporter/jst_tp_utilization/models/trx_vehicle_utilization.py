from odoo import fields, models, api, _

class TrxVehicleUtilization(models.Model):
    _name = 'trx.vehicle.utilization'
    _description = 'Vehicle Utilization Transaction'

    date = fields.Date()
    plate_no = fields.Char()

    status_plan = fields.Selection(
        selection='_get_status_plan_selection',
        string='Status Plan'
    )

    status_actual = fields.Selection(
        selection='_get_status_plan_selection',
        string='Status Actual'
    )

    @api.model
    def _get_status_plan_selection(self):
        """
        Method untuk mendapatkan selection dari utilization_details
        Returns list of tuples (code, description)
        """
        utilization_details = self.env['utilization.details'].search([])
        selection = []

        for detail in utilization_details:
            # Menggunakan code sebagai key dan description sebagai label
            selection.append((detail.parent_status, detail.description))

        return selection

    def _get_parent_status_selection(self):
        utilization_model = self.env['utilization.details']
        parent_status_field = utilization_model._fields.get('parent_status')

        if parent_status_field and hasattr(parent_status_field, 'selection'):
            selection = parent_status_field.selection
            if callable(selection):
                return selection(utilization_model)
            else:
                return selection
        return []

    def _get_utilization_status_selection(self):
        utilization_model = self.env['utilization.details']
        utilization_status_field = utilization_model._fields.get('utilization_status')

        if utilization_status_field and hasattr(utilization_status_field, 'selection'):
            selection = utilization_status_field.selection
            if callable(selection):
                return selection(utilization_model)
            else:
                return selection
        return []

    vehicle_name = fields.Char()
    do_no_lms = fields.Char()
    do_no_tms = fields.Char()
    do_id_lms = fields.Integer(string="ID DO (Odoo LMS)")
    driver = fields.Char()
    product = fields.Char()
    category = fields.Char()
    so_no = fields.Char()
    customer = fields.Char()
    # revenue = fields.Float()
    invoice_no = fields.Char()
    # bop = fields.Float()
    branch_project = fields.Char()
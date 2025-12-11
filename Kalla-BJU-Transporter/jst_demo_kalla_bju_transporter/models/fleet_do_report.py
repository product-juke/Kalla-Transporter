from odoo import models, fields, api
from odoo.exceptions import ValidationError

class FleetDoReport(models.Model):
    _name = 'fleet.do.report'
    _description = 'Fleet DO Report (snapshot asal/tujuan per status_do)'
    _rec_name = 'no_do'
    _order = 'write_date desc, create_date desc'

    fleet_do_id = fields.Many2one('fleet.do', string='Delivery Order', index=True, ondelete='set null')
    external_do_id = fields.Char(string='External DO ID', index=True)

    # Kolom utama
    no_do = fields.Char(related='fleet_do_id.name', store=True, readonly=True)
    plat_nomor = fields.Char(related='fleet_do_id.vehicle_id.license_plate', store=True, readonly=True)
    asset_type = fields.Selection(
        related='fleet_do_id.vehicle_id.asset_type',
        store=True, readonly=True
    )
    
    status_do   = fields.Selection([
        ('0', 'In Used'),
        ('1', 'In Asal'),
        ('2', 'OTW Tujuan'),
        ('3', 'In Tujuan'),
        ('4', 'Out Tujuan'),
    ], required=True, index=True)

    location    = fields.Selection([('asal', 'Asal'), ('tujuan', 'Tujuan')], required=True, index=True)
    geo_name    = fields.Char()
    tgl_masuk   = fields.Datetime(required=True)
    tgl_keluar  = fields.Datetime(required=True)
    # status_desc = fields.Char()

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        # Filter berdasarkan company yang dipilih user
        domain = domain or []

        # Cek apakah sudah ada filter company_id
        has_company_filter = any(
            term[0] == 'fleet_do_id.company_id'
            for term in domain
            if isinstance(term, (list, tuple)) and len(term) >= 3
        )

        if not has_company_filter:
            # Tambahkan filter company_ids dari context atau env.companies
            company_ids = self.env.context.get('allowed_company_ids', self.env.companies.ids)
            domain = domain + [('fleet_do_id.company_id', 'in', company_ids)]

        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            access_rights_uid=access_rights_uid
        )
    
    def action_open_sync_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pilih Tanggal',
            'res_model': 'sync.fleet.do.report.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    # OPTIONAL: boleh dipertahankan untuk UX, tapi jangan diandalkan untuk persist
    @api.onchange('fleet_do_id')
    def on_change_fleet_do_id(self):
        for rec in self:
            do = rec.fleet_do_id
            rec.plat_nomor = do.vehicle_id.license_plate
            rec.no_do = do.name
            rec.asset_type = do.vehicle_id.asset_type

    # ------- Helpers -------
    def _extract_do_fields(self, do):
        """Ambil nilai yang mau dicopy ke report dari fleet.do."""
        return {
            'no_do': do.name or False,
            'plat_nomor': do.vehicle_id.license_plate or False,
            'asset_type': do.vehicle_id.asset_type or False,
        }

    # ------- Create -------
    def create(self, vals):
        # validasi tanggal
        start = vals.get('tgl_masuk')
        end = vals.get('tgl_keluar')
        if isinstance(start, str):
            start = fields.Datetime.from_string(start)
        if isinstance(end, str):
            end = fields.Datetime.from_string(end)
        if start and end and start > end:
            raise ValidationError("Start Date tidak boleh lebih besar dari End Date.")

        # injeksi field turunan dari DO sebelum create (agar tersimpan)
        if vals.get('fleet_do_id'):
            do = self.env['fleet.do'].browse(vals['fleet_do_id'])
            if do.vehicle_id:
                vals.update(self._extract_do_fields(do))

        rec = super(FleetDoReport, self).create(vals)

        # Mapping pakai STRING keys biar match dengan Selection
        vehicle_mapping = {
            '0': ('ready',    'On Book'),
            '1': ('on_going', 'Loading'),
            '2': ('on_going', 'On Delivery'),
            '3': ('on_going', 'Unloading'),
            '4': ('on_return','On The Way Pool'),
        }
        do_status_map = {
            '0': 'draft',
            '1': 'on_going',
            '2': 'on_going',
            '3': 'on_going',
            '4': 'on_return',
        }

        do = rec.fleet_do_id
        status_key = rec.status_do or '0'

        if do:
            # 1) Update status DO
            new_status = do_status_map.get(status_key, 'draft')
            do.status_delivery = new_status

            # 2) Update vehicle
            if status_key in vehicle_mapping:
                if do.vehicle_id:
                    if rec.status_do == '2':
                        do.vehicle_id.geofence_checkpoint = False
                        do.vehicle_id.driver_confirmation = False
                        do.vehicle_id.plan_armada_confirmation = False
                    if rec.status_do == '4':
                        do.vehicle_id.geofence_checkpoint = True
                        do.vehicle_id.driver_confirmation = False
                        do.vehicle_id.plan_armada_confirmation = False
                        
                    vehicle_status, last_label = vehicle_mapping[status_key]
                    vals_update = {'vehicle_status': vehicle_status}
                    last_status = self.env['fleet.vehicle.status'].search(
                        [('name_description', 'ilike', last_label)], limit=1
                    )
                    if last_status:
                        vals_update['last_status_description_id'] = last_status.id
                    do.vehicle_id.write(vals_update)

            # 3) Sinkron ke Sale Order
            # if do.sale_id and 'status_delivery' in self.env['sale.order']._fields:
                # do.sale_id.write({'status_delivery': new_status})
                self._update_related_sale_orders(do, new_status)

        return rec

    # ------- Write -------
    def write(self, vals):
        res = super(FleetDoReport, self).write(vals)

        # Jika DO diganti via write, refresh nilai copy-an
        if 'fleet_do_id' in vals:
            for rec in self:
                if rec.fleet_do_id:
                    rec.write(self._extract_do_fields(rec.fleet_do_id))

        vehicle_mapping = {
            '0': ('ready',    'On Book'),
            '1': ('on_going', 'Loading'),
            '2': ('on_going', 'On Delivery'),
            '3': ('on_going', 'Unloading'),
            '4': ('on_return','On The Way Pool'),
        }
        do_status_map = {
            '0': 'draft',
            '1': 'on_going',
            '2': 'on_going',
            '3': 'on_going',
            '4': 'on_return',
        }

        for rec in self:
            do = rec.fleet_do_id
            status_key = rec.status_do or '0'
            if do:
                new_status = do_status_map.get(status_key, 'draft')
                do.status_delivery = new_status

                if status_key in vehicle_mapping:
                    if do.vehicle_id:
                        if rec.status_do == '2':
                            do.vehicle_id.geofence_checkpoint = False
                            do.vehicle_id.driver_confirmation = False
                            do.vehicle_id.plan_armada_confirmation = False
                        if rec.status_do == '4':
                            do.vehicle_id.geofence_checkpoint = True
                            do.vehicle_id.driver_confirmation = False
                            do.vehicle_id.plan_armada_confirmation = False
                            
                        vehicle_status, last_label = vehicle_mapping[status_key]
                        upd = {'vehicle_status': vehicle_status}
                        last_status = self.env['fleet.vehicle.status'].search(
                            [('name_description', 'ilike', last_label)], limit=1
                        )
                        if last_status:
                            upd['last_status_description_id'] = last_status.id
                        do.vehicle_id.write(upd)

                        # if do.sale_id and 'status_delivery' in self.env['sale.order']._fields:
                        do.sale_id.write({'status_delivery': new_status})

                    # sinkron ke semua SO yang terkait DO ini via sale.order.line
                    self._update_related_sale_orders(do, new_status)

        return res
    
    def _update_related_sale_orders(self, do, new_status):
        sol_rs = self.env['sale.order.line'].search([('do_id', '=', do.id)])
        so_rs = sol_rs.mapped('order_id')
        if so_rs:
            so_rs.write({'status_delivery': new_status})


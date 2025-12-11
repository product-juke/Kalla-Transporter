from tokenize import String

from odoo import fields, models, api,_
import math
from odoo.tools.float_utils import float_round

class FleetBop(models.Model):
    _name = 'fleet.bop'
    _description = 'BOP'
    _rec_name = 'category_id'

    # General Information
    category_id = fields.Many2one('fleet.vehicle.model.category', string='Category Unit', required=True)
    merk_unit = fields.Char(String="Test 1")
    origin_id = fields.Many2one('master.origin', string='Origin', required=True)
    destination_id = fields.Many2one('master.destination', string='Destination', required=True)
    customer = fields.Many2one(
        'res.partner',
        string='Customer',
        domain=[('is_customer', '=', True)],
        required=True
    )
    total_distance = fields.Integer(string="Total Distance", store=True)
    distance_one_way = fields.Integer(String="Distance One Way", required=True)
    speed_avg_setting = fields.Integer(String="Speed Avg. Setting", required=True)

    #On Delivery
    leadtime_on_delivery_hour = fields.Float(
        string="Leadtime on Delivery (Jam)",
        compute="_compute_leadtime_on_delivery_hour",
        store=True,
    )
    leadtime_on_delivery_day = fields.Char(
        string="Leadtime on Delivery (Hari)",
        compute="_compute_leadtime_on_delivery_day",
        store=True,
    )
    loading_time = fields.Float(String="Loading Time (Jam)", required=True)
    istirahat_od_6hr = fields.Float(
        string="Istirahat OD (Setiap 6 Jam)",
        compute="_compute_istirahat_fields",
        store=True,
    )
    istirahat_od_14hr = fields.Float(
        string="Istirahat OD (Setiap 14 Jam)",
        compute="_compute_istirahat_fields",
        store=True,
    )

    #On Return
    leadtime_on_return_hour = fields.Float(
        string="Leadtime on Return (Jam)",
        compute="_compute_leadtime_on_return_hour",
        store=True,
        readonly=True,
    )
    leadtime_on_return_day = fields.Char(
        string="Leadtime on Return (Hari)",
        compute="_compute_leadtime_on_return_day",
        store=True
    )
    unloading_time = fields.Float(String="Unloading Time", required=True)
    istirahat_or_6hr = fields.Float(
        string="Istirahat OR (Setiap 6 Jam)",
        compute="_compute_istirahat_or_fields",
        store=True,
    )
    istirahat_or_14hr = fields.Float(
        string="Istirahat OR (Setiap 14 Jam)",
        compute="_compute_istirahat_or_fields",
        store=True,
    )

    #cycle time
    working_time = fields.Float(
        string="Working Time (Jam)",
        compute="_compute_cycle_times",
        store=True,
    )
    total_cycle_time = fields.Float(
        string="Total Cycle Time (Jam)",
        compute="_compute_cycle_times",
        store=True,
    )
    total_cycle_time_day = fields.Integer(
        string="Total Cycle Time (Hari)",
        compute="_compute_cycle_times",
        store=True,
    )
    working_day_setting = fields.Float(String="Working Day Setting", required=True)
    plan_cycle_time = fields.Float(
        string="Plan Cycle Time in 1 Month",
        compute="_compute_cycle_times",
        store=True,
    )

    #bahan bakar
    bbm_type = fields.Char(String="BBM Type", required=True)
    harga_bbm = fields.Float(String="Harga BBM (Rp)", required=True)
    bbm_ratio_od_setting = fields.Float(String="BBM Ration OD Setting", required=True)
    bbm_ratio_or_setting =  fields.Float(String="BBM Ration OR Setting", required=True)
    bbm_od = fields.Float(
        string="BBM OD / Rit",
        compute="_compute_bbm_and_costs",
        store=True,
    )
    bbm_or = fields.Float(
        string="BBM OR / Rit",
        compute="_compute_bbm_and_costs",
        store=True,
    )

    #driver
    jumlah_driver = fields.Integer(String="Jumlah Driver", required=True)
    honor_driver = fields.Float(String="Honor Driver / Jam (Rp)", required=True)
    uang_makan_driver = fields.Float(String="Uang Makan Driver / 8 Jam (Rp)", required=True)
    jumlah_helper = fields.Integer(String="Jumlah Driver", required=True)

    #helper
    upah_helper = fields.Integer(String="% Set Upah Helper", required=True)
    honor_helper = fields.Float(
        string="Honor Helper (Rp)",
        compute="_compute_bbm_and_costs",
        store=True,
    )
    uang_makan_helper = fields.Float(String="Uang Makan Helper / 8 Jam (Rp)", required=True)

    #bbm
    bbm_cost_od = fields.Float(
        string="BBM Cost OD (Rp)",
        compute="_compute_bbm_and_costs",
        store=True,
    )
    bbm_cost_or = fields.Float(
        string="BBM Cost OR (Rp)",
        compute="_compute_bbm_and_costs",
        store=True,
    )

    #Biaya Operasional Perjalanan (BOP)
    #driver
    set_jam_ewh = fields.Float(String="Set Jam EWH", required=True)
    honor_driver_day = fields.Float(
        string="Honor Driver / Hari (Rp)",
        compute="_compute_driver_costs",
        store=True,
    )
    uang_makan_driver_day = fields.Float(String="Uang Makan / Hari", required=True)
    total_honor_driver = fields.Float(
        string="Total Honor Driver (Rp)",
        compute="_compute_driver_costs",
        store=True,
    )
    uang_makan_driver_days = fields.Float(
        string="Uang Makan / Hari2 (Rp)",
        compute="_compute_driver_costs",
        store=True,
    )
    total_uang_makan_driver = fields.Float(
        string="Total Uang Makan Driver",
        compute="_compute_driver_costs",
        store=True,
    )

    #helper
    fix_honor_helper = fields.Float(
        string="Honor Helper (Rp)",
        compute="_compute_total_bop",
        store=True,
    )
    fix_uang_makan_helper = fields.Float(
        string="Uang Makan Helper (Rp)",
        compute="_compute_total_bop",
        store=True,
    )

    #Biaya Lainnya
    shipment = fields.Float(String="Shipment (Rp)", required=True)
    tol_parkir = fields.Float(String="Total & Parkir (Rp)", required=True)
    buruh_muat_bongkar = fields.Float(String="Buruh Muat / Bongkar (Rp)", required=True)
    retribusi = fields.Float(String="Retribusi (Rp)", required=True)

    total_bop = fields.Float(
        string="Total BOP (Rp)",
        compute="_compute_total_bop",
        store=True,
    )
    total_bop_driver = fields.Float(
        string="Total BOP Driver (Rp)",
        compute="_compute_total_bop_unit_and_driver",
        store=True,
    )
    total_bop_unit = fields.Float(
        string="Total BOP Unit (Rp)",
        compute="_compute_total_bop_unit_and_driver",
        store=True,
    )

    @api.onchange('distance_one_way')
    def _onchange_distance_one_way(self):
        # if self.distance_one_way:
            self.total_distance = self.distance_one_way * 2
        # else:
        #     self.total_distance = 0

    @api.depends('distance_one_way', 'speed_avg_setting')
    def _compute_leadtime_on_delivery_hour(self):
        for rec in self:
            if rec.distance_one_way and rec.speed_avg_setting:
                rec.leadtime_on_delivery_hour = rec.distance_one_way / rec.speed_avg_setting
            else:
                rec.leadtime_on_delivery_hour = 0.0

    @api.depends('leadtime_on_delivery_hour')
    def _compute_leadtime_on_delivery_day(self):
        for rec in self:
            hours = rec.leadtime_on_delivery_hour or 0.0
            days = int(hours // 24)
            remaining_hours = int(hours % 24)
            rec.leadtime_on_delivery_day = f"{days} hari {remaining_hours} jam"

    @api.depends('leadtime_on_delivery_hour')
    def _compute_istirahat_fields(self):
        for rec in self:
            hours = rec.leadtime_on_delivery_hour or 0.0

            # Rumus istirahat_od_6hr
            round_div_6 = round(hours / 6)
            rec.istirahat_od_6hr = (round_div_6 * 0.5) - 0.5 if round_div_6 > 0 else 0.0

            # Rumus istirahat_or_14hr
            round_div_14 = round(hours / 14)
            rec.istirahat_od_14hr = round_div_14 * 8 if round_div_14 > 0 else 0.0

    @api.depends('distance_one_way', 'speed_avg_setting')
    def _compute_leadtime_on_return_hour(self):
        for rec in self:
            if rec.distance_one_way and rec.speed_avg_setting:
                rec.leadtime_on_return_hour = rec.distance_one_way / rec.speed_avg_setting
            else:
                rec.leadtime_on_return_hour = 0.0

    @api.depends('leadtime_on_return_hour')
    def _compute_leadtime_on_return_day(self):
        for rec in self:
            hours = rec.leadtime_on_return_hour or 0.0
            days = int(hours // 24)
            remaining_hours = int(hours % 24)
            rec.leadtime_on_return_day = f"{days} hari {remaining_hours} jam"

    @api.depends('leadtime_on_return_hour')
    def _compute_istirahat_or_fields(self):
        for rec in self:
            hours = rec.leadtime_on_return_hour or 0.0

            # Rumus istirahat_od_6hr
            round_div_6 = round(hours / 6)
            rec.istirahat_or_6hr = (round_div_6 * 0.5) - 0.5 if round_div_6 > 0 else 0.0

            # Rumus istirahat_or_14hr
            round_div_14 = round(hours / 14)
            rec.istirahat_or_14hr = round_div_14 * 8 if round_div_14 > 0 else 0.0

    @api.depends(
        'leadtime_on_delivery_hour', 'loading_time', 'istirahat_od_6hr',
        'leadtime_on_return_hour', 'unloading_time', 'istirahat_or_6hr',
        'istirahat_od_14hr', 'working_day_setting'
    )
    def _compute_cycle_times(self):
        for rec in self:
            od_hour = rec.leadtime_on_delivery_hour or 0.0
            loading = rec.loading_time or 0.0
            istirahat_od_6 = rec.istirahat_od_6hr or 0.0
            or_hour = rec.leadtime_on_return_hour or 0.0
            unloading = rec.unloading_time or 0.0
            istirahat_or_6 = rec.istirahat_or_6hr or 0.0
            istirahat_od_14 = rec.istirahat_od_14hr or 0.0
            working_day = rec.working_day_setting or 0.0

            # 1. Working Time
            rec.working_time = od_hour + loading + istirahat_od_6 + or_hour + unloading + istirahat_or_6

            # 2. Total Cycle Time
            total_cycle = od_hour + loading + istirahat_od_6 + istirahat_od_14 + or_hour + unloading + istirahat_or_6
            rec.total_cycle_time = total_cycle

            # 3. Total Cycle Time Day (dibulatkan ke atas)
            total_cycle_day = math.ceil(total_cycle / 24) if total_cycle > 0 else 1
            rec.total_cycle_time_day = total_cycle_day

            # 4. Plan Cycle Time
            rec.plan_cycle_time = working_day / total_cycle_day if total_cycle_day > 0 else 0.0

    @api.depends(
        'distance_one_way',
        'bbm_ratio_od_setting',
        'bbm_ratio_or_setting',
        'upah_helper',
        'honor_driver',
        'harga_bbm'
    )
    def _compute_bbm_and_costs(self):
        for rec in self:
            distance = rec.distance_one_way or 0.0
            ratio_od = rec.bbm_ratio_od_setting or 1.0  # Hindari pembagian dengan nol
            ratio_or = rec.bbm_ratio_or_setting or 1.0
            harga_bbm = rec.harga_bbm or 0.0
            upah_helper_percent = rec.upah_helper or 0.0  # Nilai dalam persen, misal 60 untuk 60%
            honor_driver = rec.honor_driver or 0.0

            # Konversi upah_helper dari persen ke desimal
            upah_helper_decimal = upah_helper_percent / 100.0

            # 1. BBM OD dan OR
            rec.bbm_od = distance / ratio_od if ratio_od else 0.0
            rec.bbm_or = distance / ratio_or if ratio_or else 0.0

            # 2. Honor Helper
            rec.honor_helper = upah_helper_decimal * honor_driver

            # 3. Biaya BBM
            rec.bbm_cost_od = harga_bbm * rec.bbm_od
            rec.bbm_cost_or = harga_bbm * rec.bbm_or

    @api.depends(
        'honor_driver',
        'set_jam_ewh',
        'total_cycle_time_day',
        'uang_makan_driver_day',
        'uang_makan_driver'
    )
    def _compute_driver_costs(self):
        for rec in self:
            honor_driver = rec.honor_driver or 0.0
            set_jam_ewh = rec.set_jam_ewh or 0.0
            total_cycle_time_day = rec.total_cycle_time_day or 1  # Hindari pembagian dengan nol
            uang_makan_driver_day = rec.uang_makan_driver_day or 0.0
            uang_makan_driver = rec.uang_makan_driver or 0.0

            # 1. Honor Driver per Hari
            rec.honor_driver_day = honor_driver * set_jam_ewh

            # 2. Total Honor Driver
            rec.total_honor_driver = rec.honor_driver_day * total_cycle_time_day

            # 3. Uang Makan Driver Days
            rec.uang_makan_driver_days = uang_makan_driver_day * uang_makan_driver

            # 4. Total Uang Makan Driver
            rec.total_uang_makan_driver = rec.uang_makan_driver_days * total_cycle_time_day if total_cycle_time_day else 0.0

    @api.depends(
        'set_jam_ewh',
        'honor_helper',
        'total_cycle_time_day',
        'jumlah_helper',
        'working_time',
        'uang_makan_helper',
        'bbm_cost_od',
        'bbm_cost_or',
        'total_honor_driver',
        'total_uang_makan_driver',
        'shipment',
        'tol_parkir',
        'buruh_muat_bongkar',
        'retribusi'
    )
    def _compute_total_bop(self):
        for rec in self:
            set_jam_ewh = rec.set_jam_ewh or 0.0
            honor_helper = rec.honor_helper or 0.0
            total_cycle_time_day = rec.total_cycle_time_day or 0.0
            jumlah_helper = rec.jumlah_helper or 0
            working_time = rec.working_time or 0.0
            uang_makan_helper = rec.uang_makan_helper or 0.0

            # 1. Fix Honor Helper
            rec.fix_honor_helper = set_jam_ewh * honor_helper * total_cycle_time_day * jumlah_helper

            # 2. Fix Uang Makan Helper
            rec.fix_uang_makan_helper = jumlah_helper * (working_time / 4) * uang_makan_helper

            # 3. Total BOP
            raw_total_bop = (
                    (rec.bbm_cost_od or 0.0) +
                    (rec.bbm_cost_or or 0.0) +
                    (rec.total_honor_driver or 0.0) +
                    (rec.total_uang_makan_driver or 0.0) +
                    rec.fix_honor_helper +
                    rec.fix_uang_makan_helper +
                    (rec.shipment or 0.0) +
                    (rec.tol_parkir or 0.0) +
                    (rec.buruh_muat_bongkar or 0.0) +
                    (rec.retribusi or 0.0)
            )

            # rec.total_bop = math.ceil(raw_total_bop)
            rec.total_bop = float_round(raw_total_bop, precision_digits=0, rounding_method='UP')

    @api.depends(
        'set_jam_ewh',
        'honor_helper',
        'total_cycle_time_day',
        'jumlah_helper',
        'working_time',
        'uang_makan_helper',
        'bbm_cost_od',
        'bbm_cost_or',
        'total_honor_driver',
        'total_uang_makan_driver',
        'shipment',
        'tol_parkir',
        'buruh_muat_bongkar',
        'retribusi',
        'total_bop'
    )
    def _compute_total_bop_unit_and_driver(self):
        for rec in self:
            set_jam_ewh = rec.set_jam_ewh or 0.0
            honor_helper = rec.honor_helper or 0.0
            total_cycle_time_day = rec.total_cycle_time_day or 0.0
            jumlah_helper = rec.jumlah_helper or 0
            working_time = rec.working_time or 0.0
            uang_makan_helper = rec.uang_makan_helper or 0.0

            total_honor_helper = set_jam_ewh * honor_helper * total_cycle_time_day * jumlah_helper
            total_uang_makan_helper = jumlah_helper * (working_time / 4) * uang_makan_helper
            total_bop_driver = (rec.total_honor_driver or 0.0) + (rec.total_uang_makan_driver or 0.0) + (rec.buruh_muat_bongkar or 0.0) + total_honor_helper + total_uang_makan_helper
            total_bop_driver = float_round(total_bop_driver, precision_digits=0, rounding_method='UP')

            # rec.total_bop = math.ceil(raw_total_bop)
            rec.total_bop_driver = total_bop_driver
            rec.total_bop_unit = rec.total_bop - total_bop_driver

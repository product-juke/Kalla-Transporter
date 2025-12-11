from odoo import fields, models, api, _

class FleetHpp(models.Model):
    _name = 'fleet.hpp'
    _description = 'HPP'

    category_id = fields.Many2one('fleet.vehicle.model.category', string='Category Armada')

    # Jenis Mode - Origin
    origin_id = fields.Many2one('master.origin', string='Origin')
    origin_distance_per_trip_km = fields.Float(string='Distance per Trip (Km)')
    origin_kecepatan = fields.Float(string='Kecepatan (Km/Jam)')
    origin_lead_time_rit = fields.Float(string='Lead Time Perjalanan / Rit (Jam)')
    origin_lead_time_hari = fields.Float(string='Lead Time Perjalanan /Hari')

    #Jenis Mode - Destination
    destination_id = fields.Many2one('master.destination', string='Destination')
    dest_distance_per_trip_km = fields.Float(string='Distance per Trip (Km)')
    dest_kecepatan = fields.Float(string='Kecepatan (Km/Jam)')
    dest_lead_time_rit = fields.Float(string='Lead Time Perjalanan / Rit (Jam)')
    dest_lead_time_hari = fields.Float(string='Lead Time Perjalanan /Hari')

    #Jenis Mode - Load/Unload
    loading = fields.Float(string='Loading (Jam)')
    unloading = fields.Float(string='Unloading (Jam)')

    #Jenis Mode - Pengkapalan
    berangkat = fields.Float(string='Berangkat (Jam)')
    pulang = fields.Float(string='Pulang (Jam)')

    #Jenis Mode - Lead time
    lead_time_rit = fields.Float(string='Lead Time / Rit (Jam)')
    menunggu_kapal_pulang = fields.Float(string='Menunggu Kapal Pulang (Jam)')
    lead_time_perjalanan = fields.Float(string='Lead Time Perjalanan (Jam)')
    total_perjalanan = fields.Float(string='Total Perjalanan (Hari)')
    jumlah_hari_cycle_time = fields.Float(string='Jumlah Hari (Cycle Time)')

    # Jenis Mode - Asumsi Revenue
    asumsi_do_real = fields.Float(string='Asumsi DO Real')
    asumsi_do_ke_bju = fields.Float(string='Asumsi DO Ke BJU')
    hari_produktif_unit = fields.Float(string='Hari Produktif / Unit')
    jumlah_kebutuhan_unit = fields.Float(string='Jumlah Kebutuhan Unit')
    revenue_ritase = fields.Float(string='Revenue / Ritase')
    add_revenue_inap = fields.Float(string='Add Revenue Inap')
    revenue_rit = fields.Float(string='Revenue / Rit')
    revenue_bulan = fields.Float(string='Revenue / Bulan')

    # Direct Cost - BOP Driver Jakarta
    gaji_driver_jkt = fields.Float(string='Gaji Driver')
    uang_makan_jkt = fields.Float(string='Uang Makan')
    perkalian_uang_makan_jkt = fields.Integer(string='Perkalian Uang Makan')
    total_biaya_uang_makan_jkt = fields.Integer(string='Total Biaya Uang Makan?')


    # Direct Cost - BOP Driver Makassar & Balik papan
    gaji_driver_mks = fields.Float(string='Gaji Driver')
    uang_makan_mks = fields.Float(string='Uang Makan')
    perkalian_uang_makan_mks = fields.Integer(string='Perkalian Uang Makan')
    total_biaya_uang_makan_mks = fields.Integer(string='Total Biaya Uang Makan?')


    # Direct Cost - BOP BBM
    origin_ration_fuel = fields.Float(string='Ratio Fuel consumption factor - Km/L (Origin)')
    dest_ration_fuel = fields.Float(string='Ratio Fuel consumption factor - Km/L (Destination)')
    total_fuel = fields.Float(string='Total Fuel')
    biaya_bbm = fields.Float(string='Biaya BBM')

    # Direct Cost - BOP Additional
    biaya_pulang_transport_lokal = fields.Float(string='Biaya Pulang + Transport Lokal')
    biaya_retribusi = fields.Float(string='Biaya Restribusi')

    # Direct Cost - Biaya Pengkapalan
    biaya_berangkat = fields.Float(string='Biaya Berangkat')
    biaya_pulang = fields.Float(string='Biaya Pulang')

    # Direct Cost - Summary
    summary_revenue_rit = fields.Float(string='Revenue / Rit')
    summary_direct_cost_rit = fields.Float(string='Direct Cost / Rit')
    summary_direct_cost = fields.Float()
    direct_cost = fields.Float(string='Direct Cost')

    # Indirect Cost - Variable Indirect Cost
    jumlah_km = fields.Float(string='Jumlah KM')
    biaya_ban = fields.Float(string='Biaya Ban (KM)')
    penggunaan_ban = fields.Float(string='Penggunaan Ban (KM)')
    harga_ban = fields.Float()
    jumlah_ban = fields.Float(string='Jumlah Ban (Pcs)')
    biaya_maintenance = fields.Float(string='Biaya Mantenance (1000 Rupiah per KM)')

    # Laba Rugi
    laba_rugi_jumlah_km = fields.Float()
    laba_rugi_revenue_rit = fields.Float()
    laba_rugi_revenue_km = fields.Float()
    laba_rugi_bop_rit = fields.Float()
    laba_rugi_bop_km = fields.Float()
    laba_rugi_bop_to_revenue = fields.Float()

    # Gross Margin
    gross_margin = fields.Float()
    gross_margin_rit = fields.Float()
    gross_margin_to_revenue = fields.Float()

    company_id = fields.Many2one('res.company')
    currency_id = fields.Many2one('res.currency', string="Currency",
                                  default=lambda self: self.env.user.company_id.currency_id.id)
    analytic_distribution = fields.Many2one('account.analytic.account')

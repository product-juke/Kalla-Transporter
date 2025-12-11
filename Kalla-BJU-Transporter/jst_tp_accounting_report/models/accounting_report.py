# models/account_report_custom.py
from odoo import models, fields
import calendar

class AccountReport(models.Model):
    _inherit = "account.report"

    def _report_custom_engine_vehicle_target(self, *args, **kwargs):
        # --- ambil options (dict) dari *args* ---
        options = {}
        for a in args:
            if isinstance(a, dict) and ('date' in a or 'companies' in a or 'company_ids' in a):
                options = a
                break

        VL = self.env['vehicle.target.line']
        domain = []

        # -------------------------------------------------
        # 1) FILTER COMPANY via VEHICLE
        # -------------------------------------------------
        company_ids = []
        if isinstance(options, dict):
            company_ids = options.get('company_ids') or options.get('forced_company_ids') or []
            if not company_ids:
                comps = options.get('companies') or options.get('multi_company', {}).get('companies') or []
                if isinstance(comps, list) and comps and isinstance(comps[0], dict):
                    company_ids = [c.get('id') for c in comps if c.get('id')]
        if not company_ids:
            company_ids = [self.env.company.id]

        # cari field relasi ke vehicle di line
        veh_field = None
        for cand in ('vehicle_id', 'vehicle'):
            if cand in VL._fields and VL._fields[cand].type == 'many2one':
                veh_field = cand
                break

        # -------------------------------------------------
        # 2) FILTER BERDASARKAN analytic_accounts_groupby (match by NAME)
        #    - ambil nama analytic account dari options['analytic_accounts_groupby']
        #    - match ke nama vehicle (case-insensitive)
        # -------------------------------------------------
        # --- which analytic(s) apply to THIS column? ---
        owner_key = (options or {}).get('owner_column_group')
        fo = {}
        if owner_key and isinstance(options, dict) and isinstance(options.get('column_groups'), dict):
            fo = (options['column_groups'].get(owner_key) or {}).get('forced_options') or {}

        # 1) per-column ids (preferred)  2) fallback to global selection  3) none
        aa_ids = []
        if fo.get('analytic_groupby_option'):
            raw = fo.get('analytic_accounts_list') or ()
            aa_ids = [int(x) for x in raw] if isinstance(raw, (list, tuple)) else []
        if not aa_ids and isinstance(options, dict):
            aa_ids = options.get('analytic_accounts_groupby') or []

        # build names set for name-based matching (case-insensitive, trimmed)
        aa_names = set()
        if aa_ids:
            AA = self.env['account.analytic.account'].browse(aa_ids)
            aa_names = {(n or '').strip().lower() for n in AA.mapped('name') if n}

        if veh_field:
            veh_model = self.env[VL._fields[veh_field].comodel_name]
            veh_domain = []
            if 'company_id' in veh_model._fields and company_ids:
                veh_domain.append(('company_id', 'in', company_ids))
            # kandidat kendaraan di company aktif
            vehicles = veh_model.search(veh_domain)
            if aa_names:
                matched_ids = vehicles.filtered(
                    lambda v: (v.vehicle_name or '').strip().lower() in aa_names
                ).ids
            else:
                # bila tidak ada filter analytic → gunakan semua kendaraan di company
                matched_ids = vehicles.ids

            if not matched_ids:
                return {'balance': 0.0, 'result': 0.0}
            domain.append((veh_field, 'in', matched_ids))

        elif 'vehicle_name' in VL._fields:
            # Line hanya simpan nama kendaraan (char)
            if aa_names:
                # susun OR of ilike untuk tiap nama (robust ke case)
                name_or = []
                for nm in sorted({n for n in aa_names if n}):
                    name_or = (['|'] + name_or) if name_or else []
                    name_or += [('vehicle_name', 'ilike', nm)]
                if name_or:
                    domain += name_or
            # batasi company langsung kalau line punya company_id
            if 'company_id' in VL._fields and company_ids:
                domain.append(('company_id', 'in', company_ids))
        else:
            # tidak ada jejak vehicle; batasi company langsung bila ada
            if 'company_id' in VL._fields and company_ids:
                domain.append(('company_id', 'in', company_ids))

        # -------------------------------------------------
        # 3) FILTER RENTANG PERIODE → proyeksi ke (year, month)
        # -------------------------------------------------
        date_opt = (options.get('date') or {}) if isinstance(options, dict) else {}
        df_str = date_opt.get('date_from')
        dt_str = date_opt.get('date_to')
        if not df_str and not dt_str:
            dt = fields.Date.today()
            df = dt.replace(day=1)
        else:
            df = fields.Date.from_string(df_str) if df_str else fields.Date.from_string(dt_str)
            dt = fields.Date.from_string(dt_str) if dt_str else df
        if df > dt:
            df, dt = dt, df  # swap

        year_in_model = 'year' in VL._fields
        month_in_model = 'month' in VL._fields
        if year_in_model and month_in_model:
            year_is_int = VL._fields['year'].type in ('integer', 'float', 'monetary')
            month_field_type = VL._fields['month'].type

            # siapkan mapping selection key (kalau month=selection)
            selection_keys_lower = {}
            if month_field_type == 'selection':
                sel = VL._fields['month'].selection
                try:
                    sel_list = sel(self.env) if callable(sel) else (sel or [])
                except Exception:
                    sel_list = sel or []
                selection_keys_lower = {str(k).lower(): k for k, _ in sel_list}

            def month_key(m):
                if month_field_type == 'integer':
                    return m
                candidates = [
                    str(m), f"{m:02d}",
                    calendar.month_abbr[m].lower(),
                    calendar.month_name[m].lower(),
                ]
                if month_field_type == 'selection':
                    for c in candidates:
                        if c in selection_keys_lower:
                            return selection_keys_lower[c]
                    return f"{m:02d}" if f"{m:02d}".lower() in selection_keys_lower else str(m)
                # char/text
                return f"{m:02d}"

            # kelompokkan month per tahun lalu OR-kan
            groups = {}
            y, m = df.year, df.month
            while (y < dt.year) or (y == dt.year and m <= dt.month):
                groups.setdefault(y, []).append(month_key(m))
                if m == 12:
                    y += 1; m = 1
                else:
                    m += 1

            if groups:
                per_year = []
                for Y, months in groups.items():
                    if not months:
                        continue
                    yr_val = Y if year_is_int else str(Y)
                    per_year.append(['&', ('year', '=', yr_val), ('month', 'in', months)])
                if per_year:
                    or_dom = per_year[0]
                    for gd in per_year[1:]:
                        or_dom = ['|'] + or_dom + gd
                    domain += or_dom
        # jika tidak ada field year/month → tidak ditambah filter periode

        # -------------------------------------------------
        # 4) Agregasi total_target (alias + fallback manual)
        # -------------------------------------------------
        agg = VL.read_group(domain, ['total_target:sum as total'], [])
        total = 0.0
        if agg:
            total = (agg[0].get('total') or agg[0].get('total_target_sum') or 0.0)
        if not total:
            total = sum(VL.search(domain).mapped('total_target') or [0.0])

        sign = kwargs.get('sign', 1)
        value = float(total) * sign
        return {'balance': value, 'result': value}

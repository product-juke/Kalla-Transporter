# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # membuat DO dari PO
    def action_create_do(self, multiple=None):
        res = super().action_create_do(multiple=multiple)
        res_id = res['res_id'] if res else None
        if res_id and isinstance(res_id, int):
            do = self.env['fleet.do'].search([
                ('id', '=', res_id)
            ], limit=1)
            print('do detail => ', do.date, do.po_line_ids, do.category_id, do.line_ids)
            if (
                do.date
                and do.po_line_ids
                and do.category_id
                and (len(do.po_line_ids) > 0 or len(do.line_ids) > 0)
            ):
                line_ids = self._get_line_ids(do)
                print('line_ids => ', line_ids)
                if line_ids:
                    max_distance_line, bop = do._find_max_distance_line_and_bop(line_ids, do.category_id.id)
                    print('do ====> ', max_distance_line, bop)
                    utilization_data = do._prepare_single_utilization_data(do, line_ids)
                    if utilization_data and utilization_data != None:
                        for date_info in utilization_data['date_strings']:
                            do._create_single_utilization_record(do, utilization_data, date_info)

        return res

    def _get_line_ids(self, do):
        if len(do.po_line_ids) > 0:
            return [item.id for item in do.po_line_ids]
        elif len(do.line_ids) > 0:
            return [item.id for item in do.line_ids]
        return []
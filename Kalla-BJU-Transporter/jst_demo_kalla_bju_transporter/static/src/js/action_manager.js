/** @odoo-module **/
import { registry } from "@web/core/registry";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";
import { ListRenderer } from "@web/views/list/list_renderer";
/**
This handler is responsible for generating XLSX reports.
*/
registry.category("ir.actions.report handlers").add("qwerty_xlsx", async function (action) {
    if (action.report_type === 'xlsx') {
        BlockUI;

   await download({

           url: '/xlsx_reports',

           data: action.data,

           complete: () => unblockUI,

           error: (error) => self.call('crash_manager', 'rpc_error', error),

           });    }
});

export class CustomListRenderer extends ListRenderer {
    _onRowClicked(event) {
        if (event.target.closest('.o_list_boolean_toggle')) {
            event.stopPropagation();  // Prevent form from opening
        } else {
            super._onRowClicked(...arguments);
        }
    }
}
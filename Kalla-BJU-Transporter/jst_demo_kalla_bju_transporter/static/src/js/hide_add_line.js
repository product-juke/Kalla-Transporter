/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    get canCreate() {
        // Hide "Add a line" if context.hide_add is true
        return !this.props.list?.context?.hide_add;
    },
});

/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService, useBus } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class PrintDotMatrix extends Component {
    static template = "vit_dotmatrix.PrintDotMatrix";

    setup() {
        this.orm = useService("orm");
    }

    async handleOnClick() {
        const url = await this.orm.call("ir.config_parameter", "get_param", [
            "dotmatrix.url",
        ]);
        const printer_data = this.props.record.data.printer_data;
        if (!printer_data){
            alert('No data to print. Please click Update Printer Data on Dot Matrix Tab');
            return;
        }        
        $.ajax({
            type: "POST",
            url: url,
            data: {
                printer_data : printer_data
            },
            success: function(data) {
                alert('Print Succeeded!');
                console.log(data);
            },
            error: function(data) {
                alert('Dotmatrix Print Failed. Please check the Printer Proxy running');
                console.log(data);
            },
        });
    }
}
registry.category("view_widgets").add("print_dot_matrix", {
    component: PrintDotMatrix,
});
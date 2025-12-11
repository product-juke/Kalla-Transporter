/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CustomerDashboardOutstanding extends Component {
    static template = "customer.Dashboard.Outstanding";

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            outstandingData: [],
        });

        onWillStart(async () => {
            await this.loadOutstandingData();
        });
    }

    async loadOutstandingData() {
        try {
            console.log("📤 Fetching outstanding payment data...");
            const response = await this.rpc("/customer_dashboard_outstanding/data");
            console.log("📢 Received outstanding data:", response);

            if (response.error) {
                throw new Error(response.error);
            }

            this.state.outstandingData = response.top_outstanding_customers || [];
        } catch (error) {
            console.error("❌ Error loading outstanding data:", error);
            alert("⚠️ Error loading data: " + error.message);
        }
    }
}

console.log("📊 CustomerDashboardOutstanding loaded");
CustomerDashboardOutstanding.template = "customer.Dashboard.Outstanding";
registry.category("actions").add("customer_dashboard_outstanding", CustomerDashboardOutstanding);

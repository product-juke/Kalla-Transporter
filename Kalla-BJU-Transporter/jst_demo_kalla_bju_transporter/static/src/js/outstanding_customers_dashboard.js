/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class OutstandingCustomersDashboard extends Component {
    static template = "account.OutstandingCustomersDashboard"; // Template name

    setup() {
        this.rpc = useService("rpc");  // Use rpc service for API calls
        this.state = useState({
            outstandingCustomers: [],  // Stores top 10 customers with outstanding payments
            startDate: "",             // Filter start date
            endDate: "",               // Filter end date
        });

        // Load data when the component starts
        onWillStart(async () => {
            await this.loadOutstandingCustomers();
        });
    }

    // Fetch outstanding customer data from the server
    async loadOutstandingCustomers() {
        try {
            const params = {};
            if (this.state.startDate) params.start_date = this.state.startDate;
            if (this.state.endDate) params.end_date = this.state.endDate;

            const response = await this.rpc("/account_dashboard/top_outstanding", params);
            console.log("📢 Received data:", response);
            this.state.outstandingCustomers = response.top_outstanding || [];
        } catch (error) {
            console.error("❌ Error loading outstanding customers:", error);
        }
    }

    // Handle date filter change
    handleDateChange(event) {
        const { name, value } = event.target;
        this.state[name] = value;  // Update startDate or endDate
        console.log(`📅 Updated ${name}:`, value);
    }
}

console.log("📊 OutstandingCustomersDashboard loaded");
OutstandingCustomersDashboard.template = "account.OutstandingCustomersDashboard";
registry.category("actions").add("outstanding_customers_dashboard", OutstandingCustomersDashboard);


/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CustomerDashboard extends Component {
    static template = "customer.Dashboard";

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            customerData: [],
            outstandingData: [], // Data pelanggan dengan utang tertinggi
            startDate: "",  // Simpan input filter tanggal
            endDate: "",
            outstandingCustomers: [],
        });

        onWillStart(async () => {
            await this.loadAllData();
        });
    }

    async loadCustomerData() {
        try {
            const params = {};
            if (this.state.startDate) params.start_date = this.state.startDate;
            if (this.state.endDate) params.end_date = this.state.endDate;

            console.log("📤 Sending request with:", params);
            const response = await this.rpc("/customer_dashboard/data", params);
            console.log("📢 Received data:", response);

            this.state.customerData = response.transactions_per_customer || [];
            this.renderCharts();
        } catch (error) {
            console.error("❌ Error loading customer data:", error);
        }
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

    async loadAllData() {
        await this.loadCustomerData();
        await this.loadOutstandingCustomers(); 
    }

    handleDateChange(event) {
        const { name, value } = event.target;
        this.state[name] = value;  // Menyimpan nilai startDate atau endDate
        console.log(`📅 Updated ${name}:`, value);
    }

    renderCharts() {
        setTimeout(() => {
            const chartElement = document.getElementById("customerChart");
            if (!chartElement) {
                console.error("❌ customerChart element not found!");
                return;
            }

            if (this.customerChart) this.customerChart.destroy();

            const ctx = chartElement.getContext("2d");
            const labels = this.state.customerData.map(d => d.customer_name);
            const transactions = this.state.customerData.map(d => d.transactions);

            this.customerChart = new window.Chart(ctx, {
                type: "bar",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Total Transactions",
                        data: transactions,
                        backgroundColor: "rgba(54, 162, 235, 0.7)",
                        borderColor: "rgba(54, 162, 235, 1)",
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: "rgba(200, 200, 200, 0.2)" } },
                        y: { beginAtZero: true, grid: { color: "rgba(200, 200, 200, 0.2)" } }
                    },
                    plugins: { legend: { position: "top" } }
                }
            });
        }, 500);
    }
}

console.log("📊 CustomerDashboard loaded");
CustomerDashboard.template = "customer.Dashboard";
registry.category("actions").add("customer_dashboard", CustomerDashboard);

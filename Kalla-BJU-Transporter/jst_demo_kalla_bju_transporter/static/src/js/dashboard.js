/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class AccountingDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            revenue: 0,
            expenses: 0,
            outstandingPayments: 0,
            agingReport: { "0-30": 0, "31-60": 0, "61-90": 0, "90+": 0 },
            cashFlowIn: 0,
            cashFlowOut: 0,
            totalTaxCollected: 0,
            profitability: 0,
        });

        onMounted(() => this.fetchData());
    }

    async fetchData() {
        try {
            const result = await this.orm.call("account.move.line", "get_dashboard_data", []);
            Object.assign(this.state, result);
            this.renderCharts();
        } catch (error) {
            console.error("Error fetching dashboard data:", error);
        }
    }

    renderCharts() {
        const ctx1 = document.getElementById("revenueExpenseChart");
        new Chart(ctx1, {
            type: "line",
            data: {
                labels: ["Revenue", "Expenses"],
                datasets: [
                    {
                        data: [this.state.revenue, this.state.expenses],
                        borderColor: ["green", "red"],
                        backgroundColor: ["green", "red"],
                        fill: false,
                    },
                ],
            },
        });

        const ctx2 = document.getElementById("agingReportChart");
        new Chart(ctx2, {
            type: "bar",
            data: {
                labels: ["0-30 Days", "31-60 Days", "61-90 Days", "90+ Days"],
                datasets: [
                    {
                        data: Object.values(this.state.agingReport),
                        backgroundColor: [
                            "rgba(32, 201, 151, 0.8)",
                            "rgba(255, 193, 7, 0.8)",
                            "rgba(255, 145, 0, 0.8)",
                            "rgba(220, 53, 69, 0.8)"
                        ],
                        borderColor: [
                            "rgb(32, 201, 151)",
                            "rgb(255, 193, 7)",
                            "rgb(255, 145, 0)",
                            "rgb(220, 53, 69)"
                        ],
                        borderWidth: 1
                    },
                ],
            },
            options: {
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                }
            }
        });

        const ctx3 = document.getElementById("cashFlowChart");
        new Chart(ctx3, {
            type: "pie",
            data: {
                labels: ["Cash In", "Cash Out"],
                datasets: [
                    {
                        data: [this.state.cashFlowIn, this.state.cashFlowOut],
                        backgroundColor: [
                            "rgba(32, 201, 151, 0.8)",    // Green for cash in
                            "rgba(220, 53, 69, 0.8)"      // Red for cash out
                        ],
                        borderColor: [
                            "rgb(32, 201, 151)",
                            "rgb(220, 53, 69)"
                        ],
                    },
                ],
            },
            options: {
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                }
            }
        });
    }
}

console.log("📊 AccountingDashboard loaded");

AccountingDashboard.template = "accounting_dashboard.accounting_dashboard_template";

// ✅ Ensure action registry is properly set
registry.category("actions").add("accounting_dashboard_template", AccountingDashboard);

export default AccountingDashboard;
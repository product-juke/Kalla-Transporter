/** @odoo-module  **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";


export class VehicleDashboard extends Component {
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        className: { type: String, optional: true },
        globalState: { type: Object, optional: true }
    };

    setup() {
        this.action = useService("action");
        this.rpc = useService("rpc");
        this.state = useState({
            total_dos: 0,
            pending_dos: 0,
            done_dos: 0,
            unmatch_dos: 0,
            line_not_created_dos: 0,
            trans_vehicle_count_ready: 0,
            trans_vehicle_count_ready_on_book: 0,
            trans_vehicle_count_on_going: 0,
            trans_vehicle_count_on_return: 0,
            trans_vehicle_count_not_ready: 0,
            vli_vehicle_count_ready: 0,
            vli_vehicle_count_ready_on_book: 0,
            vli_vehicle_count_on_going: 0,
            vli_vehicle_count_on_return: 0,
            vli_vehicle_count_not_ready: 0,
            truck_vehicle_count_ready: 0,
            truck_vehicle_count_ready_on_book: 0,
            truck_vehicle_count_on_going: 0,
            truck_vehicle_count_on_return: 0,
            truck_vehicle_count_not_ready: 0,
            utilizationData: [],
            portfolios: [],
            show_all: false,
            driver_ready: 0,
            driver_on_duty: 0,
            driver_sakit: 0,
            driver_cuti: 0,
            driver_absent: 0,
        });

        this._onClickTotalDO = this._onClickTotalDO.bind(this);
        this._onClickPendingDO = this._onClickPendingDO.bind(this);
        this._onClickDoneDO = this._onClickDoneDO.bind(this);
        this._onClickTransReadyForUse = this._onClickTransReadyForUse.bind(this);
        this._onClickTransOnBook = this._onClickTransOnBook.bind(this);
        this._onClickTransOnGoing = this._onClickTransOnGoing.bind(this);
        this._onClickTransOnReturn= this._onClickTransOnReturn.bind(this);
        this._onClickVliReadyForUse = this._onClickVliReadyForUse.bind(this);
        this._onClickVliReadyOnBook = this._onClickVliReadyOnBook.bind(this);
        this._onClickVliOnGoing = this._onClickVliOnGoing.bind(this);
        this._onClickVliOnReturn = this._onClickVliOnReturn.bind(this);
        this._onClickVliNotReady = this._onClickVliNotReady.bind(this);
        this._onClickTruckReadyForUse = this._onClickTruckReadyForUse.bind(this);
        this._onClickTruckReadyOnBook = this._onClickTruckReadyOnBook.bind(this);
        this._onClickTruckOnGoing = this._onClickTruckOnGoing.bind(this);
        this._onClickTruckOnReturn = this._onClickTruckOnReturn.bind(this);
        this._onClickTruckNotReady = this._onClickTruckNotReady.bind(this);
        this._onClickDriverReady = this._onClickDriverReady.bind(this);
        this._onClickDriverOnDuty = this._onClickDriverOnDuty.bind(this);
        this._onClickDriverSakit = this._onClickDriverSakit.bind(this);
        this._onClickDriverCuti = this._onClickDriverCuti.bind(this);
        this._onClickDriverAbsent = this._onClickDriverAbsent.bind(this);
        onWillStart(async () => {
            await this.loadData();
            await this.loadUtilizationData();
        });

        onMounted(() => {
            setTimeout(() => this.renderCharts(), 1000);
        });
    }

    async loadData() {
        const data = await this.rpc("/vehicle_dashboard/data");
        Object.assign(this.state, data);
        this.renderCharts();
    }

    async loadUtilizationData() {
        this.state.utilizationData = await this.rpc("/vehicle_dashboard/utilization_data");
        this.renderCharts();
    }

    renderCharts() {
        setTimeout(() => {
            if (!document.getElementById("vehicleChart")) {
                console.error("vehicleChart element not found!");
                return;
            }

            if (this.vehicleChart) this.vehicleChart.destroy();
            if (this.doChart) this.doChart.destroy();
            if (this.utilizationChart) this.utilizationChart.destroy();

            const ctxVehicle = document.getElementById("vehicleChart").getContext("2d");
            this.vehicleChart = new window.Chart(ctxVehicle, {
                type: "doughnut",
                data: {
                    labels: ["Ready", "Ready On Book","On Going","On Return","Not Ready"],
                    datasets: [{
                        label: "Transporter Vehicle Status",
                        data: [this.state.trans_vehicle_count_ready, this.state.trans_vehicle_count_ready_on_book,
                               this.state.trans_vehicle_count_on_going, this.state.trans_vehicle_count_ready_on_book,
                               this.state.trans_vehicle_count_not_ready],
                        backgroundColor: ["rgb(199,21,133)", "rgb(139,0,139)", "rgb(218,165,32)", "rgb(178,34,34)", "rgb(255,69,0)"]
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            const ctxDO = document.getElementById("doChart").getContext("2d");
            this.doChart = new window.Chart(ctxDO, {
                type: "bar",
                data: {
                    labels: ["Total DO", "Pending DO", "Done DO","Unmatch DO","DO Line Not Created"],
                    datasets: [{
                        label: "Delivery Orders",
                        data: [this.state.total_dos, this.state.pending_dos, this.state.done_dos, this.state.unmatch_dos, this.state.line_not_created_dos],
                        backgroundColor: ["peachpuff", "yellow", "green", "red","gray"]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        tooltip: {
                            enabled: true,
                            callbacks: {
                                label: function(tooltipItem) {
                                    let label = tooltipItem.dataset.label || "";
                                    let value = tooltipItem.raw;
                                    return `${label}: ${value} orders`;
                                }
                            }
                        }
                    }
                }
            });

            const ctxUtilization = document.getElementById("utilizationChart").getContext("2d");

            // Ubah labels menjadi sumbu X
            const labels = this.state.utilizationData.map(d => `${d.vehicle_name} (${d.month}/${d.year})`);
            const totalTargets = this.state.utilizationData.map(d => d.total_target);
            const actualTargets = this.state.utilizationData.map(d => d.actual_target);
            const targetDayUtilization = this.state.utilizationData.map(d => d.target_days_utilization);

            this.utilizationChart = new window.Chart(ctxUtilization, {
                type: "bar",
                data: {
                    labels: labels, // Sumbu X akan berisi nama kendaraan + bulan/tahun
                    datasets: [
                        {
                            label: "Total Target",
                            data: totalTargets,
                            backgroundColor: "rgba(0, 0, 255, 0.7)", // Biru transparan
                            borderColor: "blue",
                            borderWidth: 1
                        },
                        {
                            label: "Actual Target",
                            data: actualTargets,
                            backgroundColor: "rgba(0, 128, 0, 0.7)", // Hijau transparan
                            borderColor: "green",
                            borderWidth: 1
                        },
                        {
                            label: "Target Day Utilization",
                            data: targetDayUtilization,
                            backgroundColor: "rgba(255, 0, 0, 0.7)", // Merah transparan
                            borderColor: "red",
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: "x", // Pastikan indexAxis adalah "x" agar nama kendaraan ada di X
                    scales: {
                        x: {
                            grid: { color: "rgba(200, 200, 200, 0.2)" },
                            ticks: {
                                autoSkip: false, // Agar semua label tetap terlihat
                                maxRotation: 45, // Rotasi teks untuk label agar tidak bertumpuk
                                minRotation: 45
                            }
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: "rgba(200, 200, 200, 0.2)" }
                        }
                    },
                    plugins: {
                        legend: { position: "top" },
                        tooltip: {
                            callbacks: {
                                label: function (tooltipItem) {
                                    return `${tooltipItem.dataset.label}: ${tooltipItem.raw}`;
                                }
                            }
                        }
                    }
                }
            });
        }, 500);
    }

    navigateToFleetDO(domain = []) {
        this.action.doAction({
            name: "Delivery Orders",
            type: "ir.actions.act_window",
            res_model: "fleet.do",
            view_mode: "list",
            views: [[false, "list"], [false, "form"]],
            domain: domain
        });
    }

    navigateToFleetVehicle(domain = []) {
        this.action.doAction({
            name: "Fleet Vehicles",
            type: "ir.actions.act_window",
            res_model: "fleet.vehicle",
            view_mode: "list",
            views: [[false, "list"], [false, "form"]],
            domain: domain
        });
    }

    navigateToDrivers(domain = []) {
        this.action.doAction({
            name: "Drivers",
            type: "ir.actions.act_window",
            res_model: "res.partner",
            view_mode: "list",
            views: [[false, "list"], [false, "form"]],
            domain: domain
        });
    }

    _onClickTotalDO() {
        this.navigateToFleetDO();
    }

    _onClickPendingDO() {
        this.navigateToFleetDO([["state", "=", "draft"]]);
    }

    _onClickDoneDO() {
        this.navigateToFleetDO([["state", "=", "done"], ["status_do", "=", "DO Match"]]);
    }

    _onClickTransReadyForUse() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "ready"], ["product_category_id.name", "=", "Transporter"], ["last_status_description_id.name_description", "ilike", "Ready for Use"]]);
    }

    _onClickTransOnBook() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "ready"], ["product_category_id.name", "=", "Transporter"], ["last_status_description_id.name_description", "ilike", "On Book"]]);
    }

    _onClickTransOnGoing() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "on_going"], ["product_category_id.name", "=", "Transporter"]]);
    }

    _onClickTransOnReturn() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "on_return"], ["product_category_id.name", "=", "Transporter"]]);
    }

    _onClickTransNotReady() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "not_ready"], ["product_category_id.name", "=", "Transporter"]]);
    }

     _onClickVliReadyForUse() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "ready"], ["product_category_id.name", "=", "VLI"], ["last_status_description_id.name_description", "ilike", "Ready for Use"]]);
    }

    _onClickVliReadyOnBook() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "ready"], ["product_category_id.name", "=", "VLI"], ["last_status_description_id.name_description", "ilike", "On Book"]]);
    }

    _onClickVliOnGoing() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "on_going"], ["product_category_id.name", "=", "VLI"]]);
    }
    _onClickVliOnReturn() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "on_return"], ["product_category_id.name", "=", "VLI"]]);
    }

    _onClickVliNotReady() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "not_ready"], ["product_category_id.name", "=", "VLI"]]);
    }
     _onClickTruckReadyForUse() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "ready"], ["product_category_id.name", "=", "Trucking"], ["last_status_description_id.name_description", "ilike", "Ready for Use"]]);
    }

    _onClickTruckReadyOnBook() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "ready"], ["product_category_id.name", "=", "Trucking"], ["last_status_description_id.name_description", "ilike", "On Book"]]);
    }

    _onClickTruckOnGoing() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "on_going"], ["product_category_id.name", "=", "Trucking"]]);
    }
    _onClickTruckOnReturn() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "on_return"], ["product_category_id.name", "=", "Trucking"]]);
    }

    _onClickTruckNotReady() {
        this.navigateToFleetVehicle([["vehicle_status", "=", "not_ready"], ["product_category_id.name", "=", "Trucking"]]);
    }

    _onClickDriverReady() {
        this.navigateToDrivers([["is_driver", "=", true], ["availability", "=", "Ready"]]);
    }

    _onClickDriverOnDuty() {
        this.navigateToDrivers([["is_driver", "=", true], ["availability", "=", "On Duty"]]);
    }

    _onClickDriverSakit() {
        this.navigateToDrivers([["is_driver", "=", true], ["availability", "=", "Sakit"]]);
    }

    _onClickDriverCuti() {
        this.navigateToDrivers([["is_driver", "=", true], ["availability", "=", "Cuti"]]);
    }

    _onClickDriverAbsent() {
        this.navigateToDrivers([["is_driver", "=", true], ["availability", "=", "Absent"]]);
    }
}

console.log("🚗 VehicleDashboard loaded");
VehicleDashboard.template = "vehicle.Dashboard";
registry.category("actions").add("vehicle_dashboard", VehicleDashboard);

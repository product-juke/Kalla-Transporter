/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class FleetMonitoring extends Component {
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        className: { type: String, optional: true },
        globalState: { type: Object, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.rpc = useService("rpc");
        this.state = useState({
            readyDrivers: 0,
            notReadyDrivers: 0,
            simExpiredDrivers: 0,
            competencyNeeded: 0,
            competencyNeededIds: [],
            standbyVehicles: 0,
            onDeliveryVehicles: 0,
            onReturnVehicles: 0,
            today: null,
        });

        this._onClickReadyDrivers = this._onClickReadyDrivers.bind(this);
        this._onClickNotReadyDrivers = this._onClickNotReadyDrivers.bind(this);
        this._onClickSimExpired = this._onClickSimExpired.bind(this);
        this._onClickCompetency = this._onClickCompetency.bind(this);
        this._onClickStandbyVehicles = this._onClickStandbyVehicles.bind(this);
        this._onClickOnDelivery = this._onClickOnDelivery.bind(this);
        this._onClickOnReturn = this._onClickOnReturn.bind(this);

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const data = await this.rpc("/fleet_monitoring/data");
        Object.assign(this.state, {
            readyDrivers: data.ready_drivers ?? 0,
            notReadyDrivers: data.not_ready_drivers ?? 0,
            simExpiredDrivers: data.sim_expired_drivers ?? 0,
            competencyNeeded: data.competency_needed ?? 0,
            competencyNeededIds: data.competency_needed_ids ?? [],
            standbyVehicles: data.standby_vehicles ?? 0,
            onDeliveryVehicles: data.on_delivery_vehicles ?? 0,
            onReturnVehicles: data.on_return_vehicles ?? 0,
            today: data.current_date ?? null,
        });
    }

    _companyFilter() {
        const companyService = this.env.services.company;
        const companyIds = Object.values(companyService.allowedCompanies || {}).map((c) => c.id);
        return companyIds.length ? [["company_id", "in", companyIds]] : [];
    }

    navigateToDrivers(domain = []) {
        const baseDomain = [["is_driver", "=", true]];
        const companyDomain = this._companyFilter();
        const newDomain = baseDomain.concat(domain, companyDomain);

        this.action.doAction({
            name: "Drivers",
            type: "ir.actions.act_window",
            res_model: "res.partner",
            view_mode: "tree,form",
            views: [[false, "tree"], [false, "form"]],
            domain: newDomain,
        });
    }

    navigateToVehicles(domain = []) {
        const companyDomain = this._companyFilter();
        const newDomain = domain.concat(companyDomain);

        this.action.doAction({
            name: "Fleet Vehicles",
            type: "ir.actions.act_window",
            res_model: "fleet.vehicle",
            view_mode: "tree,form",
            views: [[false, "tree"], [false, "form"]],
            domain: newDomain,
        });
    }

    _onClickReadyDrivers() {
        this.navigateToDrivers([["availability", "=", "Ready"]]);
    }

    _onClickNotReadyDrivers() {
        this.navigateToDrivers([["availability", "!=", "Ready"]]);
    }

    _onClickSimExpired() {
        this.navigateToDrivers([["is_license_expiring", "=", true]]);
    }

    _onClickCompetency() {
        if (this.state.competencyNeededIds.length) {
            this.navigateToDrivers([["id", "in", this.state.competencyNeededIds]]);
        } else {
            this.navigateToDrivers();
        }
    }

    _onClickStandbyVehicles() {
        this.navigateToVehicles([
            ["vehicle_status", "=", "ready"],
            ["last_status_description_id.name_description", "ilike", "Ready for Use"]
        ]);
    }

    _onClickOnDelivery() {
        this.navigateToVehicles([["vehicle_status", "=", "on_going"]]);
    }

    _onClickOnReturn() {
        this.navigateToVehicles([["vehicle_status", "=", "on_return"]]);
    }
}

FleetMonitoring.template = "fleet.Monitoring";
registry.category("actions").add("fleet_monitoring", FleetMonitoring);

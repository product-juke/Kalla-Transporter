/** @odoo-module  **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";


export class DoMonitoring extends Component {
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
            pending_approval_dos_by_spv: 0,
            pending_approval_dos_by_cashier: 0,
            pending_approval_dos_by_adh: 0,
            pending_approval_dos_by_kacab: 0,
            pending_approval_dos_by_delivery_document: 0,
            done_dos: 0,
            unmatch_dos: 0,
            match_dos: 0,
            ongoing_dos: 0,
            onreturn_dos: 0,
            line_not_created_dos: 0,
            cancel_dos: 0,
            pending_approval_bop_by_adh: 0,
            pending_approval_bop_by_kacab: 0,
//            trans_vehicle_count_ready: 0,
//            trans_vehicle_count_ready_on_book: 0,
//            trans_vehicle_count_on_going: 0,
//            trans_vehicle_count_on_return: 0,
//            trans_vehicle_count_not_ready: 0,
//            vli_vehicle_count_ready: 0,
//            vli_vehicle_count_ready_on_book: 0,
//            vli_vehicle_count_on_going: 0,
//            vli_vehicle_count_on_return: 0,
//            vli_vehicle_count_not_ready: 0,
//            truck_vehicle_count_ready: 0,
//            truck_vehicle_count_ready_on_book: 0,
//            truck_vehicle_count_on_going: 0,
//            truck_vehicle_count_on_return: 0,
//            truck_vehicle_count_not_ready: 0,
        });

        this._onClickTotalDO = this._onClickTotalDO.bind(this);
        this._onClickPendingDO = this._onClickPendingDO.bind(this);
        this._onClickPendingApprovalDOBySPV = this._onClickPendingApprovalDOBySPV.bind(this);
        this._onClickPendingApprovalDOByCashier = this._onClickPendingApprovalDOByCashier.bind(this);
        this._onClickPendingApprovalDOByADH = this._onClickPendingApprovalDOByADH.bind(this);
        this._onClickPendingApprovalDOByKacab = this._onClickPendingApprovalDOByKacab.bind(this);
        this._onClickPendingApprovalDOByDocDelivery = this._onClickPendingApprovalDOByDocDelivery.bind(this);
        this._onClickDoneDO = this._onClickDoneDO.bind(this);
        this._onClickUnmatchDO = this._onClickUnmatchDO.bind(this);
        this._onClickMatchDO = this._onClickMatchDO.bind(this);
        this._onClickOnGoingDO = this._onClickOnGoingDO.bind(this);
        this._onClickOnReturnDO = this._onClickOnReturnDO.bind(this);
        this._onClickCancelDO = this._onClickCancelDO.bind(this);
        this._onClickPendingApprovalBOPByADH = this._onClickPendingApprovalBOPByADH.bind(this);
        this._onClickPendingApprovalBOPByKacab = this._onClickPendingApprovalBOPByKacab.bind(this);
        onWillStart(async () => {
            await this.loadData();
        });

//        onMounted(() => {
//            setTimeout(() => this.renderCharts(), 1000);
//        });
    }

    async loadData() {
        const data = await this.rpc("/do_monitoring/data");
        console.log('data => ', data)
        Object.assign(this.state, data);
        this.state.pending_approval_dos_by_cashier = data.pending_approval_dos_by_cashier ?? '-'
        this.state.pending_approval_dos_by_spv = data.pending_approval_dos_by_spv ?? '-'
//        this.renderCharts();
    }


    navigateToFleetDO(domain = []) {
        const companyService = this.env.services.company;

        // ambil semua company_id dalam bentuk array of ids
        const company_ids = Object.values(companyService.allowedCompanies || {}).map(c => c.id);

        console.log('company_ids', company_ids)
        // tambahkan filter company
        const newDomain = domain.concat([["company_id", "=", company_ids]]);

        this.action.doAction({
            name: "Delivery Orders",
            type: "ir.actions.act_window",
            res_model: "fleet.do",
            view_mode: "list",
            views: [[false, "list"], [false, "form"]],
            domain: newDomain,
        });
    }

    //  Parameter role belum dibutuhkan/digunakan untuk apapun
    navigateToBopList(domain = [], role = '') {
        const companyService = this.env.services.company;

        // ambil semua company_id dalam bentuk array of ids
        const company_ids = Object.values(companyService.allowedCompanies || {}).map(c => c.id);

        console.log('company_ids', company_ids)
        // tambahkan filter company
        const newDomain = domain.concat([["fleet_do_id.company_id", "=", company_ids]]);

        this.action.doAction({
            name: "Delivery Orders",
            type: "ir.actions.act_window",
            res_model: 'bop.line',
            view_mode: "list",
            views: [[false, "list"], [false, "form"]],
            domain: newDomain,
            context: {
                group_by: ['fleet_do_id']
            }
        });
    }


    _onClickTotalDO() {
        this.navigateToFleetDO();
    }

    _onClickPendingDO() {
        this.navigateToFleetDO([["state", "=", "draft"],["vehicle_id", "=", null], ["status_do", "=", "DO Unmatch"]]);
    }

    _onClickPendingApprovalDOBySPV() {
        this.navigateToFleetDO([["vehicle_id", "!=", null], ["status_do", "=", "DO Draft"],["state", "=", "to_approve"]]);
    }

    _onClickPendingApprovalDOByCashier() {
        this.navigateToBopList([["fleet_do_id.vehicle_id", "!=", null], ["fleet_do_id.status_do", "=", "DO Match"],["fleet_do_id.state", "=", "approved_operation_spv"]]);
    }

    _onClickPendingApprovalDOByADH() {
        this.navigateToBopList([["fleet_do_id.vehicle_id", "!=", null], ["fleet_do_id.status_do", "=", "DO Match"],["fleet_do_id.state", "=", "approved_cashier"]]);
    }

    _onClickPendingApprovalDOByKacab() {
        this.navigateToBopList([["fleet_do_id.vehicle_id", "!=", null], ["fleet_do_id.status_do", "=", "DO Match"],["fleet_do_id.state", "=", "approved_adh"]], 'KACAB');
    }

    _onClickPendingApprovalDOByDocDelivery() {
//        this.navigateToFleetDO([["vehicle_id", "!=", null], ["status_do", "=", "DO Match"],["status_delivery", "!=", "good_receive"]]);
        this.navigateToFleetDO([["vehicle_id", "!=", null], ["status_do", "=", "DO Match"],["state", "=", "approved_by_kacab"]]);
    }

    _onClickDoneDO() {
        this.navigateToFleetDO([["state", "=", "done"], ["status_do", "=", "DO Match"]]);
    }
    _onClickUnmatchDO() {
        this.navigateToFleetDO([["status_do", "=", "DO Unmatch"]]);
    }
    _onClickMatchDO() {
        this.navigateToFleetDO([["status_do", "=", "DO Match"], ['status_document_status', 'in', ['Draft', 'draft']]]);
    }
    _onClickOnGoingDO() {
        this.navigateToFleetDO([["status_delivery", "=", "on_going"]]);
    }
    _onClickOnReturnDO() {
        this.navigateToFleetDO([["status_delivery", "=", "on_return"]]);
    }
    _onClickCancelDO() {
        this.navigateToFleetDO([["state", "=", "cancel"]]);
    }
    _onClickPendingApprovalBOPByADH() {
        this.navigateToBopList([['fleet_do_id.state', '=', 'done'], ["state", "=", "approved_cashier"],["is_settlement", "=", true]]);
    }
    _onClickPendingApprovalBOPByKacab() {
        this.navigateToBopList([['fleet_do_id.state', '=', 'done'], ["state", "=", "approved_adh"],["is_settlement", "=", true]]);
    }
}

console.log("🚗 DoMonitoring loaded");
DoMonitoring.template = "do.Monitoring";
registry.category("actions").add("do_monitoring", DoMonitoring);

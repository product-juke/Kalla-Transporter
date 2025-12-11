/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class SoMonitoring extends Component {
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        className: { type: String, optional: true },
        globalState: { type: Object, optional: true },
    };

    setup() {
        this.actionService = useService("action");
        this.rpc = useService("rpc");
        this.state = useState({
            total_so: 0,
            draft_so: 0,
            confirm_so: 0,
            without_do_so: 0,
            with_do_so: 0,
            done_so_with_done_do: 0,
        });

        this._onClickTotalSO = this._onClickTotalSO.bind(this);
        this._onClickDraftSO = this._onClickDraftSO.bind(this);
        this._onClickConfirmSO = this._onClickConfirmSO.bind(this);
        this._onClickWithoutDO = this._onClickWithoutDO.bind(this);
        this._onClickWithDO = this._onClickWithDO.bind(this);
        this._onClickCompletedSO = this._onClickCompletedSO.bind(this);

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const data = await this.rpc("/so_monitoring/data");
        Object.assign(this.state, data);
    }

    async navigateToSaleOrders(domain = []) {
        const companyService = this.env.services.company;
        const company_ids = Object.values(companyService.allowedCompanies || {}).map((c) => c.id);
        const newDomain = company_ids.length ? domain.concat([["company_id", "in", company_ids]]) : domain;

        const baseAction = await this.actionService.loadAction(
            "jst_demo_kalla_bju_transporter.sale_order_transporter_action"
        );

        const actionContext = {
            ...(baseAction.context || {}),
            search_default_my_quotation: 0,
        };

        const actionToExecute = {
            ...baseAction,
            domain: newDomain,
            context: actionContext,
        };

        this.actionService.doAction(actionToExecute);
    }

    _onClickTotalSO() {
        this.navigateToSaleOrders();
    }

    _onClickDraftSO() {
        this.navigateToSaleOrders([["state", "=", "draft"]]);
    }

    _onClickConfirmSO() {
        this.navigateToSaleOrders([["state", "=", "sale"]]);
    }

    _onClickWithoutDO() {
        this.navigateToSaleOrders([["order_line.do_id", "=", false]]);
    }

    _onClickWithDO() {
        this.navigateToSaleOrders([["order_line.do_id", "!=", false]]);
    }

    _onClickCompletedSO() {
        this.navigateToSaleOrders([["state", "=", "done"], ["order_line.do_id.state", "=", "done"]]);
    }
}

SoMonitoring.template = "so.Monitoring";
registry.category("actions").add("so_monitoring", SoMonitoring);

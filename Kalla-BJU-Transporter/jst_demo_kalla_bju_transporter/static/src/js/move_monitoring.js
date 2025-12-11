/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class InvoiceMonitoringDashboard extends Component {
    static template = "invoice_monitoring.Dashboard";

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({
            stats: {},
            domains: {},
            loading: true
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            this.state.loading = true;

            // Ambil allowed_company_ids dari context
            const allowedCompanyIds = this.env.services.user.context.allowed_company_ids;
            console.log("Allowed companies:", allowedCompanyIds);

            // Gunakan method baru yang mengembalikan data sinkron
            const data = await this.rpc('/web/dataset/call_kw', {
                model: 'invoice.monitoring',
                method: 'get_synchronized_data',
                args: [allowedCompanyIds],
                kwargs: {}
            });

            console.log('Synchronized data => ', data);

            this.state.stats = data.stats;
            this.state.domains = data.domains;

        } catch (error) {
            console.error("Error loading dashboard data:", error);
            // Set default stats if error occurs
            this.state.stats = {
                done_not_invoiced: 0,
                draft_invoices: 0,
                done_not_paid: 0,
                done_not_sent: 0,
                paid_invoices: 0
            };
            this.state.domains = {};
        } finally {
            this.state.loading = false;
        }
    }

    async onCardClick(filterType) {
        try {
            console.log("Card clicked:", filterType);

            // Get action configuration
            const actionData = this.getActionForFilter(filterType);

            if (actionData) {
                console.log("Opening action with domain:", actionData.domain);
                // Open the action in a new view
                this.action.doAction(actionData);
            }
        } catch (error) {
            console.error("Error opening detail view:", error);
        }
    }

    getActionForFilter(filterType) {
        // Ambil allowed_company_ids yang sama dengan yang digunakan di backend
        const allowedCompanyIds = this.env.services.user.context.allowed_company_ids;
        console.log("Using allowed companies for action:", allowedCompanyIds);

        // Base domain untuk invoice - HARUS SAMA dengan backend
        const baseInvoiceDomain = [
            ['move_type', 'in', ['out_invoice', 'out_refund']],
            ["company_id", "in", allowedCompanyIds]
        ];

        // Base domain untuk sale order - HARUS SAMA dengan backend
        const baseSaleDomain = [
            ["company_id", "in", allowedCompanyIds]
        ];

        switch (filterType) {
            case 'draft_invoices':
                return {
                    name: 'Draft Invoices',
                    type: 'ir.actions.act_window',
                    res_model: 'account.move',
                    view_mode: 'tree,form',
                    views: [[false, 'tree'], [false, 'form']],
                    // Domain SAMA persis dengan backend
                    domain: [...baseInvoiceDomain, ['state', '=', 'draft']],
                    context: {
                        'search_default_group_by_state': 1,
                        'default_move_type': 'out_invoice'
                    },
                    target: 'current'
                };

            case 'done_not_paid':
                return {
                    name: 'Posted Invoices - Not Paid',
                    type: 'ir.actions.act_window',
                    res_model: 'account.move',
                    view_mode: 'tree,form',
                    views: [[false, 'tree'], [false, 'form']],
                    // Domain SAMA persis dengan backend
                    domain: [
                        ...baseInvoiceDomain,
                        ['state', '=', 'posted'],
                        ['payment_state', 'in', ['not_paid', 'partial']]
                    ],
                    context: {
                        'search_default_group_by_payment_state': 1,
                        'default_move_type': 'out_invoice'
                    },
                    target: 'current'
                };

            case 'done_not_sent':
                return {
                    name: 'Posted Invoices - Not Sent',
                    type: 'ir.actions.act_window',
                    res_model: 'account.move',
                    view_mode: 'tree,form',
                    views: [[false, 'tree'], [false, 'form']],
                    // Domain SAMA persis dengan backend - menggunakan date_sent_to_customer
                    domain: [
                        ...baseInvoiceDomain,
                        ['state', '=', 'posted'],
                        ['date_sent_to_customer', '=', false]  // SAMA dengan backend
                    ],
                    context: {
                        'search_default_group_by_state': 1,
                        'default_move_type': 'out_invoice'
                    },
                    target: 'current'
                };

            case 'paid_invoices':
                return {
                    name: 'Paid Invoices',
                    type: 'ir.actions.act_window',
                    res_model: 'account.move',
                    view_mode: 'tree,form',
                    views: [[false, 'tree'], [false, 'form']],
                    // Domain SAMA persis dengan backend
                    domain: [
                        ...baseInvoiceDomain,
                        ['state', '=', 'posted'],
                        ['payment_state', '=', 'paid']
                    ],
                    context: {
                        'search_default_group_by_payment_state': 1,
                        'default_move_type': 'out_invoice'
                    },
                    target: 'current'
                };

            case 'done_not_invoiced':
                return {
                    name: 'Sales Orders - To Invoice',
                    type: 'ir.actions.act_window',
                    res_model: 'sale.order',
                    view_mode: 'tree,form',
                    views: [
                       [this.state.stats.view_ids.tree, 'tree'],
                       [this.state.stats.view_ids.form, 'form']
                    ],
                    // Domain SAMA persis dengan backend
                    domain: [
                        ...baseSaleDomain,
                        ['state', '=', 'sale'],
                        ['invoice_status', 'in', ['to invoice']]
                    ],
                    context: {
                        'search_default_group_by_invoice_status': 1,
                        'default_state': 'sale'
                    },
                    target: 'current'
                };

            case 'doc_delivery':
                return {
                    name: 'Doc Delivery',
                    type: 'ir.actions.act_window',
                    res_model: 'fleet.do',
                    view_mode: 'tree,form',
                    views: [[false, 'tree'], [false, 'form']],
                    // Domain SAMA persis dengan backend
                    domain: [
                        ...baseSaleDomain,
                        ['vehicle_id', '!=', null],
                        ['status_do', '=', 'DO Match'],
                        ['state', '=', 'approved_by_kacab']
                    ],
                    context: {
//                        'search_default_group_by_invoice_status': 1,
                    },
                    target: 'current'
                };

            default:
                return null;
        }
    }

    getCardTitle(filterType) {
        const titles = {
            'done_not_invoiced': 'SO Done - Belum Invoice',
            'draft_invoices': 'Invoice Draft',
            'done_not_sent': 'Invoice Done - Belum Dikirim',
            'done_not_paid': 'Invoice Sudah Dikirim - Belum Terbayar',
            'paid_invoices': 'Invoice Paid',
            'doc_delivery': 'Doc Delivery',
        };
        return titles[filterType] || '';
    }

    getCardColor(filterType) {
        const colors = {
            'done_not_invoiced': 'bg-warning',
            'draft_invoices': 'bg-secondary',
            'done_not_paid': 'bg-danger',
            'done_not_sent': 'bg-info',
            'paid_invoices': 'bg-success',
            'doc_delivery': 'bg-primary',
        };
        return colors[filterType] || 'bg-primary';
    }

    getCardIcon(filterType) {
        const icons = {
            'done_not_invoiced': 'jst_demo_kalla_bju_transporter/static/src/img/to_invoice.png',
            'draft_invoices': 'jst_demo_kalla_bju_transporter/static/src/img/draft_invoice.png',
            'done_not_paid': 'jst_demo_kalla_bju_transporter/static/src/img/delivered_not_paid.png',
            'done_not_sent': 'jst_demo_kalla_bju_transporter/static/src/img/done_not_delivered.png',
            'paid_invoices': 'jst_demo_kalla_bju_transporter/static/src/img/paid_invoice.png',
            'doc_delivery': 'jst_demo_kalla_bju_transporter/static/src/img/Menunggu Update Surat Jalan oleh Delivery Documen.png',
        };
        return icons[filterType] || 'jst_demo_kalla_bju_transporter/static/src/img/Menunggu Update Surat Jalan oleh Delivery Documen.png';
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('id-ID', {
            style: 'currency',
            currency: 'IDR'
        }).format(amount);
    }

    // Method untuk debug - bisa dihapus di production
    async debugData() {
        const allowedCompanyIds = this.env.services.user.context.allowed_company_ids;
        console.log("=== DEBUG SYNCHRONIZATION ===");
        console.log("Allowed Company IDs:", allowedCompanyIds);
        console.log("Current Stats:", this.state.stats);
        console.log("Current Domains:", this.state.domains);

        // Test manual count untuk verifikasi
        for (const [filterType, domain] of Object.entries(this.state.domains)) {
            if (domain && domain.length > 0) {
                const model = filterType === 'done_not_invoiced' ? 'sale.order' : 'account.move';
                const count = await this.rpc('/web/dataset/call_kw', {
                    model: model,
                    method: 'search_count',
                    args: [domain],
                    kwargs: {}
                });
                console.log(`${filterType} - Stats: ${this.state.stats[filterType]}, Manual Count: ${count}`);
            }
        }
        console.log("=== END DEBUG ===");
    }
}

registry.category("actions").add("invoice_monitoring_dashboard", InvoiceMonitoringDashboard);
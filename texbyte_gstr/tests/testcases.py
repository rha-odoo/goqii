from odoo.tests import common
from odoo.tests import tagged
from datetime import date


@tagged('post_install', '-at_install')
class GSTRTestcases(common.SingleTransactionCase):
    def setUp(self):
        super(GSTRTestcases, self).setUp()
        country = self.env['res.country'].search([('code', '=', 'IN')], limit=1)
        state = self.env['res.country.state'].search([('country_id', '=', country.id)], limit=1)
        cmp = self.env.company
        cmp.update({'country_id': country.id, 'state_id': state.id})
        other_state = self.env['res.country.state'].search([('country_id', '=', country.id), ('id', '!=', state.id), ('l10n_in_tin', '=', '12')], limit=1)  # Arunachal Pradesh
        self.fiscal_export = self.env['account.fiscal.position'].search([('name', '=', 'Export')])
        self.partner_unreg_intra = self.env['res.partner'].create({'name': 'Cx1', 'state_id': state.id})
        self.partner_reg_intra = self.env['res.partner'].create(
            {'name': 'Cx2', 'vat': '32ASDFG1234A1Z5', 'state_id': state.id})
        self.partner_unreg_inter = self.env['res.partner'].create(
            {'name': 'Cx2', 'state_id': other_state.id})
        self.partner_reg_inter = self.env['res.partner'].create(
            {'name': 'Cx2', 'vat': '12GEOPS0823BBZH', 'state_id': other_state.id})
        self.vendor_unreg_intra = self.env['res.partner'].create({'name': 'Vx1', 'state_id': state.id})
        self.vendor_reg_intra = self.env['res.partner'].create({'name': 'Vx2', 'vat': '32ASDFF1233A1Z5', 'state_id': state.id})
        self.vendor_unreg_inter = self.env['res.partner'].create({'name': 'Vx1', 'state_id': other_state.id})
        self.vendor_reg_inter = self.env['res.partner'].create(
            {'name': 'Vx2', 'vat': '33BSFFG2534A1Z5', 'state_id': other_state.id})
        self.vendor_import = self.env['res.partner'].create({'name': 'V_IMP', 'state_id': other_state.id, 'property_account_position_id': self.fiscal_export.id})
        self.uom_unit = self.env.ref('uom.product_uom_unit')
        self.gst5 = self.env['account.tax'].search([('name', '=', 'GST 5%'), ('type_tax_use', '=', 'sale')])
        self.igst5 = self.env['account.tax'].search([('name', '=', 'IGST 5%'), ('type_tax_use', '=', 'sale')])
        self.exempt = self.env['account.tax'].search([('name', '=', 'Exempt Sale'), ('type_tax_use', '=', 'sale')])
        self.nil = self.env['account.tax'].search([('name', '=', 'Nil Rated'), ('type_tax_use', '=', 'sale')])
        #self.import_vendor_journal = self.env['account.journal'].create({
        #    'move_type': 'purchase',
        #    'name': 'Import Bill',
        #    'code': 'BILLIMP',
        #    'company_id': cmp.id,
        #    'l10n_in_gstin_partner_id': cmp.id,
        #    'sequence': 50,
        #})
        today = date.today()
        self.currency_usd = self.env['res.currency'].search([('name', '=', 'USD')])
        self.currency_usd_rate = self.env['res.currency.rate'].create({
            'rate': float(1 / 75),
            'currency_id': self.currency_usd.id,
        })

        self.product1 = self.env['product.product'].create({
            'name': 'Product A',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'type': 'consu',
            'categ_id': self.env.ref('product.product_category_all').id,
            'taxes_id': self.gst5,
            'supplier_taxes_id': self.gst5,
            'list_price': 100.0,
            'standard_price': 50.0,

        })
        self.product2 = self.env['product.product'].create({
            'name': 'Product B',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'type': 'consu',
            'categ_id': self.env.ref('product.product_category_all').id,
            'taxes_id': self.gst5,
            'supplier_taxes_id': self.gst5,
            'list_price': 100.0,
            'standard_price': 50.0,
        })
        self.service1 = self.env['product.product'].create({
            'name': 'Service 1',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'type': 'service',
            'categ_id': self.env.ref('product.product_category_all').id,
            'taxes_id': self.gst5,
            'supplier_taxes_id': self.gst5,
            'list_price': 100.0,
            'standard_price': 50.0,
        })
        self.service2 = self.env['product.product'].create({
            'name': 'Service 2',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'type': 'service',
            'categ_id': self.env.ref('product.product_category_all').id,
            'taxes_id': self.igst5,
            'supplier_taxes_id': self.gst5,
            'list_price': 100.0,
            'standard_price': 50.0,
        })
        self.product_line_vals_1 = {
            'name': self.product1.name,
            'product_id': self.product1.id,
            'product_uom_id': self.product1.uom_id.id,
            'quantity': 10.0,
            'discount': 0.0,
            'tax_ids': self.gst5,
            'price_unit': self.product1.list_price,
            'price_subtotal': 1050.0,
            'price_total': 1000.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 1050.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_2 = {
            'name': self.product2.name,
            'product_id': self.product2.id,
            'product_uom_id': self.product2.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.igst5,
            'price_unit': 100.0,
            'price_subtotal': 2000.0,
            'price_total': 2100.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 2100.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_3 = {
            'name': self.product2.name,
            'product_id': self.product2.id,
            'product_uom_id': self.product2.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.exempt,
            'price_unit': 100.0,
            'price_subtotal': 2000.0,
            'price_total': 2000.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 20000.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_4 = {
            'name': self.product2.name,
            'product_id': self.product2.id,
            'product_uom_id': self.product2.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.nil,
            'price_unit': 100.0,
            'price_subtotal': 2000.0,
            'price_total': 2000.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 2000.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_discount = {
            'name': self.product2.name,
            'product_id': self.product2.id,
            'product_uom_id': self.product2.uom_id.id,
            'quantity': 10.0,
            'price_unit': 100.0,
            'discount': 20.0,
            'tax_ids': self.igst5,
            'price_subtotal': 800.0,
            'price_total': 840.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 840.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_discount_import_export = {
            'name': self.product2.name,
            'product_id': self.product2.id,
            'product_uom_id': self.product2.uom_id.id,
            'quantity': 20.0,
            'price_unit': 4.0,
            'discount': 10.0,
            'tax_ids': self.igst5,
            'price_subtotal': 72.0,
            'price_total': 75.6,
            'currency_id': self.currency_usd.id,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 75.6,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.service_line_vals_1_sale = {
            'name': self.service1.name,
            'product_id': self.service1.id,
            'product_uom_id': self.service1.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.gst5,
            'price_unit': 100.0,
            'price_subtotal': 2000.0,
            'price_total': 2100.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 2100.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.service_line_vals_2_sale = {
            'name': self.service2.name,
            'product_id': self.service2.id,
            'product_uom_id': self.service1.uom_id.id,
            'quantity': 10.0,
            'discount': 0.0,
            'tax_ids': self.igst5,
            'price_unit': 100.0,
            'price_subtotal': 1000.0,
            'price_total': 1050.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 1050.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_1_purchase = {
            'name': self.product1.name,
            'product_id': self.product1.id,
            'product_uom_id': self.product1.uom_id.id,
            'quantity': 10.0,
            'discount': 0.0,
            'tax_ids': self.gst5,
            'price_unit': 50.0,
            'price_subtotal': 500.0,
            'price_total': 525.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 525.0,
            'credit': 0.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_2_purchase = {
            'name': self.product2.name,
            'product_id': self.product2.id,
            'product_uom_id': self.product2.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.igst5,
            'price_unit': 50.0,
            'price_subtotal': 1000.0,
            'price_total': 1050.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 1050.0,
            'credit': 0.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_2_import_export = {
            'name': self.product2.name,
            'product_id': self.product2.id,
            'product_uom_id': self.product2.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.igst5,
            'price_unit': 2,
            'price_subtotal': 40,
            'price_total': 42.0,
            'currency_id': self.currency_usd.id,
            'amount_currency': 0.0,
            'debit': 42.0,
            'credit': 0.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.service_line_vals_1_purchase = {
            'name': self.service1.name,
            'product_id': self.service1.id,
            'product_uom_id': self.service1.uom_id.id,
            'quantity': 10.0,
            'discount': 0.0,
            'tax_ids': self.gst5,
            'price_unit': 50.0,
            'price_subtotal': 500.0,
            'price_total': 525.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 525.0,
            'credit': 0.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.service_line_vals_2_purchase = {
            'name': self.service2.name,
            'product_id': self.service2.id,
            'product_uom_id': self.service2.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.igst5,
            'price_unit': 50.0,
            'price_subtotal': 1000.0,
            'price_total': 1050.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 1050.0,
            'credit': 0.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.service_line_vals_2_import_export = {
            'name': self.service2.name,
            'product_id': self.service2.id,
            'product_uom_id': self.service2.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.igst5,
            'price_unit': 3,
            'price_subtotal': 60.0,
            'price_total': 63.0,
            'currency_id': self.currency_usd.id,
            'amount_currency': 0.0,
            'debit': 63.0,
            'credit': 0.0,
            'date_maturity': False,
            'tax_exigible': True,
        }

        self.b2b = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_reg_inter.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_2),
                (0, None, self.service_line_vals_2_sale),
            ]
        })
        self.b2c = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_unreg_intra.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_1),
                (0, None, self.service_line_vals_1_sale),
            ]
        })
        self.sez_wp_tax = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_reg_inter,
            'l10n_in_gst_treatment': 'special_economic_zone',
            'invoice_line_ids': [
                (0, None, self.product_line_vals_2),
                (0, None, self.service_line_vals_2_sale),
                (0, None, self.product_line_vals_discount),

            ]
        })
        self.deemed = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_reg_inter,
            'currency_id': self.currency_usd.id,
            'l10n_in_gst_treatment': 'deemed_export',
            'invoice_line_ids': [
                (0, None, self.product_line_vals_2_import_export),
                (0, None, self.product_line_vals_discount_import_export),
            ]
        })
        self.credit_inv = self.env['account.move'].create({
            'move_type': 'out_refund',
            'invoice_date': today,
            'partner_id': self.partner_reg_inter,
            'l10n_in_gst_treatment': 'regular',
            'invoice_line_ids': [
                (0, None, self.product_line_vals_2),
                (0, None, self.service_line_vals_2_sale),
            ]
        })
        self.debit_inv = self.env['account.move'].create({
            'move_type': 'in_refund',
            'invoice_date': today,
            'partner_id': self.vendor_reg_intra,
            'l10n_in_gst_treatment': 'regular',
            'invoice_line_ids': [
                (0, None, self.product_line_vals_1_purchase),
            ]
        })

        # 5.outward tax not payable todo:zero rated, credit
        self.exempt_nil_5 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_unreg_intra,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_3),
                (0, None, self.product_line_vals_4),
            ]
        })

        self.supply_sez_wop_5 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_reg_inter,
            'l10n_in_gst_treatment': 'special_economic_zone',
            'invoice_line_ids': [
                (0, None, self.product_line_vals_4),
            ]
        })

        # ITC
        self.inwrd_reg = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': today,
            'partner_id': self.vendor_reg_intra,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_1_purchase),
                (0, None, self.service_line_vals_1_purchase),
            ]
        })
        self.inwrd_import_other = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': today,
            'partner_id': self.vendor_import,
            'currency_id': self.currency_usd.id,
            'l10n_in_gst_treatment': 'overseas',
            'invoice_line_ids': [
                (0, None, self.product_line_vals_2_import_export),
                (0, None, self.product_line_vals_2_import_export),
                (0, None, self.service_line_vals_2_import_export),
            ]
        })
        self.inwrd_not_reg = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': today,
            'partner_id': self.vendor_unreg_inter,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_1_purchase),
                (0, None, self.service_line_vals_1_purchase),
            ]
        })

        #gstr1
        self.product_large = self.env['product.product'].create({
            'name': 'Product Large',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'type': 'consu',
            'categ_id': self.env.ref('product.product_category_all').id,
            'taxes_id': self.gst5,
            'supplier_taxes_id': self.gst5,
            'list_price': 50000.0,
            'standard_price': 40000.0,

        })
        self.service_large = self.env['product.product'].create({
            'name': 'Service Large',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'type': 'service',
            'categ_id': self.env.ref('product.product_category_all').id,
            'taxes_id': self.gst5,
            'supplier_taxes_id': self.gst5,
            'list_price': 50000.0,
            'standard_price': 40000.0,

        })
        self.product_line_vals_large = {
            'name': self.product_large.name,
            'product_id': self.product_large.id,
            'product_uom_id': self.product_large.uom_id.id,
            'quantity': 6.0,
            'discount': 0.0,
            'tax_ids': self.gst5,
            'price_unit': self.product_large.list_price,
            'price_subtotal': 315000.0,
            'price_total': 300000.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 315000.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.service_line_vals_large = {
            'name': self.service_large.name,
            'product_id': self.service_large.id,
            'product_uom_id': self.service_large.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.gst5,
            'price_unit': 100.0,
            'price_subtotal': 2000.0,  # add
            'price_total': 2100.0,  # add
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 2100.0,  # add
            'date_maturity': False,
            'tax_exigible': True,
        }

        # if company_sate not equal to partner state_id if partner has state_id else True
        self.b2cl_large = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_unreg_inter.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_large),
            ]
        })

        # Sale to unregistered customers other than B2CL (unreg. intra-state for any amount + unreg. inter-state <= 2.5 lakh)
        # b2c is one with itra state define inter state < 25000 todo: writing directly to xls
        self.b2cs_inter = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_unreg_inter.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_2),
                (0, None, self.service_line_vals_2_sale),
            ]
        })
        # self.sorted_invoices.filtered(lambda p: not p.partner_id.vat and not ((p.company_id.state_id != p.partner_id.state_id if p.partner_id.state_id else True) and p.amount_untaxed_signed > B2CL_INVOICE_AMT_LIMIT))
        # not calling utility method directly writing to xls todo

        # exempted intra is already posted exempted intra define here aslo writing directly to the report todo
        self.exempt_nil_5 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_unreg_inter.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_3),
                (0, None, self.product_line_vals_4),
            ]
        })

        # credit note registered already posted

        # credit note not registered and invoice amount > 2.5 lakh
        self.credit_unreg_2_5 = self.env['account.move'].create({
            'move_type': 'out_refund',
            'invoice_date': today,
            'partner_id': self.partner_unreg_inter.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_large),
            ]
        })

        # exports declared already difine reversal exports
        # HSN writing directly to report here todo

        #gstr2
        self.product_line_vals_3_purchase = {
            'name': self.product2.name,
            'product_id': self.product2.id,
            'product_uom_id': self.product2.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.exempt,
            'price_unit': 50.0,
            'price_subtotal': 1000.0,
            'price_total': 1000.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 10000.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_4_purchase = {
            'name': self.product2.name,
            'product_id': self.product2.id,
            'product_uom_id': self.product2.uom_id.id,
            'quantity': 20.0,
            'discount': 0.0,
            'tax_ids': self.nil,
            'price_unit': 50.0,
            'price_subtotal': 1000.0,
            'price_total': 1000.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 0.0,
            'credit': 1000.0,
            'date_maturity': False,
            'tax_exigible': True,
        }
        self.product_line_vals_large_purhase = {
            'name': self.product_large.name,
            'product_id': self.product_large.id,
            'product_uom_id': self.product_large.uom_id.id,
            'quantity': 7.0,
            'discount': 0.0,
            'tax_ids': self.igst5,
            'price_unit': self.product_large.standard_price,
            'price_subtotal': 294000.0,
            'price_total': 280000.0,
            'currency_id': False,
            'amount_currency': 0.0,
            'debit': 294000.0,
            'credit': 0.0,
            'date_maturity': False,
            'tax_exigible': True,
        }

        # already defined 1 in gstrn add one more
        self.b2b_inward = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': today,
            'partner_id': self.vendor_reg_inter.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_2_purchase),
            ]
        })

        self.b2bu_inward = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': today,
            'partner_id': self.vendor_unreg_inter.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_2_purchase),
            ]
        })

        # import of service todo

        # import of goods todo

        # for both importstry to use utility method if possible

        # debit note registered defined already create debit note unregistered Cx
        self.debit_inv_unreg = self.env['account.move'].create({
            'move_type': 'in_refund',
            'invoice_date': today,
            'partner_id': self.vendor_unreg_inter,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_large_purhase),
            ]
        })

        #xempted/nil rated writing directly to report
        self.exempt_nil_intra_in = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': today,
            'partner_id': self.vendor_unreg_intra.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_3_purchase),
                (0, None, self.product_line_vals_4_purchase),
            ]
        })
        self.exempt_nil_intra_in = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': today,
            'partner_id': self.vendor_reg_intra.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_3_purchase),
                (0, None, self.product_line_vals_4_purchase),
            ]
        })
        self.exempt_nil_intra_in = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': today,
            'partner_id': self.vendor_unreg_inter.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_3_purchase),
                (0, None, self.product_line_vals_4_purchase),
            ]
        })
        self.exempt_nil_intra_in = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': today,
            'partner_id': self.vendor_reg_inter.id,
            'invoice_line_ids': [
                (0, None, self.product_line_vals_3_purchase),
                (0, None, self.product_line_vals_4_purchase),
            ]
        })

        # hsn writing directly to report try to use the existing utitlity

        # debit note unregistered todo

        self.b2b.action_post()
        self.b2c.action_post()
        #self.zero_rated.action_post()
        self.sez_wp_tax.action_post()
        self.deemed.action_post()
        self.credit_inv.action_post()
        self.debit_inv.action_post()
        self.exempt_nil_5.action_post()
        self.supply_sez_wop_5.action_post()
        self.inwrd_reg.action_post()
        self.inwrd_import_other.action_post()
        self.inwrd_not_reg.action_post()
        self.b2cl_large.action_post()
        self.b2cs_inter.action_post()
        self.credit_unreg_2_5.action_post()
        self.b2b_inward.action_post()
        self.b2bu_inward.action_post()
        self.debit_inv_unreg.action_post()

        print("B2B: Registered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.b2b.name, self.b2b.fiscal_position_id.name, self.b2b.l10n_in_gst_treatment))
        self.print_inv_lines(self.b2b)
        print("B2C: UnRegistered Intrastate, Number: %s, FiscalPos: %s, Export type: %s" % (self.b2c.name, self.b2c.fiscal_position_id.name, self.b2c.l10n_in_gst_treatment))
        self.print_inv_lines(self.b2c)
        print("Sez With Payment: Registered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.sez_wp_tax.name, self.sez_wp_tax.fiscal_position_id.name, self.sez_wp_tax.l10n_in_gst_treatment))
        self.print_inv_lines(self.sez_wp_tax)
        print("Deemed: Registered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.deemed.name, self.deemed.fiscal_position_id.name, self.deemed.l10n_in_gst_treatment))
        self.print_inv_lines(self.deemed)
        print("Credit: Registered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.credit_inv.name, self.credit_inv.fiscal_position_id.name, self.credit_inv.l10n_in_gst_treatment))
        self.print_inv_lines(self.credit_inv)
        print("Debit: Registered Intrastate, Number: %s, FiscalPos: %s, Export type: %s" % (self.debit_inv.name, self.debit_inv.fiscal_position_id.name, self.debit_inv.l10n_in_gst_treatment))
        self.print_inv_lines(self.debit_inv)
        print("Exempt/Nil: UnRegistered Intrastate, Number: %s, FiscalPos: %s, Export type: %s" % (self.exempt_nil_5.name, self.exempt_nil_5.fiscal_position_id.name, self.exempt_nil_5.l10n_in_gst_treatment))
        self.print_inv_lines(self.exempt_nil_5)
        print("Sez Without Pay: Registered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.supply_sez_wop_5.name, self.supply_sez_wop_5.fiscal_position_id.name, self.supply_sez_wop_5.l10n_in_gst_treatment))
        self.print_inv_lines(self.supply_sez_wop_5)
        print("REG Inward: Registered Intrastate, Number: %s, FiscalPos: %s, Export type: %s" % (self.inwrd_reg.name, self.inwrd_reg.fiscal_position_id.name, self.inwrd_reg.l10n_in_gst_treatment))
        self.print_inv_lines(self.inwrd_reg)
        print("IMP: UnRegistered, Number: %s, FiscalPos: %s, Export type: %s" % (self.inwrd_import_other.name, self.inwrd_import_other.fiscal_position_id.name, self.inwrd_import_other.l10n_in_gst_treatment))
        self.print_inv_lines(self.inwrd_import_other)
        print("Inward UnReg: UnRegistered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.inwrd_not_reg.name, self.inwrd_not_reg.fiscal_position_id.name, self.inwrd_not_reg.l10n_in_gst_treatment))
        self.print_inv_lines(self.inwrd_not_reg)
        print("B2CL Large: UnRegistered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.b2cl_large.name, self.b2cl_large.fiscal_position_id.name, self.b2cl_large.l10n_in_gst_treatment))
        self.print_inv_lines(self.b2cl_large)
        print("Credit > 2.5: UnRegistered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.credit_unreg_2_5.name, self.credit_unreg_2_5.fiscal_position_id.name, self.credit_unreg_2_5.l10n_in_gst_treatment))
        self.print_inv_lines(self.credit_unreg_2_5)
        print("B2B Inward: Registered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.b2b_inward.name, self.b2b_inward.fiscal_position_id.name, self.b2b_inward.l10n_in_gst_treatment))
        self.print_inv_lines(self.b2b_inward)
        print("B2BU Inward: UnRegistered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.b2bu_inward.name, self.b2bu_inward.fiscal_position_id.name, self.b2bu_inward.l10n_in_gst_treatment))
        self.print_inv_lines(self.b2bu_inward)
        print("Debit Unreg: UnRegistered Interstate, Number: %s, FiscalPos: %s, Export type: %s" % (self.debit_inv_unreg.name, self.debit_inv_unreg.fiscal_position_id.name, self.debit_inv_unreg.l10n_in_gst_treatment))
        self.print_inv_lines(self.debit_inv_unreg)

    def print_inv_lines(self, inv):
        for line in inv.invoice_line_ids:
            print("Product: {},  Amount: {},  Tax: {},  Total: {}, Currency: {}, rate: {}" .format(line.product_id.name, line.price_subtotal, line.tax_ids.name, line.price_total, line.move_id.currency_id.name, line.move_id.currency_id.rate))

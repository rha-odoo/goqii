from odoo import fields, models, api
import xlwt
import base64
from io import BytesIO
from datetime import datetime

import pdb
import logging
_logger = logging.getLogger(__name__)


class GSTR9Report(models.TransientModel):

    _name = 'texbyte_gstr.report.gstr9'

    # fields to generate xls
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To')

    # fields for download xls
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],
                             default='choose')
    report = fields.Binary('Prepared file', filters='.xls', readonly=True)
    filename = fields.Char('File Name', size=128)

    all_invoices = []
    sorted_invoices = []
    refund_invoices = []
    canceled_invoices = []

    def get_valid_invoices(self):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        # Searching for customer invoices
        from_date = self.date_from
        to_date = self.date_to
        refund_invoice_ids = []

        # Get all invoices except canceled and draft
        all_invoices = self.env['account.move'].search(
            [('invoice_date', '>=', from_date), ('invoice_date', '<=', to_date), ('state', '!=', 'draft')])
        canceled_invoices = all_invoices.filtered(lambda i: i.state == 'cancel')
        # Refund invoices
        refund_invoices = all_invoices.filtered(
            lambda i: i.state != 'cancel' and i.move_type in ('out_refund', 'in_refund'))  # Skip canceled refunds
        # Legitimate invoices -- other than canceled and refund
        invoices = all_invoices.filtered(
            lambda i: i.id not in canceled_invoices.ids + refund_invoices.ids)
        sorted_invoices = invoices.sorted(key=lambda p: (p.invoice_date, p.name))


    def generate_gstr9_report(self):
        #Error handling is not taken into consideraion
        self.ensure_one()
        fp = BytesIO()
        xl_workbook = xlwt.Workbook(encoding='utf-8')

        from_date = self.date_from
        to_date = self.date_to

        # Get the invoices to generate report
        self.get_valid_invoices()

        #call to generate reports in seperate sheets. ie, "4.Outward", "5.Outward", "6.ITC Availed", "17.HSN_out", "18.HSN_in".
        self.outward_tax_payable_report(xl_workbook)
        self.outward_tax_not_payable_report(xl_workbook)
        self.itc_availed(xl_workbook)
        self.hsn_outward(xl_workbook)
        self.hsn_inward(xl_workbook)

        xl_workbook.save(fp)

        out = base64.encodebytes(fp.getvalue())
        self.write({'state': 'choose', 'report': out, 'filename':'gstr9_'+str(from_date)+'-'+str(to_date)+'.xls'})
        return {
            'name': 'GSTR9',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=texbyte_gstr.report.gstr9&id=" + str(self.id) + "&filename_field=filename&field=report&download=true&filename=" + self.filename,
            'target': 'current',
        }

    #Details of advances, inward and outward supplies made during the financial year on which tax is payable
    def outward_tax_payable_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('4.Outward')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500

        ws1.write(row, col + 2, "From:", sub_header_style)
        ws1.write(row, col + 3, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 2, "To:", sub_header_style)
        ws1.write(row, col + 3, self.format_date(self.date_to), sub_header_content_style)
        row += 1

        b2b = {}
        b2c = {}
        inward_rev_charge = {}
        zero_rated = {}
        supply_sez = {}
        deemed_exp = {}
        credit_note = {}
        debit_note = {}

        #B2C in GSTR should be net amount (subtract debit/credit notes)
        b2c_invoices = sorted_invoices.filtered(lambda p: not p.partner_id.vat and p.move_type == 'out_invoice' and p.l10n_in_gst_treatment != 'overseas')  # GST un-registered customers excluding export
        b2c_invoices += refund_invoices.filtered(lambda p: not p.partner_id.vat and p.move_type == 'out_refund' and p.l10n_in_gst_treatment != 'overseas')  # Credit notes of unregistered customers excluding export
        self.summarize_tax_values(b2c_invoices, b2c, lambda p: True if p.tax_ids.name not in ['Exempt Sale', 'Nil Rated'] else False)

        b2b_invoices = sorted_invoices.filtered(lambda p: p.partner_id.vat and p.move_type == 'out_invoice')  # GST registered customers
        self.summarize_tax_values(b2b_invoices, b2b, lambda p: True if p.tax_ids.name not in ['Exempt Sale', 'Nil Rated'] else False)

        inward_reverse_charge_inv = sorted_invoices.filtered(lambda p: p.move_type == 'in_invoice' and p._is_reverse_charge_applicable())  # Inward reverse charge applicable
        self.summarize_tax_values(inward_reverse_charge_inv, inward_rev_charge)

        zero_rated_inv = sorted_invoices.filtered(lambda p: p.move_type == 'out_invoice' and p.l10n_in_gst_treatment in ('overseas',) and p.amount_tax == 0.00)  # Zero rated
        self.summarize_tax_values(zero_rated_inv, zero_rated)

        supply_sezwp_inv = sorted_invoices.filtered(lambda p: p.move_type == 'out_invoice' and p.l10n_in_gst_treatment in ('special_economic_zone', 'overseas') and p.amount_tax != 0.00)  # supply to sez with payment of tax
        self.summarize_tax_values(supply_sezwp_inv, supply_sez)

        deemed_exp_inv = sorted_invoices.filtered(lambda p: p.move_type == 'out_invoice' and p.l10n_in_gst_treatment in ('deemed_export',))   #Deemed exports
        self.summarize_tax_values(deemed_exp_inv, deemed_exp)

        valid_exp_imp_type = ['regular', 'deemed_export', 'overseas', 'special_economic_zone']
        credit_note_inv = refund_invoices.filtered(lambda p: p.move_type == 'out_refund' and p.partner_id.vat and p.l10n_in_gst_treatment in valid_exp_imp_type)  # Credit note
        self.summarize_tax_values(credit_note_inv, credit_note)

        debit_note_inv = refund_invoices.filtered(lambda p: p.move_type == 'in_refund' and p.partner_id.vat and p.l10n_in_gst_treatment in valid_exp_imp_type)  # Debit note
        self.summarize_tax_values(debit_note_inv, debit_note)

        ws1.write_merge(row, row + 1, col + 2, col + 2, "Nature of Supplies", sub_header_style)
        ws1.write_merge(row, row + 1, col + 3, col + 3, "Taxable Value(₹)", sub_header_style)
        ws1.write_merge(row, row, col + 4, col + 7, "Amount in ₹ in all tables", sub_header_style)
        row += 1

        ws1.write(row, col + 4, "Central Tax", sub_header_style)
        ws1.write(row, col + 5, "State Tax/ UT Tax", sub_header_style)
        ws1.write(row, col + 6, "Integrated tax", sub_header_style)
        ws1.write(row, col + 7, "Cess", sub_header_style)
        row += 1

        ws1.write(row, col + 1, "4", sub_header_style)
        ws1.write_merge(row, row, col + 2, col + 7, "Details of advances, inwards and outward supplies made during the financial year on which tax is payable", sub_header_style)
        row += 1

        ws1.write(row + 1, col + 1, "A", sub_header_content_style)
        ws1.write(row + 2, col + 1, "B", sub_header_content_style)
        ws1.write(row + 3, col + 1, "C", sub_header_content_style)
        ws1.write(row + 4, col + 1, "D", sub_header_content_style)
        ws1.write(row + 5, col + 1, "E", sub_header_content_style)
        ws1.write(row + 6, col + 1, "F", sub_header_content_style)
        ws1.write(row + 7, col + 1, "G", sub_header_content_style)
        ws1.write(row + 8, col + 1, "H", sub_header_content_style)
        ws1.write(row + 9, col + 1, "I", sub_header_content_style)
        ws1.write(row + 10, col + 1, "J", sub_header_content_style)
        ws1.write(row + 11, col + 1, "K", sub_header_content_style)
        ws1.write(row + 12, col + 1, "L", sub_header_content_style)
        ws1.write(row + 13, col + 1, "M", sub_header_content_style)
        ws1.write(row + 14, col + 1, "N", sub_header_content_style)

        ws1.write(row + 1, col + 2, "Supplies made to un-registered persons (B2C)", sub_header_content_style)
        ws1.write(row + 2, col + 2, "Supplies made to registered persons (B2B)", sub_header_content_style)
        ws1.write(row + 3, col + 2, "Zero rated supply (Export) on payment of tax (except supplies to SEZs)", sub_header_content_style)
        ws1.write(row + 4, col + 2, "Supply to SEZs on payment of tax", sub_header_content_style)
        ws1.write(row + 5, col + 2, "Deemed Exports", sub_header_content_style)
        ws1.write(row + 6, col + 2, "Advances on which tax has been paid but invoice has not been issued (not covered under (A) to (E) above)",sub_header_content_style)
        ws1.write(row + 7, col + 2, "Inward supplies on which tax is to be paid on reverse charge basis",sub_header_content_style)
        ws1.write(row + 8, col + 2, "Sub-total (A to G above)", sub_header_content_style)
        ws1.write(row + 9, col + 2, "Credit Notes issued in respect of transactions specified in (B) to (E) above (-)", sub_header_content_style)
        ws1.write(row + 10, col + 2, "Debit Notes issued in respect of transactions specified in (B) to (E) above (+)", sub_header_content_style)
        ws1.write(row + 11, col + 2, "Supplies / tax declared through Amendments (+)", sub_header_content_style)
        ws1.write(row + 12, col + 2, "Supplies / tax reduced through Amendments (-)", sub_header_content_style)
        ws1.write(row + 13, col + 2, "Sub-total (I to L above)", sub_header_content_style)
        ws1.write(row + 14, col + 2, "Supplies and advances on which tax is to be paid (H + M) above", sub_header_content_style)

        # b2c
        ws1.write(row + 1, col + 3, b2c['taxable_value'], line_content_style)
        ws1.write(row + 1, col + 4, b2c['cgst'], line_content_style)
        ws1.write(row + 1, col + 5, b2c['sgst'], line_content_style)
        ws1.write(row + 1, col + 6, b2c['igst'], line_content_style)
        ws1.write(row + 1, col + 7, b2c['cess'], line_content_style)

        # b2b
        ws1.write(row + 2, col + 3, b2b['taxable_value'], line_content_style)
        ws1.write(row + 2, col + 4, b2b['cgst'], line_content_style)
        ws1.write(row + 2, col + 5, b2b['sgst'], line_content_style)
        ws1.write(row + 2, col + 6, b2b['igst'], line_content_style)
        ws1.write(row + 2, col + 7, b2b['cess'], line_content_style)

        # zero rated
        ws1.write(row + 3, col + 3, zero_rated['taxable_value'], line_content_style)
        ws1.write(row + 3, col + 6, zero_rated['igst'], line_content_style)

        # supply to sez
        ws1.write(row + 4, col + 3, supply_sez['taxable_value'], line_content_style)
        ws1.write(row + 4, col + 6, supply_sez['igst'], line_content_style)

        # deemed
        ws1.write(row + 5, col + 3, deemed_exp['taxable_value'], line_content_style)
        ws1.write(row + 5, col + 4, deemed_exp['cgst'], line_content_style)
        ws1.write(row + 5, col + 5, deemed_exp['sgst'], line_content_style)
        ws1.write(row + 5, col + 6, deemed_exp['igst'], line_content_style)
        ws1.write(row + 5, col + 7, deemed_exp['cess'], line_content_style)

        # inward reverse charge
        ws1.write(row + 7, col + 3, inward_rev_charge['taxable_value'], line_content_style)
        ws1.write(row + 7, col + 4, inward_rev_charge['cgst'], line_content_style)
        ws1.write(row + 7, col + 5, inward_rev_charge['sgst'], line_content_style)
        ws1.write(row + 7, col + 6, inward_rev_charge['igst'], line_content_style)
        ws1.write(row + 7, col + 7, inward_rev_charge['cess'], line_content_style)

        # credit note
        ws1.write(row + 9, col + 3, credit_note['taxable_value'], line_content_style)
        ws1.write(row + 9, col + 4, credit_note['cgst'], line_content_style)
        ws1.write(row + 9, col + 5, credit_note['sgst'], line_content_style)
        ws1.write(row + 9, col + 6, credit_note['igst'], line_content_style)
        ws1.write(row + 9, col + 7, credit_note['cess'], line_content_style)

        # debit note
        ws1.write(row + 10, col + 3, debit_note['taxable_value'], line_content_style)
        ws1.write(row + 10, col + 4, debit_note['cgst'], line_content_style)
        ws1.write(row + 10, col + 5, debit_note['sgst'], line_content_style)
        ws1.write(row + 10, col + 6, debit_note['igst'], line_content_style)
        ws1.write(row + 10, col + 7, debit_note['cess'], line_content_style)

        return b2b, b2c, inward_rev_charge, zero_rated, supply_sez, deemed_exp, credit_note, debit_note

    def outward_tax_not_payable_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('5 Outward')

        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500

        ws1.write(row, col + 2, "From:", sub_header_style)
        ws1.write(row, col + 3, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 2, "To:", sub_header_style)
        ws1.write(row, col + 3, self.format_date(self.date_to), sub_header_content_style)
        row += 1

        ws1.write_merge(row, row + 1, col + 2, col + 2, "Nature of Supplies", sub_header_style)
        ws1.write_merge(row, row + 1, col + 3, col + 3, "Taxable Value(₹)", sub_header_style)
        ws1.write_merge(row, row, col + 4, col + 7, "Amount in ₹ in all tables", sub_header_style)
        row += 1

        ws1.write(row, col + 4, "Central Tax", sub_header_style)
        ws1.write(row, col + 5, "State Tax/ UT Tax", sub_header_style)
        ws1.write(row, col + 6, "Integrated tax", sub_header_style)
        ws1.write(row, col + 7, "Cess", sub_header_style)
        row += 1

        ws1.write(row, col + 1, "5", sub_header_style)
        ws1.write_merge(row, row, col + 2, col + 7, "Details of outward supplies made during the financial year on which tax is not payable", sub_header_style)
        row += 1

        ws1.write(row + 1, col + 1, "A", sub_header_content_style)
        ws1.write(row + 2, col + 1, "B", sub_header_content_style)
        ws1.write(row + 3, col + 1, "C", sub_header_content_style)
        ws1.write(row + 4, col + 1, "D", sub_header_content_style)
        ws1.write(row + 5, col + 1, "E", sub_header_content_style)
        ws1.write(row + 6, col + 1, "F", sub_header_content_style)
        ws1.write(row + 7, col + 1, "G", sub_header_content_style)
        ws1.write(row + 8, col + 1, "H", sub_header_content_style)
        ws1.write(row + 9, col + 1, "I", sub_header_content_style)
        ws1.write(row + 10, col + 1, "J", sub_header_content_style)
        ws1.write(row + 11, col + 1, "K", sub_header_content_style)
        ws1.write(row + 12, col + 1, "L", sub_header_content_style)
        ws1.write(row + 13, col + 1, "M", sub_header_content_style)
        ws1.write(row + 14, col + 1, "N", sub_header_content_style)

        ws1.write(row + 1, col + 2, "Zero rated supply (Export) without payment of tax", sub_header_content_style)
        ws1.write(row + 2, col + 2, "Supply to SEZs without payment of tax", sub_header_content_style)
        ws1.write(row + 3, col + 2, "Supplies on which tax is to be paid by recipient on reverse charge basis", sub_header_content_style)
        ws1.write(row + 4, col + 2, "Exempted ", sub_header_content_style)
        ws1.write(row + 5, col + 2, "Nil rated", sub_header_content_style)
        ws1.write(row + 6, col + 2, "Non-GST supply (includes 'no supply' ) ", sub_header_content_style)
        ws1.write(row + 7, col + 2, "Sub-total (A to F above)", sub_header_content_style)
        ws1.write(row + 8, col + 2, "Credit Notes issued in respect of transactions specified in A to F above (-)", sub_header_content_style)
        ws1.write(row + 9, col + 2, "Debit Notes issued in respect of transactions specified in A to F above (+)", sub_header_content_style)
        ws1.write(row + 10, col + 2, "Supplies declared through Amendments (+)", sub_header_content_style)
        ws1.write(row + 11, col + 2, "Supplies reduced through Amendments (-)", sub_header_content_style)
        ws1.write(row + 12, col + 2, "Sub-Total (H to K above)", sub_header_content_style)
        ws1.write(row + 13, col + 2, "Turnover on which tax is not to be paid (G + L) above", sub_header_content_style)
        ws1.write(row + 14, col + 2, "Total Turnover (including advances) (4N + 5M - 4G) above", sub_header_content_style)

        zero_rate = {}
        supply_sez_wop = {}
        exempted = {}
        nil_rated = {}
        credit = {}

        # TODO: credit/debit note 
        zero_rate_inv = sorted_invoices.filtered(lambda p: p.move_type == 'out_invoice' and p.l10n_in_gst_treatment == 'overseas')  # zero rated supplies   TODO: odoo14 field
        self.summarize_tax_values(zero_rate_inv, zero_rate, lambda p: p.tax_ids[0].name.startswith('Exempt') or p.tax_ids[0].name.startswith('Nil')if p.tax_ids else True)

        supply_sez_wop_inv = sorted_invoices.filtered(lambda p: p.move_type == 'out_invoice' and p.l10n_in_gst_treatment in ('special_economic_zone',) and p.amount_tax == 0.00)  # supply to sez wop
        self.summarize_tax_values(supply_sez_wop_inv, supply_sez_wop)

        exe_nil_inv = sorted_invoices.filtered(lambda p: p.move_type == 'out_invoice')
        self.summarize_tax_values(exe_nil_inv, exempted, lambda p: p.tax_ids[0].name.startswith('Exempt') if p.tax_ids else True)  # Exempted
        self.summarize_tax_values(exe_nil_inv, nil_rated, lambda p: p.tax_ids[0].name.startswith('Nil') if p.tax_ids else True)  # nil rated

        #get all processed invoices (supply t sez wop, exempted, nil) and remove duplicates: can be used to filter credit/debit note
        valid_invoices = []
        [valid_invoices.append(x) for x in exempted['processed_invs'] if x not in valid_invoices]
        [valid_invoices.append(x) for x in nil_rated['processed_invs'] if x not in valid_invoices]
        [valid_invoices.append(x) for x in supply_sez_wop['processed_invs'] if x not in valid_invoices]

        # credit note
        credit_inv = refund_invoices.filtered(lambda p: p.move_type == 'out_refund' and p.reversed_entry_id and p.reversed_entry_id.id in valid_invoices)
        self.summarize_tax_values(credit_inv, credit)

        # sez without payment of tax
        ws1.write(row + 1, col + 3, zero_rate['taxable_value'], line_content_style)

        ws1.write(row + 2, col + 3, supply_sez_wop['taxable_value'], line_content_style)

        ws1.write(row + 4, col + 3, exempted['taxable_value'], line_content_style)  # exempted

        ws1.write(row + 5, col + 3, nil_rated['taxable_value'], line_content_style)  # nil rated

        ws1.write(row + 8, col + 3, credit['taxable_value'], line_content_style)  # credit note

        return zero_rate, supply_sez_wop, exempted, nil_rated, credit

    def itc_availed(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('6 ITC Availed')

        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500

        ws1.write(row, col + 2, "From:", sub_header_style)
        ws1.write(row, col + 3, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 2, "To:", sub_header_style)
        ws1.write(row, col + 3, self.format_date(self.date_to), sub_header_content_style)
        row += 1

        ws1.write_merge(row, row + 1, col + 2, col + 2, "Description", sub_header_style)
        ws1.write_merge(row, row + 1, col + 3, col + 3, "Type", sub_header_style)
        ws1.write_merge(row, row, col + 4, col + 7, "Amount in ₹ in all tables", sub_header_style)
        row += 1

        ws1.write(row, col + 4, "Central Tax", sub_header_style)
        ws1.write(row, col + 5, "State Tax/ UT Tax", sub_header_style)
        ws1.write(row, col + 6, "Integrated tax", sub_header_style)
        ws1.write(row, col + 7, "Cess", sub_header_style)
        row += 1

        ws1.write(row, col + 1, "6", sub_header_style)
        ws1.write_merge(row, row, col + 2, col + 7, "Details of ITC availed during the financial year", sub_header_style)
        row += 1

        ws1.write_merge(row, row, col + 1, col + 1, "A", sub_header_content_style)
        ws1.write_merge(row + 1, row + 3, col + 1, col + 1, "B", sub_header_content_style)
        ws1.write_merge(row + 4, row + 6, col + 1, col + 1, "C", sub_header_content_style)
        ws1.write_merge(row + 7, row + 9, col + 1, col + 1, "D", sub_header_content_style)
        ws1.write_merge(row + 10, row + 11, col + 1, col + 1, "E", sub_header_content_style)
        ws1.write(row + 12, col + 1, "F", sub_header_content_style)
        ws1.write(row + 13, col + 1, "G", sub_header_content_style)
        ws1.write(row + 14, col + 1, "H", sub_header_content_style)
        ws1.write(row + 15, col + 1, "I", sub_header_content_style)
        ws1.write(row + 16, col + 1, "J", sub_header_content_style)
        ws1.write(row + 17, col + 1, "K", sub_header_content_style)
        ws1.write(row + 18, col + 1, "L", sub_header_content_style)
        ws1.write(row + 19, col + 1, "M", sub_header_content_style)
        ws1.write(row + 20, col + 1, "N", sub_header_content_style)
        ws1.write(row + 21, col + 1, "O", sub_header_content_style)

        ws1.write_merge(row, row, col + 2, col + 3, "Total amount of input tax credit availed through FORM GSTR-3B (Sum total of table 4A of FORM GSTR-3B)", line_content_style)
        ws1.write_merge(row + 1, row + 3, col + 2, col + 2, "Inward supplies (other than imports and inward supplies liable to reverse charge but includes services received from SEZs)", line_content_style)
        ws1.write(row + 1, col + 3, "Inputs", line_content_style)
        ws1.write(row + 2, col + 3, "Capital Goods", line_content_style)
        ws1.write(row + 3, col + 3, "Input Services", line_content_style)
        ws1.write_merge(row + 4, row + 6, col + 2, col + 2, "Inward supplies received from unregistered persons liable to reverse charge (other than B above) on which tax is paid & ITC availed", line_content_style)
        ws1.write(row + 4, col + 3, "Inputs", line_content_style)
        ws1.write(row + 5, col + 3, "Capital Goods", line_content_style)
        ws1.write(row + 6, col + 3, "Input Services", line_content_style)
        ws1.write_merge(row + 7, row + 9, col + 2, col + 2, "Inward supplies received from registered persons liable to reverse charge (other than B above) on which tax is paid and ITC availed", line_content_style)
        ws1.write(row + 7, col + 3, "Inputs", line_content_style)
        ws1.write(row + 8, col + 3, "Capital Goods", line_content_style)
        ws1.write(row + 9, col + 3, "Input Services", line_content_style)
        ws1.write_merge(row + 10, row + 11, col + 2, col + 2, "Import of goods (including supplies from SEZ)", line_content_style)
        ws1.write(row + 10, col + 3, "Inputs", line_content_style)
        ws1.write(row + 11, col + 3, "Capital Goods", line_content_style)
        ws1.write_merge(row + 12, row + 12, col + 2, col + 3, "Import of services (excluding inward supplies from SEZs)", line_content_style)
        ws1.write_merge(row + 13, row + 13, col + 2, col + 3, "Input Tax credit received from ISD", line_content_style)
        ws1.write_merge(row + 14, row + 14, col + 2, col + 3, "Amount of ITC reclaimed (other than B above) under the provisions of the Act", line_content_style)
        ws1.write_merge(row + 15, row + 15, col + 2, col + 3, "Sub-total (B to H above)", line_content_style)
        ws1.write_merge(row + 16, row + 16, col + 2, col + 3, "Difference (I - A) above", line_content_style)
        ws1.write_merge(row + 17, row + 17, col + 2, col + 3, "Transition Credit through TRAN-1 (including revisions if any)", line_content_style)
        ws1.write_merge(row + 18, row + 18, col + 2, col + 3, "Transition Credit through TRAN-2", line_content_style)
        ws1.write_merge(row + 19, row + 19, col + 2, col + 3, "Any other ITC availed but not specified above", line_content_style)
        ws1.write_merge(row + 20, row + 20, col + 2, col + 3, "Sub-total (K to M above)", line_content_style)
        ws1.write_merge(row + 21, row + 21, col + 2, col + 3, "Total ITC availed (I + N) above", line_content_style)

        inward_expt_reverse_service = {}
        inward_expt_reverse_input = {}
        inward_not_reg = {}
        import_goods = {}
        import_service = {}

        # Inward supplies (other than import and reverse charge) but include supply from sez
        inward_expt_reverse_inv = sorted_invoices.filtered(lambda p: p.move_type == 'in_invoice' and not p._is_reverse_charge_applicable() and not p.l10n_in_gst_treatment == 'overseas')
        self.summarize_tax_values(inward_expt_reverse_inv, inward_expt_reverse_service, lambda p: p.product_id.type == 'service')
        self.summarize_tax_values(inward_expt_reverse_inv, inward_expt_reverse_input, lambda p: p.product_id.type != 'service')

        # inward not registered imports liable to reverse charge #todo:registered
        inward_not_reg_inv = sorted_invoices.filtered(lambda p: p.move_type == 'in_invoice' and p._is_reverse_charge_applicable())
        self.summarize_tax_values(inward_not_reg_inv, inward_not_reg, lambda p: p.product_id.type != 'service')

        # import of goods
        imp_goods_inv = sorted_invoices.filtered(lambda p: p.move_type == 'in_invoice' and p.l10n_in_gst_treatment == 'overseas')
        self.summarize_tax_values(imp_goods_inv, import_goods, lambda p: p.product_id.type != 'service')

        # import of service except from sez
        imp_service_inv = sorted_invoices.filtered(lambda p: p.move_type == 'in_invoice' and p.l10n_in_gst_treatment == 'overseas')    #TODO: exclude sez!
        self.summarize_tax_values(imp_service_inv, import_service, lambda p: p.product_id.type == 'service')

        ws1.write(row + 1, col + 4, inward_expt_reverse_service['cgst'], line_content_style)
        ws1.write(row + 1, col + 5, inward_expt_reverse_service['sgst'], line_content_style)
        ws1.write(row + 1, col + 6, inward_expt_reverse_service['igst'], line_content_style)
        ws1.write(row + 1, col + 7, inward_expt_reverse_service['cess'], line_content_style)
        ws1.write(row + 3, col + 4, inward_expt_reverse_input['cgst'], line_content_style)
        ws1.write(row + 3, col + 5, inward_expt_reverse_input['sgst'], line_content_style)
        ws1.write(row + 3, col + 6, inward_expt_reverse_input['igst'], line_content_style)
        ws1.write(row + 3, col + 7, inward_expt_reverse_input['cess'], line_content_style)

        ws1.write(row + 4, col + 4, inward_not_reg['cgst'], line_content_style)
        ws1.write(row + 4, col + 5, inward_not_reg['sgst'], line_content_style)
        ws1.write(row + 4, col + 6, inward_not_reg['igst'], line_content_style)
        ws1.write(row + 4, col + 7, inward_not_reg['cess'], line_content_style)

        ws1.write(row + 10, col + 6, import_goods['igst'], line_content_style)
        ws1.write(row + 10, col + 7, import_goods['cess'], line_content_style)

        ws1.write(row + 12, col + 6, import_service['igst'], line_content_style)
        ws1.write(row + 12, col + 7, import_service['cess'], line_content_style)

        return inward_expt_reverse_service, inward_expt_reverse_input, inward_not_reg, import_goods, import_service

    #HSN Wise Summary of outward supplies
    def hsn_outward(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('17 HSN Outward')

        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500

        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1

        ws1.write_merge(row, row, col + 1, col + 11, "17. HSN wise summary of outward supplies", sub_header_style)
        row += 1

        ws1.write(row, col + 1, "HSN Code", sub_header_content_style)
        ws1.write(row, col + 2, "Description", sub_header_content_style)
        ws1.write(row, col + 3, "UQC", sub_header_content_style)
        ws1.write(row, col + 4, "Total Quantity", sub_header_content_style)
        ws1.write(row, col + 5, "Total Taxable value (₹)", sub_header_content_style)
        ws1.write(row, col + 6, "Is supply applicable for concessional rate of tax", sub_header_content_style)
        ws1.write(row, col + 7, "Rate of Tax (%)", sub_header_content_style)
        ws1.write(row, col + 8, "Integrated Tax (₹)", sub_header_content_style)
        ws1.write(row, col + 9, "Central Tax (₹)", sub_header_content_style)
        ws1.write(row, col + 10, "State/UT Tax", sub_header_content_style)
        ws1.write(row, col + 11, "Cess", sub_header_content_style)
        row += 1

        hsn_summary_data = {}

        hsn_outward = sorted_invoices.filtered(lambda p: p.move_type == 'out_invoice')
        hsn_outward += refund_invoices.filtered(lambda p: p.move_type == 'out_refund')  # consider invoices + credit notes
        self.summarize_hsn_tax(hsn_outward, hsn_summary_data)

        for product_hsn, hsn_sum in sorted(hsn_summary_data.items(), key=lambda p: p[0].name):
            tax_rate = float(self.get_num(product_hsn.taxes_id[0].name.split('%')[0])) if product_hsn.taxes_id else 0
            if product_hsn.default_code in ('ADVANCE','CHARGES','DISCOUNT'):    #Skip Roundoff/Discount/Extra Charges/Advance items
                continue
            ws1.write(row, col + 1, product_hsn.l10n_in_hsn_code, line_content_style)
            ws1.write(row, col + 2, product_hsn.name, line_content_style)
            ws1.write(row, col + 3, product_hsn.uom_id.l10n_in_code.split('-')[0], line_content_style) #UQC
            ws1.write(row, col + 4, hsn_sum[0], line_content_style) #Quantity in Base UoM
            ws1.write(row, col + 5, hsn_sum[1], line_content_style) #taxable value
            #todo: Is supply applicable for concessional rate of tax
            ws1.write(row, col + 6, "", line_content_style)
            ws1.write(row, col + 7, tax_rate, line_content_style)
            ws1.write(row, col + 8, hsn_sum[2], line_content_style)
            ws1.write(row, col + 9, hsn_sum[3], line_content_style)
            ws1.write(row, col + 10, hsn_sum[4], line_content_style)
            ws1.write(row, col + 11, hsn_sum[5], line_content_style)
            row += 1
        return hsn_summary_data

    # HSN Wise Summary of inward supplies
    def hsn_inward(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('18 HSN Inward')

        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500

        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1

        ws1.write_merge(row, row, col + 1, col + 11, "18. HSN wise summary of Inward supplies", sub_header_style)
        row += 1

        ws1.write(row, col + 1, "HSN Code", sub_header_content_style)
        ws1.write(row, col + 2, "Description", sub_header_content_style)
        ws1.write(row, col + 3, "UQC", sub_header_content_style)
        ws1.write(row, col + 4, "Total Quantity", sub_header_content_style)
        ws1.write(row, col + 5, "Total Taxable value (₹)", sub_header_content_style)
        ws1.write(row, col + 6, "Is supply applicable for concessional rate of tax", sub_header_content_style)
        ws1.write(row, col + 7, "Rate of Tax (%)", sub_header_content_style)
        ws1.write(row, col + 8, "Integrated Tax (₹)", sub_header_content_style)
        ws1.write(row, col + 9, "Central Tax (₹)", sub_header_content_style)
        ws1.write(row, col + 10, "State/UT Tax", sub_header_content_style)
        ws1.write(row, col + 11, "Cess", sub_header_content_style)
        row += 1

        hsn_summary_data = {}

        hsn_inward = sorted_invoices.filtered(lambda p: p.move_type == 'in_invoice')
        hsn_inward += refund_invoices.filtered(lambda p: p.move_type == 'in_refund')  # consider bills + debit notes
        self.summarize_hsn_tax(hsn_inward, hsn_summary_data)

        for product_hsn, hsn_sum in sorted(hsn_summary_data.items(), key=lambda p: p[0].name):
            tax_rate = float(self.get_num(product_hsn.supplier_taxes_id[0].name.split('%')[0])) if product_hsn.supplier_taxes_id else 0
            if product_hsn.default_code in (
                    'ADVANCE', 'CHARGES', 'DISCOUNT'):  # Skip Roundoff/Discount/Extra Charges/Advance items
                continue
            ws1.write(row, col + 1, product_hsn.l10n_in_hsn_code, line_content_style)
            ws1.write(row, col + 2, product_hsn.name, line_content_style)
            ws1.write(row, col + 3, product_hsn.uom_id.l10n_in_code.split('-')[0], line_content_style)  # UQC
            ws1.write(row, col + 4, hsn_sum[0], line_content_style)  # Quantity in Base UoM
            ws1.write(row, col + 5, hsn_sum[1], line_content_style)  # taxable value
            # todo: Is supply applicable for concessional rate of tax
            ws1.write(row, col + 6, "", line_content_style)
            ws1.write(row, col + 7, tax_rate, line_content_style)
            ws1.write(row, col + 8, hsn_sum[2], line_content_style)
            ws1.write(row, col + 9, hsn_sum[3], line_content_style)
            ws1.write(row, col + 10, hsn_sum[4], line_content_style)
            ws1.write(row, col + 11, hsn_sum[5], line_content_style)
            row += 1
        return hsn_summary_data

    """ Utility method to summarize tax amount by rate, per invoice """

    def summarize_tax_values(self, invoice_list, tax_values, inv_line_filter_fn=None):
        # @invoice_list: list of invoices
        # tax_values: returned tax summary
        # @inv_line_filter_fn: lambda function to filter invoice lines, if required (needed for IMPS and IMPG)

        tax_values.clear()
        inv_ids = []
        if not inv_line_filter_fn:
            inv_line_filter_fn = lambda p: True
        # Can't use invoice.tax_line_ids directly because it will contain on individual/leaf taxes (like CGST@2.5%, SGST@2.5%)
        # while gstr9 report needs the 'group' tax (like GST@5%).
        # Iterate through invoice.invoice_line_ids.invoice_line_tax_line_ids and collect/compute from there
        igst_amount = cgst_amount = sgst_amount = cess_amount = taxable_amount = 0.0
        for invoice in invoice_list:
            #Subtract if invoice is refund (in/out) - this may cause amount reported to be negative, e.g. 4I: Credit Notes
            sign = 1
            if invoice.move_type in ('out_refund', 'in_refund'):
                sign = -1

            foreign_curr = None
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                foreign_curr = invoice.currency_id
                curr_rate_date = invoice.date or invoice.invoice_date
                company_curr = invoice.company_id.currency_id

            for inv_line in invoice.invoice_line_ids.filtered(inv_line_filter_fn):  # Filter lines if necessary (e.g. goods/service)
                price = inv_line.price_unit * (1 - (inv_line.discount or 0.0) / 100.0)
                line_taxes = inv_line.tax_ids.compute_all(price, invoice.currency_id, inv_line.quantity,
                                                          inv_line.product_id, invoice.partner_id)
                if foreign_curr:
                    line_taxes['total_excluded'] = foreign_curr._convert(line_taxes['total_excluded'], company_curr, invoice.company_id, curr_rate_date)
                    line_taxes['total_included'] = foreign_curr._convert(line_taxes['total_included'], company_curr, invoice.company_id, curr_rate_date)
                    for l in line_taxes['taxes']:
                        l['amount'] = foreign_curr._convert(l['amount'], company_curr, invoice.company_id, curr_rate_date)
                        l['base'] = foreign_curr._convert(l['base'], company_curr, invoice.company_id, curr_rate_date)
                if invoice.id not in inv_ids:
                    inv_ids.append(invoice.id)
                # _logger.info(line_taxes)
                # _logger.info(invoice_line.tax_ids.sorted(reverse=True))
                for tax in line_taxes['taxes']:
                    if 'IGST' in tax['name']:
                        igst_amount += tax['amount'] * sign
                    elif 'CGST' in tax['name']:
                        cgst_amount += tax['amount'] * sign
                    elif 'SGST' in tax['name'] or 'UTGST' in tax['name']:
                        sgst_amount += tax['amount'] * sign
                    elif 'CESS' in tax['name']:
                        cess_amount += tax['amount'] * sign
                taxable_amount += line_taxes['total_excluded'] * sign
        tax_values['taxable_value'] = taxable_amount
        tax_values['igst'] = igst_amount
        tax_values['cgst'] = cgst_amount
        tax_values['sgst'] = sgst_amount
        tax_values['cess'] = cess_amount
        tax_values['processed_invs'] = inv_ids

    """Utility to compute HSN wise taxes"""
    def summarize_hsn_tax(self, invoice_list, hsn_summary_data):
        # @invoice_list: list of invoices
        # tax_values: returned hsn tax summary
        hsn_summary_data.clear()
        for invoice in invoice_list:
            # Subtract if invoice is refund (in/out) - this may cause amount reported to be negative, e.g. 4I: Credit Notes
            sign = 1
            if invoice.move_type in ('out_refund', 'in_refund'):
                sign = -1

            foreign_curr = None
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                foreign_curr = invoice.currency_id
                curr_rate_date = invoice.date or invoice.invoice_date
                company_curr = invoice.company_id.currency_id

            for invoice_line in invoice.invoice_line_ids.filtered(lambda l: l.product_id):
                prod_id = invoice_line.product_id
                line_uom = invoice_line.product_uom_id
                line_qty = line_uom._compute_quantity(invoice_line.quantity, prod_id.uom_id) * sign
                # Take care of currency conversion
                line_amount = foreign_curr._convert(invoice_line.price_subtotal, company_curr, invoice.company_id, curr_rate_date) \
                    if foreign_curr else invoice_line.price_subtotal
                line_amount *= sign  # subtract if refund
                price = invoice_line.price_unit * (1 - (invoice_line.discount or 0.0) / 100.0)
                line_taxes = invoice_line.tax_ids.compute_all(price, invoice.currency_id,
                                                                           invoice_line.quantity, prod_id,
                                                                           invoice.partner_id)

                if foreign_curr:
                    line_taxes['total_excluded'] = foreign_curr._convert(line_taxes['total_excluded'], company_curr, invoice.company_id, curr_rate_date)
                    line_taxes['total_included'] = foreign_curr._convert(line_taxes['total_included'], company_curr, invoice.company_id, curr_rate_date)
                    for l in line_taxes['taxes']:
                        l['amount'] = foreign_curr._convert(l['amount'], company_curr, invoice.company_id, curr_rate_date)
                        l['base']   = foreign_curr._convert(l['base'], company_curr, invoice.company_id, curr_rate_date)

                igst_amount = cgst_amount = sgst_amount = cess_amount = 0.0
                for tax_line in line_taxes['taxes']:
                    if 'IGST' in tax_line['name']:
                        igst_amount += tax_line['amount'] * sign
                    elif 'CGST' in tax_line['name']:
                        cgst_amount += tax_line['amount'] * sign
                    elif 'SGST' in tax_line['name'] or 'UTGST' in tax_line['name']:
                        sgst_amount += tax_line['amount'] * sign
                    else:
                        cess_amount += tax_line['amount'] * sign

                if hsn_summary_data.get(prod_id):
                    hsn_summary_data[prod_id][0] += line_qty
                    hsn_summary_data[prod_id][1] += line_amount
                    hsn_summary_data[prod_id][2] += igst_amount
                    hsn_summary_data[prod_id][3] += cgst_amount
                    hsn_summary_data[prod_id][4] += sgst_amount
                    hsn_summary_data[prod_id][5] += cess_amount
                else:
                    hsn_summary_data[prod_id] = [line_qty, line_amount, igst_amount, cgst_amount,
                                                 sgst_amount, cess_amount]


    """ Utility to convert date/datetime to dd-mmm-yy format """
    def format_date(self, date_in):
        return datetime.strftime(date_in, "%d-%b-%y")

    """ Utility to get integer present in a string """

    def get_num(self, x):
        return int(''.join(ele for ele in x if ele.isdigit()) or 0)

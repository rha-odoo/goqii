# This file is part of TeXByte GST module. See LICENSE for details
from odoo import fields, models, api, _
from odoo.tools import float_is_zero, float_compare
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import xlwt
import base64
from io import BytesIO
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)
import pdb

B2CL_INVOICE_AMT_LIMIT = 250000

all_invoices = []
sorted_invoices = []
refund_invoices = []
canceled_invoices = []

#Map l10n_in_gst_treatment with GSTR1 excel template values
inv_tye_map = {
    'regular': 'Regular',
    'composition': 'Regular',
    'unregistered': 'Regular',
    'consumer': 'Regular',
    'overseas': 'Regular',       #TODO: export is regular?
    'special_economic_zone': 'SEZ supplies {} payment',    #With/Without payment, to be filled by checking tax amount
    'deemed_export': 'Deemed Exp'
    }

class GSTR2Report(models.TransientModel):

    _name = 'texbyte_gstr.report.gstr2'

    # fields to generate xls
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To')
    #inv_type = fields.Selection([('cust_inv','Sales Invoice'),('vndr_bil','Purchase Invoice')],
    #                            default='vndr_bil')

    # fields for download xls
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],
                             default='choose')
    report = fields.Binary('Prepared file', filters='.xls', readonly=True)
    filename = fields.Char('File Name', size=128)

    def get_valid_invoices(self):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        # Searching for customer invoices
        from_date = self.date_from
        to_date = self.date_to
        refund_invoice_ids = []
        inv_domain = ('move_type', 'in', ('in_invoice', 'in_refund'))

        #Get all invoices including canceled and refund
        all_invoices = self.env['account.move'].search([('invoice_date','>=', from_date),('invoice_date','<=', to_date),inv_domain,('state', '!=', 'draft')])
        #Canceled invoices
        canceled_invoices = all_invoices.filtered(lambda i: i.state == 'cancel')
        #Refund invoices
        refund_invoices = all_invoices.filtered(lambda i: i.state != 'cancel' and i.move_type == 'in_refund')
        #Legitimate invoices -- other than canceled and refund
        invoices = all_invoices.filtered(lambda i: i.id not in canceled_invoices.ids + refund_invoices.ids)
        sorted_invoices = invoices.sorted(key=lambda p: (p.invoice_date, p.name))


    def generate_gstr2_report(self):
        #Error handling is not taken into consideraion
        self.ensure_one()
        fp = BytesIO()
        xl_workbook = xlwt.Workbook(encoding='utf-8')

        from_date = self.date_from
        to_date = self.date_to

        # Get the invoices
        self.get_valid_invoices()

        self.generate_b2b_report(xl_workbook)
        self.generate_b2bur_report(xl_workbook)
        self.generate_imps_report(xl_workbook)
        self.generate_impg_report(xl_workbook)
        self.generate_cdnr_report(xl_workbook)
        self.generate_cdnur_report(xl_workbook)
        self.generate_at_report(xl_workbook)
        self.generate_atadj_report(xl_workbook)
        self.generate_exempted_report(xl_workbook)
        self.generate_itcr_report(xl_workbook)
        self.generate_hsn_report(xl_workbook)


        xl_workbook.save(fp)

        out = base64.encodebytes(fp.getvalue())
        self.write({'state': 'choose', 'report': out, 'filename':'gstr2_'+str(from_date)+'-'+str(to_date)+'.xls'})
        return {
            'name': 'GSTR2',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=texbyte_gstr.report.gstr2&id=" + str(self.id) + "&filename_field=filename&field=report&download=true&filename=" + self.filename,
            'target': 'current',
        }

    # Dont know the filter is correct in all report.
    """ B2B (Business to Business report) """
    def generate_b2b_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        #Error handling is not taken into consideraion
        self.ensure_one()

        #TODO: format (group & split by tax rate):
        #   GSTIN           Inv No     Inv Date     Inv Value   PoS         Tax Rate    Taxable Value
        #   GSTIN000022     INV001     01/01/2018   5092.00     32-Kerala   5           2200
        #   GSTIN000022     INV001     01/01/2018   5092.00     32-Kerala   12          1600
        #Plan:
        #   1.  Get invoices within range. Filter out 'Canceled', 'Refund' & 'Refunded' invoices
        #   2.  Loop through invoices
        #   3.      Loop through invoice lines
        #   4.          Loop through invoice_line_tax__ids
        #   5.              Collect the invoice, untaxed_total and tax rate/name (such as 'GST @5%')
        #   6.  Loop through collected invoice and tax details
        #   7.      Print invoice details, tax rate/name and untaxed_total

        #wb1 = self.xl_workbook      # xlwt.Workbook(encoding='utf-8')
        ws1 = wb1.add_sheet('b2b')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary Of Supplies From Registered Suppliers B2B(3)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "GSTIN of Supplier", sub_header_style)
        ws1.write(row, col + 2, "Invoice Number", sub_header_style)
        ws1.write(row, col + 3, "Invoice Date", sub_header_style)
        ws1.write(row, col + 4, "Invoice Value", sub_header_style)
        ws1.write(row, col + 5, "Place of Supply", sub_header_style)
        ws1.write(row, col + 6, "Reverse Charge", sub_header_style)
        ws1.write(row, col + 7, "Invoice Type", sub_header_style)
        ws1.write(row, col + 8, "Rate", sub_header_style)
        ws1.write(row, col + 9, "Taxable Value", sub_header_style)
        ws1.write(row, col + 10, "Integrated Tax Paid", sub_header_style)
        ws1.write(row, col + 11, "Central Tax Paid", sub_header_style)
        ws1.write(row, col + 12, "State/UT Tax Paid", sub_header_style)
        ws1.write(row, col + 13, "Cess Paid", sub_header_style)
        ws1.write(row, col + 14, "Eligibility For ITC", sub_header_style)
        ws1.write(row, col + 15, "Availed ITC Integrated Tax", sub_header_style)
        ws1.write(row, col + 16, "Availed ITC Central Tax", sub_header_style)
        ws1.write(row, col + 17, "Availed ITC State/UT Tax", sub_header_style)
        ws1.write(row, col + 18, "Availed ITC Cess", sub_header_style)

        row += 1
        #variables for columns and totals

        invoice_gst_tax_lines = {}

        b2b_invoices = sorted_invoices.filtered(lambda p: p.partner_id.vat) #GST registered customers
        self.summarize_inv_per_tax_rate(b2b_invoices, invoice_gst_tax_lines)

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                #if tax_id.gst_type in ('gst','ugst','igst'):
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                place_of_supply = invoice.partner_id.state_id and invoice.partner_id.state_id.name or invoice.company_id.state_id.name
                if float_is_zero(tax_rate, precision_digits=3):     #Skip zero rated/exempted rates
                    continue
                ws1.write(row, col + 1, invoice.partner_id.vat or "", line_content_style)
                ws1.write(row, col + 2, invoice.name, line_content_style)
                ws1.write(row, col + 3, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 4, invoice.amount_total, line_content_style)
                ws1.write(row, col + 5, place_of_supply, line_content_style)
                ws1.write(row, col + 6, invoice._is_reverse_charge_applicable() and "Y" or "N", line_content_style)
                ws1.write(row, col + 7, self.gst_inv_type_from_l10n(invoice), line_content_style)
                ws1.write(row, col + 8, tax_rate, line_content_style)
                ws1.write(row, col + 9, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 10, tax_amounts['igst_amount'], line_content_style)
                ws1.write(row, col + 11, tax_amounts['cgst_amount'], line_content_style)
                ws1.write(row, col + 12, tax_amounts['sgst_amount'], line_content_style)
                ws1.write(row, col + 13, tax_amounts['cess_amount'], line_content_style)
                ws1.write(row, col + 14, "NA", line_content_style)
                ws1.write(row, col + 15, 0, line_content_style)
                ws1.write(row, col + 16, 0, line_content_style)
                ws1.write(row, col + 17, 0, line_content_style)
                ws1.write(row, col + 18, 0, line_content_style)   #Cess amount

                row += 1
        return invoice_gst_tax_lines


        #for invoice in canceled_refund_invoices:
        #    row += 1
        #    ws1.write(row, col + 1, invoice.name, line_content_style)
        #    ws1.write(row, col + 2, invoice.invoice_date, line_content_style)
        #    ws1.write(row, col + 3, invoice.state.title(), line_content_style)
        #    ws1.write(row, col + 4, invoice.origin, line_content_style)
        #    ws1.write(row, col + 5, invoice.partner_id.vat or "", line_content_style)
        #    partner_name = invoice.partner_id.vat and invoice.partner_id.name or invoice.partner_name
        #    ws1.write(row, col + 6, partner_name, line_content_style)

    """ B2BUR Summary Of Supplies From Unregistered Suppliers B2BUR(4B) """
    def generate_b2bur_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        #Error handling is not taken into consideraion
        self.ensure_one()

        ws1 = wb1.add_sheet('b2bur')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary Of Supplies From Unregistered Suppliers B2BUR(4B)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Supplier Name", sub_header_style)
        ws1.write(row, col + 2, "Invoice Number", sub_header_style)
        ws1.write(row, col + 3, "Invoice date", sub_header_style)
        ws1.write(row, col + 4, "Invoice Value", sub_header_style)
        ws1.write(row, col + 5, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 6, "Supply Type", sub_header_style)
        ws1.write(row, col + 7, "Rate", sub_header_style)
        ws1.write(row, col + 8, "Taxable Value", sub_header_style)
        ws1.write(row, col + 9, "Integrated Tax Paid", sub_header_style)
        ws1.write(row, col + 10, "Central Tax Paid", sub_header_style)
        ws1.write(row, col + 11, "State/UT Tax Paid", sub_header_style)
        ws1.write(row, col + 12, "Cess Paid", sub_header_style)
        ws1.write(row, col + 13, "Eligibility For ITC", sub_header_style)
        ws1.write(row, col + 14, "Availed ITC Integrated Tax", sub_header_style)
        ws1.write(row, col + 15, "Availed ITC Central Tax", sub_header_style)
        ws1.write(row, col + 16, "Availed ITC State/UT Tax", sub_header_style)
        ws1.write(row, col + 17, "Availed ITC Cess", sub_header_style)

        row += 1

        invoice_gst_tax_lines = {}

        b2bur_invoices = sorted_invoices.filtered(lambda p: not p.partner_id.vat and not p.l10n_in_gst_treatment == 'overseas')   #Unregistered, excluding import
        self.summarize_inv_per_tax_rate(b2bur_invoices, invoice_gst_tax_lines)

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                #if tax_id.gst_type in ('gst','ugst','igst'):
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                place_of_supply = invoice.partner_id.state_id and invoice.partner_id.state_id.name or invoice.company_id.state_id.name
                if float_is_zero(tax_rate, precision_digits=3):     #Skip zero rated/exempted rates
                    continue
                ws1.write(row, col + 1, invoice.partner_id.name or "", line_content_style)
                ws1.write(row, col + 2, invoice.name, line_content_style)
                ws1.write(row, col + 3, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 4, invoice.amount_total, line_content_style)
                ws1.write(row, col + 5, place_of_supply, line_content_style)
                ws1.write(row, col + 6, self.gst_inv_type_from_l10n(invoice), line_content_style)
                ws1.write(row, col + 7, tax_rate, line_content_style)
                ws1.write(row, col + 8, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 9, tax_amounts['igst_amount'], line_content_style)
                ws1.write(row, col + 10, tax_amounts['cgst_amount'], line_content_style)
                ws1.write(row, col + 11, tax_amounts['sgst_amount'], line_content_style)
                ws1.write(row, col + 12, tax_amounts['cess_amount'], line_content_style)
                ws1.write(row, col + 13, "NA", line_content_style)
                ws1.write(row, col + 14, 0, line_content_style)
                ws1.write(row, col + 15, 0, line_content_style)
                ws1.write(row, col + 16, 0, line_content_style)
                ws1.write(row, col + 17, 0, line_content_style)   #Cess amount

                row += 1
        return invoice_gst_tax_lines

        #for invoice in canceled_refund_invoices:
        #    row += 1
        #    ws1.write(row, col + 1, invoice.name, line_content_style)
        #    ws1.write(row, col + 2, invoice.invoice_date, line_content_style)
        #    ws1.write(row, col + 3, invoice.state.title(), line_content_style)
        #    ws1.write(row, col + 4, invoice.origin, line_content_style)
        #    ws1.write(row, col + 5, invoice.partner_id.vat or "", line_content_style)
        #    partner_name = invoice.partner_id.vat and invoice.partner_id.name or invoice.partner_name
        #    ws1.write(row, col + 6, partner_name, line_content_style)

    """ IMPS - Import of Services report """
    def generate_imps_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('imps')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary For IMPS (4C)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Invoice Number of Reg Recipient", sub_header_style)
        ws1.write(row, col + 2, "Invoice Date", sub_header_style)
        ws1.write(row, col + 3, "Invoice Value", sub_header_style)
        ws1.write(row, col + 4, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 5, "Rate", sub_header_style)
        ws1.write(row, col + 6, "Taxable Value", sub_header_style)
        ws1.write(row, col + 7, "Integrated Tax Paid", sub_header_style)
        ws1.write(row, col + 8, "Cess Paid", sub_header_style)
        ws1.write(row, col + 9, "Eligibility For ITC", sub_header_style)
        ws1.write(row, col + 10, "Availed ITC Integrated Tax", sub_header_style)
        ws1.write(row, col + 11, "Availed ITC Cess", sub_header_style)

        row += 1

        invoice_gst_tax_lines = {}

        imps_invoices = sorted_invoices.filtered(lambda p: p.l10n_in_gst_treatment == 'overseas')   #Import of Services
        self.summarize_inv_per_tax_rate(imps_invoices, invoice_gst_tax_lines, lambda p: p.product_id.type == 'service')

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            foreign_curr = None  # consider currency when filling total invoice value
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                foreign_curr = invoice.currency_id
                curr_rate_date = invoice.date or invoice.date_invoice
                company_curr = invoice.company_id.currency_id
            total_amount = foreign_curr._convert(invoice.amount_total, company_curr, invoice.company_id, curr_rate_date) if foreign_curr else invoice.amount_total
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                #if tax_id.gst_type in ('gst','ugst','igst'):
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                place_of_supply = invoice.partner_id.state_id and invoice.partner_id.state_id.name or invoice.company_id.state_id.name
                if float_is_zero(tax_rate, precision_digits=3):     #Skip zero rated/exempted rates
                    continue
                ws1.write(row, col + 1, invoice.name, line_content_style)
                ws1.write(row, col + 2, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 3, total_amount, line_content_style)
                ws1.write(row, col + 4, place_of_supply, line_content_style)
                ws1.write(row, col + 5, tax_rate, line_content_style)
                ws1.write(row, col + 6, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 7, tax_amounts['igst_amount'], line_content_style)
                ws1.write(row, col + 8, tax_amounts['cess_amount'], line_content_style)
                ws1.write(row, col + 9, "", line_content_style)
                ws1.write(row, col + 10, 0, line_content_style)
                ws1.write(row, col + 11, 0, line_content_style)
                row += 1

        return invoice_gst_tax_lines


    """ IMPG -Import of Goods report """
    def generate_impg_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('impg')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary For IMPG (5)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Port Code", sub_header_style)
        ws1.write(row, col + 2, "Bill Of Entry Number", sub_header_style)
        ws1.write(row, col + 3, "Bill Of Entry Date", sub_header_style)
        ws1.write(row, col + 4, "Bill Of Entry Value", sub_header_style)
        ws1.write(row, col + 5, "Document type", sub_header_style)
        ws1.write(row, col + 6, "GSTIN Of SEZ Supplier", sub_header_style)
        ws1.write(row, col + 7, "Rate", sub_header_style)
        ws1.write(row, col + 8, "Taxable Value", sub_header_style)
        ws1.write(row, col + 9, "Integrated Tax Paid", sub_header_style)
        ws1.write(row, col + 10, "Cess Paid", sub_header_style)
        ws1.write(row, col + 11, "Eligibility For ITC", sub_header_style)
        ws1.write(row, col + 12, "Availed ITC Integrated Tax", sub_header_style)
        ws1.write(row, col + 13, "Availed ITC Cess", sub_header_style)

        row += 1

        invoice_gst_tax_lines = {}

        impg_invoices = sorted_invoices.filtered(lambda p: p.l10n_in_gst_treatment == 'overseas')   #Import of Goods
        self.summarize_inv_per_tax_rate(impg_invoices, invoice_gst_tax_lines, lambda p: p.product_id.type != 'service')

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            foreign_curr = None  # consider currency when filling total invoice value
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                foreign_curr = invoice.currency_id
                curr_rate_date = invoice.date or invoice.date_invoice
                company_curr = invoice.company_id.currency_id
            total_amount = foreign_curr._convert(invoice.amount_total, company_curr, invoice.company_id, curr_rate_date) if foreign_curr else invoice.amount_total
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                #if tax_id.gst_type in ('gst','ugst','igst'):
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                place_of_supply = invoice.partner_id.state_id and invoice.partner_id.state_id.name or invoice.company_id.state_id.name
                if float_is_zero(tax_rate, precision_digits=3):     #Skip zero rated/exempted rates
                    continue
                ws1.write(row, col + 1, invoice.l10n_in_shipping_port_code_id.code, line_content_style)
                ws1.write(row, col + 2, invoice.l10n_in_shipping_bill_number or invoice.name, line_content_style)
                ws1.write(row, col + 3, self.format_date(invoice.l10n_in_shipping_bill_date or invoice.invoice_date), line_content_style)
                ws1.write(row, col + 4, total_amount, line_content_style)
                ws1.write(row, col + 5, "Received from SEZ" if invoice.l10n_in_gst_treatment == 'special_economic_zone' else "Imports", line_content_style)
                ws1.write(row, col + 6, invoice.partner_id.vat, line_content_style)
                ws1.write(row, col + 7, tax_rate, line_content_style)
                ws1.write(row, col + 8, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 9, tax_amounts['igst_amount'], line_content_style)
                ws1.write(row, col + 10, tax_amounts['cess_amount'], line_content_style)
                ws1.write(row, col + 11, "", line_content_style)
                ws1.write(row, col + 12, 0, line_content_style)
                ws1.write(row, col + 13, 0, line_content_style)
                row += 1

        return invoice_gst_tax_lines


    """ CDNR (Credit/Debit Note Registered) """
    def generate_cdnr_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('cdnr')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary For CDNR(6C)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "GSTIN of Supplier", sub_header_style)
        ws1.write(row, col + 2, "Note/Refund Voucher Number", sub_header_style)
        ws1.write(row, col + 3, "Note/Refund Voucher date", sub_header_style)
        ws1.write(row, col + 4, "Invoice/Advance Payment Voucher Number", sub_header_style)
        ws1.write(row, col + 5, "Invoice/Advance Payment Voucher date", sub_header_style)
        ws1.write(row, col + 6, "Pre GST", sub_header_style)
        ws1.write(row, col + 7, "Document Type", sub_header_style)
        ws1.write(row, col + 8, "Reason For Issuing document", sub_header_style)
        ws1.write(row, col + 9, "Supply Type", sub_header_style)
        ws1.write(row, col + 10, "Note/Refund Voucher Value", sub_header_style)
        ws1.write(row, col + 11, "Rate", sub_header_style)
        ws1.write(row, col + 12, "Taxable Value", sub_header_style)
        ws1.write(row, col + 13, "Integrated Tax Paid", sub_header_style)
        ws1.write(row, col + 14, "Central Tax Paid", sub_header_style)
        ws1.write(row, col + 15, "State/UT Tax Paid", sub_header_style)
        ws1.write(row, col + 16, "Cess Paid", sub_header_style)
        ws1.write(row, col + 17, "Eligibility For ITC", sub_header_style)
        ws1.write(row, col + 18, "Availed ITC Integrated Tax", sub_header_style)
        ws1.write(row, col + 19, "Availed ITC Central Tax", sub_header_style)
        ws1.write(row, col + 20, "Availed ITC State/UT Tax", sub_header_style)
        ws1.write(row, col + 21, "Availed ITC Cess", sub_header_style)


        row += 1

        invoice_gst_tax_lines = {}

        cdnr_invoices = refund_invoices.filtered(lambda p: p.partner_id.vat and \
                                                        p.move_type in ('in_refund','out_refund')) #GST registered customers
        self.summarize_inv_per_tax_rate(cdnr_invoices, invoice_gst_tax_lines)    #Fills invoice_gst_tax_lines


        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                if float_is_zero(tax_rate, precision_digits=3):     #Skip zero rated/exempted rates
                    continue
                ws1.write(row, col + 1, invoice.partner_id.vat, line_content_style)
                ws1.write(row, col + 2, invoice.name, line_content_style)
                ws1.write(row, col + 3, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 4, invoice.reversed_entry_id and invoice.reversed_entry_id.name or "", line_content_style)
                ws1.write(row, col + 5, invoice.reversed_entry_id and self.format_date(invoice.reversed_entry_id.invoice_date) or "", line_content_style)
                ws1.write(row, col + 6, "", line_content_style)
                ws1.write(row, col + 7, invoice.move_type == 'in_refund' and "D" or "C", line_content_style)
                ws1.write(row, col + 8, invoice.name, line_content_style)
                ws1.write(row, col + 9, "", line_content_style)
                ws1.write(row, col + 10,invoice.amount_total, line_content_style)
                ws1.write(row, col + 11, tax_rate, line_content_style)
                ws1.write(row, col + 12, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 13, tax_amounts['igst_amount'], line_content_style)
                ws1.write(row, col + 14, tax_amounts['cgst_amount'], line_content_style)
                ws1.write(row, col + 15, tax_amounts['sgst_amount'], line_content_style)
                ws1.write(row, col + 16, tax_amounts['cess_amount'], line_content_style)
                ws1.write(row, col + 17, "", line_content_style)
                ws1.write(row, col + 18, "", line_content_style)
                ws1.write(row, col + 19, "", line_content_style)
                ws1.write(row, col + 20, "", line_content_style)
                ws1.write(row, col + 21, "", line_content_style)

                row += 1
        return invoice_gst_tax_lines


    """ AT report """
    def generate_at_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('at')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary For  Tax Liability on Advance Paid  under reverse charge(10 A)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 2, "Supply Type", sub_header_style)
        ws1.write(row, col + 3, "Gross Advance Paid", sub_header_style)
        ws1.write(row, col + 4, "Cess Amount", sub_header_style)

        row += 1


    """ ATADJ report """
    def generate_atadj_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('atadj')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary For Adjustment of advance tax paid earlier for reverse charge supplies (10 B)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 2, "Supply Type", sub_header_style)
        ws1.write(row, col + 3, "Gross Advance Paid to be Adjusted", sub_header_style)
        ws1.write(row, col + 4, "Cess Adjusted", sub_header_style)

        row += 1


    """ Exempted (Nil Rated, Exempted and Non GST supplies) report """
    def generate_exempted_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('exemp')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary For Composition, Nil rated, exempted and non GST inward supplies (7)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Description", sub_header_style)
        ws1.write(row, col + 2, "Composition taxable person", sub_header_style)
        ws1.write(row, col + 3, "Nil Rated Supplies", sub_header_style)
        ws1.write(row, col + 4, "Exempted (other than nil rated/non GST supply )", sub_header_style)
        ws1.write(row, col + 5, "Non-GST supplies", sub_header_style)

        row += 1

        nil_rated_idx = 0
        exempted_idx  = 1
        non_gst_idx   = 2
        gst_exempted_values = { 'reg':{'inter-state':[0.0, 0.0, 0.0], 'intra-state':[0.0, 0.0, 0.0]}, 'unreg':{'inter-state':[0.0, 0.0, 0.0], 'intra-state':[0.0, 0.0, 0.0]} }
        for invoice in sorted_invoices:
            for invoice_line in invoice.invoice_line_ids.filtered(lambda l: l.product_id.default_code not in ('ADVANCE','CHARGES','DISCOUNT')):
                price = invoice_line.price_unit * (1 - (invoice_line.discount or 0.0) / 100.0)
                taxes = invoice_line.tax_ids.compute_all(price, invoice.currency_id, invoice_line.quantity, invoice_line.product_id, invoice.partner_id)
                if float_compare(taxes['total_included'], taxes['total_excluded'], precision_digits=3) == 0:
                    #TODO: separate Nil-Rated, Exempted & Non-GST ones
                    #TODO: Assume there will be only 1 tax in the case of Zero tax
                    if taxes['taxes'] and  'GST' in taxes['taxes'][0]['name']:     #TODO: handle non-GST
                        l_index = nil_rated_idx
                    else:
                        l_index = exempted_idx

                    if invoice.partner_id.vat:
                        if invoice.partner_id.state_id == invoice.company_id.state_id:
                            gst_exempted_values['reg']['intra-state'][l_index] += invoice_line.price_subtotal
                        else:
                            gst_exempted_values['reg']['inter-state'][l_index] += invoice_line.price_subtotal
                    else:
                        if invoice.partner_id.state_id == invoice.company_id.state_id:
                            gst_exempted_values['unreg']['intra-state'][l_index] += invoice_line.price_subtotal
                        else:
                            gst_exempted_values['unreg']['inter-state'][l_index] += invoice_line.price_subtotal

        for exemp_key, exemp_val in gst_exempted_values.items():
            if exemp_key == 'reg':
                ws1.write(row, col+1, 'Inter-State supplies to registered persons')
                ws1.write(row, col+2, "")
                ws1.write(row, col+3, exemp_val['inter-state'][0])
                ws1.write(row, col+4, exemp_val['inter-state'][1])
                ws1.write(row, col+5, exemp_val['inter-state'][2])
                row += 1
                ws1.write(row, col+1, 'Intra-State supplies to registered persons')
                ws1.write(row, col+2, "")
                ws1.write(row, col+3, exemp_val['intra-state'][0])
                ws1.write(row, col+4, exemp_val['intra-state'][1])
                ws1.write(row, col+5, exemp_val['intra-state'][2])
            else:
                ws1.write(row, col+1, 'Inter-State supplies to unregistered persons')
                ws1.write(row, col+2, "")
                ws1.write(row, col+3, exemp_val['inter-state'][0])
                ws1.write(row, col+4, exemp_val['inter-state'][1])
                ws1.write(row, col+5, exemp_val['inter-state'][2])
                row += 1
                ws1.write(row, col+1, 'Intra-State supplies to unregistered persons')
                ws1.write(row, col+2, "")
                ws1.write(row, col+3, exemp_val['intra-state'][0])
                ws1.write(row, col+4, exemp_val['intra-state'][1])
                ws1.write(row, col+5, exemp_val['intra-state'][2])

            row += 1

    """ ITCR report """
    def generate_itcr_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('itcr')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary Input Tax credit Reversal/Reclaim (11)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Description for reversal of ITC", sub_header_style)
        ws1.write(row, col + 2, "To be added or reduced from output liability", sub_header_style)
        ws1.write(row, col + 3, "ITC Integrated Tax Amount", sub_header_style)
        ws1.write(row, col + 4, "ITC Central Tax Amount", sub_header_style)
        ws1.write(row, col + 5, "ITC State/UT Tax Amount", sub_header_style)
        ws1.write(row, col + 6, "ITC Cess Amount", sub_header_style)

        row += 1

    """ HSN Summary """
    def generate_hsn_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        #Error handling is not taken into consideraion
        self.ensure_one()

        ws1 = wb1.add_sheet('hsnsum')
        fp = BytesIO()

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 12 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 1, 5, "HSN Summary", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "HSN", sub_header_style)
        ws1.write(row, col + 2, "Description", sub_header_style)
        ws1.write(row, col + 3, "UQC", sub_header_style)
        ws1.write(row, col + 4, "Total Quantity", sub_header_style)
        ws1.write(row, col + 5, "Total Value", sub_header_style)
        ws1.write(row, col + 6, "Taxable Value", sub_header_style)
        ws1.write(row, col + 7, "Integrated Tax Amount", sub_header_style)
        ws1.write(row, col + 8, "Central Tax Amount", sub_header_style)
        ws1.write(row, col + 9, "State/UT Tax Amount", sub_header_style)
        ws1.write(row, col + 10, "Cess Amount", sub_header_style)

        hsn_summary_data = {}

        for invoice in sorted_invoices + refund_invoices:  # consider bills + debit notes
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
                line_qty = line_uom._compute_quantity(invoice_line.quantity, prod_id.uom_id)
                # Take care of currency conversion
                line_amount = foreign_curr._convert(invoice_line.price_subtotal, company_curr, invoice.company_id, curr_rate_date) \
                    if foreign_curr else invoice_line.price_subtotal
                line_total_amount = foreign_curr._convert(invoice_line.price_total, company_curr, invoice.company_id, curr_rate_date) \
                    if foreign_curr else invoice_line.price_total
                price = invoice_line.price_unit * (1 - (invoice_line.discount or 0.0) / 100.0)
                line_taxes = invoice_line.tax_ids.compute_all(price, invoice.currency_id, invoice_line.quantity, prod_id, invoice.partner_id)
                if foreign_curr:
                    line_taxes['total_excluded'] = foreign_curr._convert(line_taxes['total_excluded'], company_curr, invoice.company_id, curr_rate_date)
                    line_taxes['total_included'] = foreign_curr._convert(line_taxes['total_included'], company_curr, invoice.company_id, curr_rate_date)
                    for l in line_taxes['taxes']:
                        l['amount'] = foreign_curr._convert(l['amount'], company_curr, invoice.company_id, curr_rate_date)
                        l['base']   = foreign_curr._convert(l['base'], company_curr, invoice.company_id, curr_rate_date)

                # Add customer invoice, subtract credit note
                line_qty *= sign
                line_amount *= sign
                line_total_amount *= sign
                line_taxes['total_excluded'] *= sign
                line_taxes['total_included'] *= sign
                for l in line_taxes['taxes']:
                    l['amount'] *= sign

                #_logger.info(line_taxes)
                igst_amount = cgst_amount = sgst_amount = cess_amount = 0.0
                for tax_line in line_taxes['taxes']:
                    #tax_obj = self.env['account.tax'].browse(tax_line['id'])
                    if 'IGST' in tax_line['name']:   #tax_obj.gst_type == 'igst':
                        igst_amount += tax_line['amount']
                    elif 'CGST' in tax_line['name']: #tax_obj.gst_type == 'cgst':
                        cgst_amount += tax_line['amount']
                    elif 'SGST' in tax_line['name'] or 'UTGST' in tax_line['name']:
                        sgst_amount += tax_line['amount']
                    else:
                        cess_amount += tax_line['amount']
                #cgst_amount = invoice_line.tax_ids.filtered(lambda r: r.gst_type == 'cgst').amount
                #sgst_amount = invoice_line.tax_ids.filtered(lambda r: r.gst_type == 'sgst').amount
                #_logger.info(invoice_line.tax_ids)
                if hsn_summary_data.get(prod_id):
                    hsn_summary_data[prod_id][0] += line_qty
                    hsn_summary_data[prod_id][1] += line_total_amount
                    hsn_summary_data[prod_id][2] += line_amount
                    hsn_summary_data[prod_id][3] += igst_amount
                    hsn_summary_data[prod_id][4] += cgst_amount
                    hsn_summary_data[prod_id][5] += sgst_amount
                    hsn_summary_data[prod_id][6] += cess_amount
                else:
                    hsn_summary_data[prod_id] = [line_qty, line_total_amount, line_amount, igst_amount, cgst_amount, sgst_amount, cess_amount]

        #_logger.info(hsn_summary_data)

        #Can't sort dictionary, but get ordered list of tuples
        for product_hsn, hsn_sum in sorted(hsn_summary_data.items(), key=lambda p:p[0].name):
            if product_hsn.default_code in ('ADVANCE','CHARGES','DISCOUNT'):    #Skip Roundoff/Discount/Extra Charges/Advance items
                continue
            row += 1
            ws1.write(row, col + 1, product_hsn.l10n_in_hsn_code, line_content_style)
            ws1.write(row, col + 2, product_hsn.name, line_content_style)
            ws1.write(row, col + 3, product_hsn.uom_id.name, line_content_style)
            #Quantity in Base UoM
            ws1.write(row, col + 4, hsn_sum[0], line_content_style)
            #Amount
            ws1.write(row, col + 5, hsn_sum[1], line_content_style)
            ws1.write(row, col + 6, hsn_sum[2], line_content_style)
            ws1.write(row, col + 7, hsn_sum[3], line_content_style)
            ws1.write(row, col + 8, hsn_sum[4], line_content_style)
            ws1.write(row, col + 9, hsn_sum[5], line_content_style)
            ws1.write(row, col + 10, hsn_sum[6], line_content_style)
        return hsn_summary_data

    """ CDNRA (Amended Credit/Debit Note) """
    def generate_cdnra_report(self, wb1):
        self.ensure_one()

        ws1 = wb1.add_sheet('cdnra')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Amended Credit / Debit Note ", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "GSTIN/UIN of Recipient", sub_header_style)
        ws1.write(row, col + 2, "Name of Recipient", sub_header_style)
        ws1.write(row, col + 3, "Original Invoice/Advance Receipt Number", sub_header_style)
        ws1.write(row, col + 4, "Original Invoice/Advance Receipt date", sub_header_style)
        ws1.write(row, col + 5, "Original Note/ Refund Voucher Number", sub_header_style)
        ws1.write(row, col + 6, "Original Note/ Refund Voucher date", sub_header_style)
        ws1.write(row, col + 7, "Revised Note/Refund Voucher Number", sub_header_style)
        ws1.write(row, col + 8, "Revised Note/Refund Voucher date", sub_header_style)
        ws1.write(row, col + 9, "Document Type", sub_header_style)
        ws1.write(row, col + 10, "Reason For Issuing document", sub_header_style)
        ws1.write(row, col + 11, "Place Of Supply", sub_header_style)
        ws1.write(row, col + 12, "Note/Refund Voucher Value", sub_header_style)
        ws1.write(row, col + 13, "Rate", sub_header_style)
        ws1.write(row, col + 14, "Taxable Value", sub_header_style)
        ws1.write(row, col + 15, "Cess Amount", sub_header_style)
        ws1.write(row, col + 16, "Pre GST", sub_header_style)

        row += 1

    """ CDNUR (Credit/Debit Note Unregistered, more than 2.5 lakh) """
    def generate_cdnur_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('cdnur')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary For CDNUR(6C)", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Note/Voucher Number", sub_header_style)
        ws1.write(row, col + 2, "Note/Voucher date", sub_header_style)
        ws1.write(row, col + 3, "Invoice/Advance Payment Voucher number", sub_header_style)
        ws1.write(row, col + 4, "Invoice/Advance Payment Voucher date", sub_header_style)
        ws1.write(row, col + 5, "Pre GST", sub_header_style)
        ws1.write(row, col + 6, "Document Typ", sub_header_style)
        ws1.write(row, col + 7, "Reason For Issuing document", sub_header_style)
        ws1.write(row, col + 8, "Supply Type", sub_header_style)
        ws1.write(row, col + 9, "Invoice Type", sub_header_style)
        ws1.write(row, col + 10, "Note/Voucher Value", sub_header_style)
        ws1.write(row, col + 11, "Rate", sub_header_style)
        ws1.write(row, col + 12, "Taxable Value", sub_header_style)
        ws1.write(row, col + 13, "Integrated Tax Paid", sub_header_style)
        ws1.write(row, col + 14, "Central Tax Paid", sub_header_style)
        ws1.write(row, col + 15, "State/UT Tax Paid", sub_header_style)
        ws1.write(row, col + 16, "Cess Paid", sub_header_style)
        ws1.write(row, col + 17, "Eligibility For ITC", sub_header_style)
        ws1.write(row, col + 18, "Availed ITC Integrated Tax", sub_header_style)
        ws1.write(row, col + 19, "Availed ITC Central Tax", sub_header_style)
        ws1.write(row, col + 20, "Availed ITC State/UT Tax", sub_header_style)
        ws1.write(row, col + 21, "Availed ITC Cess", sub_header_style)

        row += 1

        invoice_gst_tax_lines = {}

        cdnur_invoices = refund_invoices.filtered(lambda p: not p.partner_id.vat and p.company_id.state_id != p.partner_id.state_id \
                                                     and (p.amount_untaxed_signed * -1) > B2CL_INVOICE_AMT_LIMIT and p.move_type in ('in_refund', 'out_refund'))
        self.summarize_inv_per_tax_rate(cdnur_invoices, invoice_gst_tax_lines)    #Fills invoice_gst_tax_lines

        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p:(p[0].date, p[0].name)): # invoice_gst_tax_lines.items():
            for tax_id, tax_amounts in inv_tax_lines.items():
                #tax_id = self.env['account.tax'].browse(tax_id_id)
                tax_rate = float( self.get_num(tax_amounts['name'].split('%')[0]) )    # 'GST 18% + Cess 1% (included)'
                if float_is_zero(tax_rate, precision_digits=3):     #Skip zero rated/exempted rates
                    continue
                ws1.write(row, col + 1, invoice.name, line_content_style)
                ws1.write(row, col + 2, self.format_date(invoice.invoice_date), line_content_style)
                ws1.write(row, col + 3, invoice.reversed_entry_id.name, line_content_style)
                ws1.write(row, col + 4, self.format_date(invoice.reversed_entry_id.invoice_date), line_content_style)
                ws1.write(row, col + 5, "N", line_content_style)    #Pre-GST
                ws1.write(row, col + 6, invoice.move_type == 'in_refund' and "D" or "C", line_content_style)
                ws1.write(row, col + 7, invoice.name, line_content_style)
                ws1.write(row, col + 8, "TODO", line_content_style) #Supply-Type
                ws1.write(row, col + 9, self.gst_inv_type_from_l10n(invoice), line_content_style)
                ws1.write(row, col + 10, invoice.amount_total, line_content_style)
                ws1.write(row, col + 11, tax_rate, line_content_style)
                ws1.write(row, col + 12, tax_amounts['base_amount'], line_content_style)
                ws1.write(row, col + 13, tax_amounts['igst_amount'], line_content_style)
                ws1.write(row, col + 14, tax_amounts['cgst_amount'], line_content_style)
                ws1.write(row, col + 15, tax_amounts['sgst_amount'], line_content_style)
                ws1.write(row, col + 16, tax_amounts['cess_amount'], line_content_style)
                ws1.write(row, col + 17, "", line_content_style)
                ws1.write(row, col + 18, "", line_content_style)
                ws1.write(row, col + 19, "", line_content_style)
                ws1.write(row, col + 20, "", line_content_style)
                ws1.write(row, col + 21, "", line_content_style)

                row += 1
        return invoice_gst_tax_lines

    """ Docs (Summary of Documents) """
    def generate_docs_summary_report(self, wb1):
        global all_invoices, sorted_invoices, refund_invoices, canceled_invoices
        self.ensure_one()

        ws1 = wb1.add_sheet('docs')

        # Content/Text style
        header_content_style = xlwt.easyxf("font: name Arial size 20 px, bold 1, height 170;")
        sub_header_style = xlwt.easyxf("font: name Arial size 10 px, bold 1, height 170; align: horiz center")
        sub_header_content_style = xlwt.easyxf("font: name Arial size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Arial, height 170;")
        row = 1
        col = -1
        ws1.row(row).height = 500
        ws1.write_merge(row, row, 2, 6, "Summary of documents issued", header_content_style)
        row += 2
        ws1.write(row, col + 1, "From:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_from), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "To:", sub_header_style)
        ws1.write(row, col + 2, self.format_date(self.date_to), sub_header_content_style)
        row += 1
        ws1.write(row, col + 1, "Nature of Document", sub_header_style)
        ws1.write(row, col + 2, "Sr. No. From", sub_header_style)
        ws1.write(row, col + 3, "Sr. No. To", sub_header_style)
        ws1.write(row, col + 4, "Total Number", sub_header_style)
        ws1.write(row, col + 5, "Canceled", sub_header_style)

        row += 1
        sorted_invs = all_invoices.sorted(key=lambda p: p.name)

        ws1.write(row, col + 1, "Invoices for outward supply")
        ws1.write(row, col + 2, sorted_invs[0].name)
        ws1.write(row, col + 3, sorted_invs[-1].name)
        ws1.write(row, col + 4, len(sorted_invs))
        ws1.write(row, col + 5, len(canceled_invoices)) #+ len(refund_invoices) + len(self.refunded_invoices))

    """ Utility method to summarize tax amount by rate, per invoice """
    def summarize_inv_per_tax_rate(self, invoice_list, invoice_gst_tax_lines, inv_line_filter_fn=None):
        #@invoice_list: list of invoices
        #@invoice_gst_tax_lines: returned summary by tax: {'invoice': {'gst_tax': {'name','base_amount','cess_amount'}, ...}, ...}
        #@inv_line_filter_fn: lambda function to filter invoice lines, if required (needed for IMPS and IMPG)

        invoice_gst_tax_lines.clear()
        if not inv_line_filter_fn:
            inv_line_filter_fn = lambda p: True
        #Can't use invoice.tax_line_ids directly because it will contain on individual/leaf taxes (like CGST@2.5%, SGST@2.5%)
        #while gstr2 report needs the 'group' tax (like GST@5%).
        #Iterate through invoice.invoice_line_ids.invoice_line_tax_line_ids and collect/compute from there
        for invoice in invoice_list:
            grouped_tax_lines = {}

            foreign_curr = None
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                foreign_curr = invoice.currency_id
                curr_rate_date = invoice.date or invoice.invoice_date
                company_curr = invoice.company_id.currency_id

            for inv_line in invoice.invoice_line_ids.filtered(inv_line_filter_fn):  #Filter lines if necessary (e.g. goods/service)
                price = inv_line.price_unit * (1 - (inv_line.discount or 0.0) / 100.0)
                line_taxes = inv_line.tax_ids.compute_all(price, invoice.currency_id, inv_line.quantity, inv_line.product_id, invoice.partner_id)
                if foreign_curr:
                    line_taxes['total_excluded'] = foreign_curr._convert(line_taxes['total_excluded'], company_curr, invoice.company_id, curr_rate_date)
                    line_taxes['total_included'] = foreign_curr._convert(line_taxes['total_included'], company_curr, invoice.company_id, curr_rate_date)
                    for l in line_taxes['taxes']:
                        l['amount'] = foreign_curr._convert(l['amount'], company_curr, invoice.company_id, curr_rate_date)
                        l['base'] = foreign_curr._convert(l['base'], company_curr, invoice.company_id, curr_rate_date)

                #_logger.info(line_taxes)
                #_logger.info(invoice_line.tax_ids.sorted(reverse=True))
                for ln_tx in inv_line.tax_ids: #.sorted(reverse=True):
                    gst_tax_id = None
                    if 'GST' in ln_tx.name:    # GST taxes are named 'IGST', 'SGST', 'CGST' etc
                        gst_tax_id = ln_tx.id
                        if grouped_tax_lines.get(gst_tax_id):
                            grouped_tax_lines[gst_tax_id]['base_amount'] += line_taxes['total_excluded']
                        else:
                            grouped_tax_lines[gst_tax_id] = {'name': ln_tx.name, 'base_amount': line_taxes['total_excluded'],
                                    'cess_amount': 0, 'igst_amount': 0, 'cgst_amount': 0, 'sgst_amount': 0}  #[Taxable value, Cess amount, IGST, CGST, SGST]
                        #Add Cess amount if the Cess tax is also included in this group tax
                        grouped_tax_lines[gst_tax_id]['cess_amount'] += sum(l['amount'] for l in line_taxes['taxes'] if 'GST' not in l['name'])
                        #Collect the IGST/CGST/SGST breakup for this tax rate
                        for leaf_tax in line_taxes['taxes']:
                            if 'IGST' in leaf_tax['name']:
                                 grouped_tax_lines[gst_tax_id]['igst_amount'] += leaf_tax['amount']
                            elif 'CGST' in leaf_tax['name']:
                                 grouped_tax_lines[gst_tax_id]['cgst_amount'] += leaf_tax['amount']
                            elif 'SGST' in leaf_tax['name'] or 'UTGST' in leaf_tax['name']:
                                 grouped_tax_lines[gst_tax_id]['sgst_amount'] += leaf_tax['amount']

                    elif gst_tax_id:      #CESS and other non-GST taxes
                        #TODO:Make the bold assumption that CESS is applied *after* GST taxes, so grouped_tax_lines[gst_tx_id] is already present
                        #if len(grouped_tax_lines.get(ln_tx)) > 1:
                        #Calculate CESS amount only
                        grouped_tax_lines[gst_tax_id]['cess_amount'] += sum(l['amount'] for l in line_taxes['taxes'] if 'GST' not in l['name'])
                        #else:
                        #    grouped_tax_lines[ln_tx][1] = line_taxes['total_excluded']

            invoice_gst_tax_lines[invoice] = grouped_tax_lines


    """ Utility to get integer present in a string """
    def get_num(self, x):
        return int( ''.join(ele for ele in x if ele.isdigit()))

    """ Utility to convert date/datetime to dd-mmm-yy format """
    def format_date(self, date_in):
        return datetime.strftime(date_in, "%d-%b-%y")

    """ Utility to map l10n_in_gst_treatment to Invoice Type in GSTR excel format """
    def gst_inv_type_from_l10n(self, invoice):
        inv_type_gst = inv_tye_map[invoice.l10n_in_gst_treatment] if invoice.l10n_in_gst_treatment else "Regular"
        if inv_type_gst.startswith('SEZ'):
            with_or_without = "without" if invoice.amount_tax == 0.00 else "with"
            inv_type_gst = inv_type_gst.format(with_or_without)     #SEZ with/without payment
        return inv_type_gst

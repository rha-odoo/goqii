from odoo.tests import tagged
from .testcases import GSTRTestcases
from datetime import date
import xlwt

@tagged('post_install', '-at_install')
class CheckReport2(GSTRTestcases):
    def test_gstr2(self):
        today = date.today()
        gstr2 = self.env['texbyte_gstr.report.gstr2'].create({'date_from': today, 'date_to': today})
        xl_workbook = xlwt.Workbook(encoding='utf-8')
        print("----------GSTR2--------")
        gstr2.get_valid_invoices()
        b2b = gstr2.generate_b2b_report(xl_workbook)
        b2b_vals = self.compute_value(b2b)
        print("B2B TAXABLE, Expected: %d; Received: %d " % (2000, b2b_vals[0]))
        self.assertEqual(b2b_vals[0], 2000.0)
        self.assertEqual(b2b_vals[1], 50.0)
        self.assertEqual(b2b_vals[2], 25.0)
        self.assertEqual(b2b_vals[3], 25.0)

        b2bur = gstr2.generate_b2bur_report(xl_workbook)
        b2bur_vals = self.compute_value(b2bur)
        print("B2BUR TAXABLE, Expected: %d; Received: %d " % (2000, b2bur_vals[0]))
        self.assertEqual(b2bur_vals[0], 2000.0)
        self.assertEqual(b2bur_vals[1], 50.0)
        self.assertEqual(b2bur_vals[2], 25.0)
        self.assertEqual(b2bur_vals[3], 25.0)

        cdnr = gstr2.generate_cdnr_report(xl_workbook)
        cdnr_vals = self.compute_value(cdnr)
        print("CDNR TAXABLE, Expected: %d; Received: %d " % (500, cdnr_vals[0]))
        self.assertEqual(cdnr_vals[0], 500.0)
        self.assertEqual(cdnr_vals[1], 0.0)
        self.assertEqual(cdnr_vals[2], 12.5)
        self.assertEqual(cdnr_vals[3], 12.5)

        cdnur = gstr2.generate_cdnur_report(xl_workbook)
        cdnur_vals = self.compute_value(cdnur)

        imps = gstr2.generate_imps_report(xl_workbook)
        imps_vals = self.compute_value(imps)
        print("IMPS TAXABLE, Expected: %d; Received: %d " % (4500, imps_vals[0]))
        self.assertEqual(imps_vals[0], 4500.0)
        self.assertEqual(imps_vals[1], 225.0)
        self.assertEqual(imps_vals[2], 0.0)
        self.assertEqual(imps_vals[3], 0.0)

        impg = gstr2.generate_impg_report(xl_workbook)
        impg_vals = self.compute_value(impg)
        print("IMPG TAXABLE, Expected: %d; Received: %d " % (6000, impg_vals[0]))
        self.assertEqual(impg_vals[0], 6000.0)
        self.assertEqual(impg_vals[1], 300.0)
        self.assertEqual(impg_vals[2], 0.0)
        self.assertEqual(impg_vals[3], 0.0)

        hsn = gstr2.generate_hsn_report(xl_workbook)
        hsn_in_vals = self.compute_hsn(hsn)
        print("HSN IN PRODUCT A TAXABLE:, Expected: %d; Received: %d " % (500, hsn_in_vals['Product A'][2]))
        self.assertEqual(hsn_in_vals['Product A'][2], 500.0)
        self.assertEqual(hsn_in_vals['Product A'][3], 0.0)
        self.assertEqual(hsn_in_vals['Product A'][4], 12.5)
        self.assertEqual(hsn_in_vals['Product A'][5], 12.5)
        print("HSN IN PRODUCT B TAXABLE:, Expected: %d; Received: %d " % (8000, hsn_in_vals['Product B'][2]))
        self.assertEqual(hsn_in_vals['Product B'][2], 8000.0)
        self.assertEqual(hsn_in_vals['Product B'][3], 400.0)
        self.assertEqual(hsn_in_vals['Product B'][4], 0.0)
        self.assertEqual(hsn_in_vals['Product B'][5], 0.0)
        print("HSN IN PRODUCT LARGE TAXABLE:, Expected: %d; Received: %d " % (-280000.0, hsn_in_vals['Product Large'][2]))
        self.assertEqual(hsn_in_vals['Product Large'][2], -280000.0)
        self.assertEqual(hsn_in_vals['Product Large'][3], -14000.0)
        self.assertEqual(hsn_in_vals['Product Large'][4], 0.0)
        self.assertEqual(hsn_in_vals['Product Large'][5], 0.0)
        print("HSN IN SERVICE1 TAXABLE:, Expected: %d; Received: %d " % (1000, hsn_in_vals['Service 1'][2]))
        self.assertEqual(hsn_in_vals['Service 1'][2], 1000.0)
        self.assertEqual(hsn_in_vals['Service 1'][3], 0.0)
        self.assertEqual(hsn_in_vals['Service 1'][4], 25.0)
        self.assertEqual(hsn_in_vals['Service 1'][5], 25.0)
        print("HSN IN SERVICE2 TAXABLE:, Expected: %d; Received: %d " % (4500, hsn_in_vals['Service 2'][1]))
        self.assertEqual(hsn_in_vals['Service 2'][2], 4500.0)
        self.assertEqual(hsn_in_vals['Service 2'][3], 225.0)
        self.assertEqual(hsn_in_vals['Service 2'][4], 0.0)
        self.assertEqual(hsn_in_vals['Service 2'][5], 0.0)

    def compute_value(self, invoice_gst_tax_lines):
        taxable = 0
        igst = 0
        sgst = 0
        cgst = 0
        for invoice, inv_tax_lines in sorted(invoice_gst_tax_lines.items(), key=lambda p: (p[0].date, p[0].name)):
            for tax_id, tax_amounts in inv_tax_lines.items():
                taxable += tax_amounts['base_amount']
                igst += tax_amounts['igst_amount']
                cgst += tax_amounts['cgst_amount']
                sgst += tax_amounts['sgst_amount']
        return taxable, igst, cgst, sgst

    def compute_hsn(self, hsn_vals):
        hsn_vals_updated = {}
        for product_hsn, hsn_sum in sorted(hsn_vals.items(), key=lambda p: p[0].name):
            vals = []
            vals.append(hsn_sum[0])  # hsn quantity
            vals.append(hsn_sum[1])  # total value
            vals.append(hsn_sum[2])  # taxable value
            vals.append(hsn_sum[3])  # igst
            vals.append(hsn_sum[4])  # cgst
            vals.append(hsn_sum[5])  # sgst
            vals.append(hsn_sum[6])  # cess
            hsn_vals_updated[product_hsn.name] = vals
        return hsn_vals_updated
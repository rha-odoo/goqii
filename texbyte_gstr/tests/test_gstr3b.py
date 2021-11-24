from odoo.tests import tagged
from .testcases import GSTRTestcases
from datetime import date
import xlwt

@tagged('post_install', '-at_install')
class CheckReport3(GSTRTestcases):
    def test_gstr3(self):
        today = date.today()
        gstr3b = self.env['texbyte_gstr.report.gstr3b'].create({'date_from': today, 'date_to': today})
        xl_workbook = xlwt.Workbook(encoding='utf-8')
        print("----------GSTR3B--------")
        gstr3b.get_valid_invoices()
        vals = gstr3b.generate_3b_report(xl_workbook)

        #outward taxable supplies
        print("OUTWARD TAXABLE, Expected: %d; Received: %d " % (18200, vals[0]['taxable_value']))
        self.assertEqual(vals[0]['taxable_value'], 18200.0)
        self.assertEqual(vals[0]['igst'], 760.0)
        self.assertEqual(vals[0]['cgst'], 75.0)
        self.assertEqual(vals[0]['sgst'], 75.0)

        #outward taxable zero rated
        print("OUTWARD ZERO RATE TAXABLE, Expected: %d; Received: %d " % (6000, vals[1]['taxable_value']))
        self.assertEqual(vals[1]['taxable_value'], 6000.0)
        self.assertEqual(vals[1]['igst'], 0.0)
        self.assertEqual(vals[1]['cgst'], 0.0)
        self.assertEqual(vals[1]['sgst'], 0.0)

        #reverse charge
        print("REVERSE CHARGE TAXABLE, Expected: %d; Received: %d " % (-278000, vals[4]['taxable_value']))
        self.assertEqual(vals[4]['taxable_value'], -278000.0)
        self.assertEqual(vals[4]['igst'], -13950.0)
        self.assertEqual(vals[4]['cgst'], 25.0)
        self.assertEqual(vals[4]['sgst'], 25.0)

        #import goods
        print("IMPORT PRODUCT IGST, Expected: %d; Received: %d " % (300, vals[5]['igst']))
        self.assertEqual(vals[5]['igst'], 300.0)
        self.assertEqual(vals[5]['cgst'], 0.0)
        self.assertEqual(vals[5]['sgst'], 0.0)

        #import service
        print("IMPORT SERVICE IGST, Expected: %d; Received: %d " % (225, vals[6]['igst']))
        self.assertEqual(vals[6]['igst'], 225.0)
        self.assertEqual(vals[6]['cgst'], 0.0)
        self.assertEqual(vals[6]['sgst'], 0.0)

        #all_itc
        print("ALL ITC IGST, Expected: %d; Received: %d " % (50, vals[8]['igst']))
        print("ALL ITC IGST, Expected: %d; Received: %d " % (12.5, vals[8]['cgst']))
        print("ALL ITC IGST, Expected: %d; Received: %d " % (12.5, vals[8]['sgst']))
        self.assertEqual(vals[8]['igst'], 50.0)
        self.assertEqual(vals[8]['cgst'], 12.5)
        self.assertEqual(vals[8]['sgst'], 12.5)

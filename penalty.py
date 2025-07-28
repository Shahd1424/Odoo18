import io
import xlsxwriter
import base64
from odoo.http import request
from datetime import datetime



from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

class Penalty(models.Model):
    _name = 'penalty.penalty'
    _description = 'Penalty'
    _rec_name = 'employee_id'


    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    date = fields.Date(string="Date")
    amount = fields.Float(string="Amount per Interval", required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Done')
    ], string='Status', default='draft', tracking=True)

    duration = fields.Integer(string="Duration", required=True)
    interval = fields.Integer(string="Interval", required=True)
    contract_id = fields.Many2one('hr.contract', string='Contract')

    penalty_lines = fields.One2many('penalty.line', 'penalty_id', string="Penalty Lines")
    total_amount = fields.Float(string="Total Amount", compute="_compute_total_amount", store=True)


    debit_account_id = fields.Many2one('account.account', string="Debit Account", required=True)
    credit_account_id = fields.Many2one('account.account', string="Credit Account", required=True)
    journal_id = fields.Many2one('account.journal', string="Journal", required=True)
    move_id = fields.Many2one('account.move', string="Journal Entry", readonly=True, copy=False)

    @api.depends('amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = rec.amount

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            contract = self.env['hr.contract'].search([('employee_id', '=', self.employee_id.id)], limit=1)
            self.contract_id = contract



    def action_calculate_total(self):
        for rec in self:
            rec._compute_total_amount()




    def action_confirm(self):
        for rec in self:
            rec.penalty_lines.unlink()

            if rec.duration and rec.interval and rec.date:
                amount_per_line = rec.amount / rec.duration if rec.duration else 0
                lines = []
                for i in range(rec.duration):
                    line_date = rec.date + relativedelta(months=rec.interval * i)
                    lines.append((0, 0, {
                        'date': line_date,
                        'amount': amount_per_line,
                    }))
                rec.penalty_lines = lines
            rec.state = 'confirm'


    def action_create_entry(self):
        for rec in self:
            if not rec.debit_account_id or not rec.credit_account_id or not rec.journal_id:
                continue

            move_vals = {
                'date': rec.date,
                'journal_id': rec.journal_id.id,
                'ref': f"Penalty for {rec.employee_id.name}",
                'line_ids': [
                    (0, 0, {
                        'account_id': rec.debit_account_id.id,
                        'name': f"Penalty Debit - {rec.employee_id.name}",
                        'debit': rec.total_amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': rec.credit_account_id.id,
                        'name': f"Penalty Credit - {rec.employee_id.name}",
                        'debit': 0.0,
                        'credit': rec.total_amount,
                    }),
                ]
            }

            move = self.env['account.move'].create(move_vals)
            rec.move_id = move.id
            move.action_post()


    def action_done(self):
        for rec in self:
            rec.state = 'done'

    def set_to_draft(self):
        for rec in self:
            rec.state = 'draft'


    def action_export_report(self):
        for rec in self:
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Penalty Report')


            
            headers = ['Employee', 'Date', 'Amount', 'Duration', 'Interval', 'Total Amount', 'Contract']
            for col, header in enumerate(headers):
                sheet.write(0, col, header)

            sheet.write(1, 0, rec.employee_id.name or '')
            sheet.write(1, 1, str(rec.date) or '')
            sheet.write(1, 2, rec.amount)
            sheet.write(1, 3, rec.duration)
            sheet.write(1, 4, rec.interval)
            sheet.write(1, 5, rec.total_amount)
            sheet.write(1, 6, rec.contract_id.name or '')

            sheet.write(3, 0, "Penalty Lines:")
            sheet.write(4, 0, "Date")
            sheet.write(4, 1, "Amount")
            for index, line in enumerate(rec.penalty_lines, start=5):
                sheet.write(index, 0, str(line.date))
                sheet.write(index, 1, line.amount)

            workbook.close()
            output.seek(0)
            xlsx_data = output.read()
            request.env.cr.commit()
            request.env.cr.commit()

            attachment = self.env['ir.attachment'].create({
                'name': 'penalty_report.xlsx',
                'type': 'binary',
                'datas': base64.b64encode(xlsx_data),
                'res_model': self._name,
                'res_id': rec.id,
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }

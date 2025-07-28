import io
import xlsxwriter
import base64
from odoo.http import request
from datetime import datetime

from odoo import models, fields, api

class PenaltyLine(models.Model):
    _name = 'penalty.line'
    _description = 'Penalty Line'

    penalty_id = fields.Many2one('penalty.penalty', string='Penalty')

    date = fields.Date(string="Date")
    amount = fields.Float(string="Amount")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self._context.get('default_penalty_id'):
            res['penalty_id'] = self._context['default_penalty_id']
        return res


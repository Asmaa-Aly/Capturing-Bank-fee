# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class Payment(models.Model):
    _inherit = 'account.payment'

    fee_amount = fields.Float(string="bank Fee Amount", tracking=True, copy=False)
    fee_account_id = fields.Many2one('account.account', 'Fees account', tracking=True, copy=False)
    fee_type = fields.Selection([('is_included', 'is included'), ('is_excluded', 'is excluded'), ], string="Bank Fee type", tracking=True, copy=False)


    @api.constrains('fee_amount')
    def check_fee_amount(self):
        if self.amount != 0.0 or self.fee_amount != 0.0:
            if self.fee_amount < 0.0 or self.fee_amount >= self.amount:
                raise ValidationError(_("Fee amount can not be less than Zero and  Greater than payment amount"))


    def action_post(self):

        payment_display_name = {
            'outbound-customer': _("Customer Reimbursement"),
            'inbound-customer': _("Customer Payment"),
            'outbound-supplier': _("Vendor Payment"),
            'inbound-supplier': _("Vendor Reimbursement"),
        }
        for rec in self:
            account_move_line = self.env['account.move.line']

            name = account_move_line._get_default_line_name(
                payment_display_name['%s-%s' % (rec.payment_type, rec.partner_type)],
                rec.amount,
                rec.currency_id,
                rec.date,
                partner=rec.partner_id)  # Create with label as attached on file


            if rec.fee_amount > 0:
                # Validate YOU FEE TYPE SELECTED
                if not self.fee_type:
                    raise ValidationError(_("You must select Fee Type"))

                # Create Bank Fee Line without check Balance
                account_move_line.with_context(check_move_validity=False).create({
                    'account_id': rec.fee_account_id.id,
                    'partner_id': rec.partner_id.id,
                    'name': f"{_('Bank fee')} for " + name,
                    'debit': rec.fee_amount,
                    'credit': 0.00,
                    'move_id': rec.move_id.id
                })

                if rec.fee_type == 'is_excluded':
                    # Create Bank Fee Line with outgoing account  without check Balance and using outgoing account more than one
                    account_move_line.with_context(check_move_validity=False, skip_account_move_synchronization=True).create({
                        'account_id': rec.journal_id.payment_credit_account_id.id,
                        'partner_id': rec.partner_id.id,
                        'name': f"{_('Bank fee')} for " + name,
                        'debit': 0.00,
                        'credit': rec.fee_amount,
                        'move_id': rec.move_id.id
                    })


                if rec.fee_type == 'is_included':
                    # Modify payable account amount to balance journal and reconcile with bank fee WITHOUT UNLINK RECORD and create again
                    for line in rec.move_id.line_ids:
                        if line.account_id == rec.destination_account_id and line.debit > rec.fee_amount:
                            line.debit = line.debit - rec.fee_amount

            res = super(Payment, self).action_post()
            return res

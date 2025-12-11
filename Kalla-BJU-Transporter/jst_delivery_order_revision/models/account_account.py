from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    is_for_driver_remaining_bop = fields.Boolean(
        string='Akun untuk Sisa BOP Driver',
        help='Tandai akun ini sebagai akun untuk sisa BOP driver yang dikembalikan'
    )

    @api.constrains('is_for_driver_remaining_bop')
    def _check_unique_driver_remaining_bop(self):
        """Memastikan hanya ada satu record dengan is_for_driver_remaining_bop = True"""
        for record in self:
            if record.is_for_driver_remaining_bop:
                # Cari record lain yang juga True (exclude record saat ini)
                other_records = self.search([
                    ('is_for_driver_remaining_bop', '=', True),
                    ('id', '!=', record.id)
                ])
                if other_records:
                    raise ValidationError(
                        'Hanya boleh ada satu Account yang ditandai sebagai '
                        'Driver Remaining BOP. Account "%s" sudah ditandai.' % other_records[0].name
                    )

    def write(self, vals):
        """Override write untuk menangani update field"""
        # Jika ada yang di-set True, set yang lain menjadi False secara otomatis
        if vals.get('is_for_driver_remaining_bop'):
            other_records = self.search([
                ('is_for_driver_remaining_bop', '=', True),
                ('id', 'not in', self.ids)
            ])
            if other_records:
                raise ValidationError(
                    'Account "%s" (Code: %s) sudah ditandai sebagai Driver Remaining BOP.\n\n'
                    'Untuk mengubahnya, silakan nonaktifkan account tersebut terlebih dahulu, '
                    'atau gunakan tombol konfirmasi yang muncul.' % (
                        other_records.name,
                        other_records.code
                    )
                )
                # other_records.write({'is_for_driver_remaining_bop': False})

        return super(AccountAccount, self).write(vals)

    @api.model
    def create(self, vals):
        """Override create untuk menangani pembuatan record baru"""
        if vals.get('is_for_driver_remaining_bop'):
            # Set record lain menjadi False
            other_records = self.search([('is_for_driver_remaining_bop', '=', True)])
            if other_records:
                raise ValidationError(
                    'Account "%s" (Code: %s) sudah ditandai sebagai Driver Remaining BOP.\n\n'
                    'Untuk mengubahnya, silakan nonaktifkan account tersebut terlebih dahulu.' % (
                        other_records.name,
                        other_records.code
                    )
                )
                # other_records.write({'is_for_driver_remaining_bop': False})

        return super(AccountAccount, self).create(vals)
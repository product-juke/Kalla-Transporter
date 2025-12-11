from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re


class EmergencyContactRelationship(models.Model):
    _name = 'emergency.contact.relationship'
    _description = 'Emergency Contact Relationship'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Relationship Name',
        required=True,
        help='Name of the relationship (e.g., Spouse, Parent, Child)'
    )

    # code = fields.Char(
    #     string='Code',
    #     required=True,
    #     help='Unique code for the relationship'
    # )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of appearance in selection'
    )

    description = fields.Text(
        string='Description',
        help='Description of the relationship type'
    )

    active = fields.Boolean(
        default=True,
        help='Set to false to hide this relationship without deleting it'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Company this relationship belongs to'
    )

    _sql_constraints = [
        # ('code_unique', 'UNIQUE(code, company_id)', 'Relationship code must be unique per company!'),
        ('name_unique', 'UNIQUE(name, company_id)', 'Relationship name must be unique per company!')
    ]

    # @api.constrains('code')
    # def _check_code_format(self):
    #     """Validate code format"""
    #     for record in self:
    #         if record.code:
    #             if not re.match(r'^[a-z0-9_]+$', record.code):
    #                 raise ValidationError(
    #                     "Code must contain only lowercase letters, numbers, and underscores."
    #                 )


class EmergencyContact(models.Model):
    _name = 'emergency.contact'
    _description = 'Emergency Contact'
    _order = 'name'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(
        string='Contact Name',
        required=True,
        help='Name of the emergency contact person'
    )

    phone = fields.Char(
        string='Phone Number',
        required=True,
        help='Phone number of the emergency contact'
    )

    relationship = fields.Selection([
        ('spouse', 'Spouse'),
        ('parent', 'Parent'),
        ('child', 'Child'),
        ('sibling', 'Sibling'),
        ('relative', 'Other Relative'),
        ('friend', 'Friend'),
        ('colleague', 'Colleague'),
        ('neighbor', 'Neighbor'),
        ('other', 'Other')
    ], string='Relationship', required=True, default='spouse',
        help='Relationship with the driver')

    relationship_id = fields.Many2one(
        'emergency.contact.relationship',
        string='Relationship',
        required=True,
        help='Relationship with the driver'
    )

    relationship_note = fields.Char(
        string='Relationship Details',
        help='Additional details about the relationship (e.g., "Mother-in-law", "Best Friend")'
    )

    # Driver relation
    driver_id = fields.Many2one(
        'hr.employee',
        string='Driver',
        required=True,
        # domain=[('is_driver', '=', True)],
        ondelete='cascade',
        help='Driver associated with this emergency contact'
    )

    # Additional Information
    email = fields.Char(
        string='Email',
        help='Email address of the emergency contact'
    )

    address = fields.Text(
        string='Address',
        help='Address of the emergency contact'
    )

    is_primary = fields.Boolean(
        string='Primary Contact',
        default=False,
        help='Mark as primary emergency contact'
    )

    notes = fields.Text(
        string='Notes',
        help='Additional notes about this emergency contact'
    )

    # System fields
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    # Computed fields
    display_name_full = fields.Char(
        string='Full Display Name',
        compute='_compute_display_name_full',
        store=True
    )

    @api.depends('name', 'relationship_id', 'phone')
    def _compute_display_name_full(self):
        for record in self:
            relationship_name = record.relationship_id.name if record.relationship_id else 'Unknown'
            record.display_name_full = f"{record.name} ({relationship_name}) - {record.phone}"

    @api.constrains('phone')
    def _check_phone_format(self):
        """Validate phone number format"""
        for record in self:
            if record.phone:
                # Remove spaces, dashes, and parentheses for validation
                phone_clean = re.sub(r'[\s\-\(\)]', '', record.phone)
                # Check if it contains only digits and + sign
                if not re.match(r'^\+?[\d]+$', phone_clean):
                    raise ValidationError(
                        f"Phone number '{record.phone}' format is invalid. "
                        "Please use a valid phone number format."
                    )
                # Check minimum length
                if len(phone_clean.replace('+', '')) < 8:
                    raise ValidationError(
                        "Phone number must be at least 8 digits long."
                    )

    @api.constrains('email')
    def _check_email_format(self):
        """Validate email format"""
        for record in self:
            if record.email:
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, record.email):
                    raise ValidationError(
                        f"Email '{record.email}' format is invalid."
                    )

    @api.constrains('is_primary', 'driver_id')
    def _check_primary_contact_unique(self):
        """Ensure only one primary contact per driver"""
        for record in self:
            if record.is_primary:
                existing_primary = self.search([
                    ('driver_id', '=', record.driver_id.id),
                    ('is_primary', '=', True),
                    ('id', '!=', record.id)
                ])
                if existing_primary:
                    raise ValidationError(
                        f"Driver '{record.driver_id.name}' already has a primary emergency contact. "
                        "Please uncheck the primary contact flag from the existing one first."
                    )

    @api.model
    def create(self, vals):
        """Override create to handle primary contact logic"""
        # If this is the first emergency contact for the driver, make it primary
        if vals.get('driver_id') and not vals.get('is_primary'):
            existing_contacts = self.search([('driver_id', '=', vals['driver_id'])])
            if not existing_contacts:
                vals['is_primary'] = True

        return super().create(vals)

    @api.model
    def _create_default_relationships(self):
        """Create default relationship types if they don't exist"""
        default_relationships = [
            {'name': 'Suami/Istri', 'sequence': 1,
             'description': 'Pasangan hidup (suami atau istri)'},
            {'name': 'Orang Tua', 'sequence': 2, 'description': 'Ayah atau ibu'},
            {'name': 'Anak', 'sequence': 3, 'description': 'Anak kandung atau anak angkat'},
            {'name': 'Saudara Kandung', 'sequence': 4, 'description': 'Kakak atau adik'},
            {'name': 'Keluarga Lain', 'sequence': 5,
             'description': 'Keluarga besar (paman, tante, sepupu, dll)'},
            {'name': 'Teman', 'sequence': 6, 'description': 'Teman pribadi atau sahabat'},
            {'name': 'Rekan Kerja', 'sequence': 7,
             'description': 'Teman atau atasan di tempat kerja'},
            {'name': 'Tetangga', 'sequence': 8,
             'description': 'Orang yang tinggal di sekitar tempat tinggal'},
            {'name': 'Lainnya', 'sequence': 9, 'description': 'Jenis hubungan lainnya'},
        ]

        RelationshipModel = self.env['emergency.contact.relationship']
        for rel_data in default_relationships:
            existing = RelationshipModel.search([
                ('company_id', '=', self.env.company.id)
            ])
            if not existing:
                RelationshipModel.create(rel_data)

    # def name_get(self):
    #     """Custom name display"""
    #     result = []
    #     for record in self:
    #         relationship_name = record.relationship_id.name if record.relationship_id else 'Unknown'
    #         name = f"{record.name} ({relationship_name})"
    #         result.append((record.id, name))
    #     return result
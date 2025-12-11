import odoo, datetime, logging, tempfile, os
from odoo import http
from odoo.http import request
from odoo.service import db
from odoo.tools.misc import file_open, str2bool
from odoo import api, SUPERUSER_ID
from odoo.http import content_disposition, dispatch_rpc, request, Response
from odoo.addons.web.controllers.database import Database as DB

_logger = logging.getLogger(__name__)

# @http.route('/web/database/backup', type='http', auth="none", methods=['POST'], csrf=False)
# def backup(self, master_pwd, name, backup_format='zip'):
#     insecure = odoo.tools.config.verify_admin_password('admin')
#     if insecure and master_pwd:
#         dispatch_rpc('db', 'change_admin_password', ["admin", master_pwd])
#     try:
#         odoo.service.db.check_super(master_pwd)
#         ts = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
#         filename = "%s_%s.%s" % (name, ts, backup_format)
#         headers = [
#             ('Content-Type', 'application/octet-stream; charset=binary'),
#             ('Content-Disposition', content_disposition(filename)),
#         ]
#         dump_stream = odoo.service.db.dump_db(name, None, backup_format)
#
#         registry = odoo.registry(name)
#         with registry.cursor() as cr:
#             env = api.Environment(cr, SUPERUSER_ID, {})
#
#             param_key = [
#                 'jst_integration_bju.url_bju'
#             ]
#             for key in param_key:
#                 env.cr.execute(
#                     "UPDATE ir_config_parameter SET value = '-' WHERE key = '%s';" % key
#                 )
#
#         response = Response(dump_stream, headers=headers, direct_passthrough=True)
#         return response
#     except Exception as e:
#         _logger.exception('Database.backup')
#         error = "Database backup error: %s" % (str(e) or repr(e))
#         return self._render_template(error=error)
#
# DB.backup = backup


@http.route('/web/database/restore', type='http', auth="none", methods=['POST'], csrf=False, max_content_length=None)
def restore(self, master_pwd, backup_file, name, copy=False, neutralize_database=False):
    insecure = odoo.tools.config.verify_admin_password('admin')
    if insecure and master_pwd:
        dispatch_rpc('db', 'change_admin_password', ["admin", master_pwd])
    try:
        data_file = None
        db.check_super(master_pwd)
        with tempfile.NamedTemporaryFile(delete=False) as data_file:
            backup_file.save(data_file)
        db.restore_db(name, data_file.name, str2bool(copy), neutralize_database)

        registry = odoo.registry(name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})

            param_key = [
                'jst_integration_bju.url_bju'
            ]
            for key in param_key:
                env.cr.execute(
                    "UPDATE ir_config_parameter SET value = '-' WHERE key = '%s';" % key
                )

        return request.redirect('/web/database/manager')
    except Exception as e:
        error = "Database restore error: %s" % (str(e) or repr(e))
        return self._render_template(error=error)
    finally:
        if data_file:
            os.unlink(data_file.name)

DB.restore = restore
# -*- coding: utf-8 -*-

from . import models


def _post_init_hook(env):
    user = env['res.users'].search(
        [('login', '=', 'abo.hemaia@gmail.com')], limit=1)
    if not user:
        user = env['res.users'].search(
            [('email', '=', 'abo.hemaia@gmail.com')], limit=1)
    if user:
        group = env.ref('LeadersITS_HR.group_lits_operation_data',
                        raise_if_not_found=False)
        if group:
            group.write({'users': [(4, user.id)]})

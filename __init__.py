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

    _setup_leave_types(env)


def _setup_leave_types(env):
    LeaveType = env['hr.leave.type']
    LEAVE_TYPES = [
        {
            'name': 'اجازة سنوية',
            'time_type': 'other',
            'leave_validation_type': 'no_validation',
            'request_unit': 'day',
            'requires_allocation': 'no',
            'sequence': 1,
            'color': 1,
        },
        {
            'name': 'اجازة عارضة',
            'time_type': 'other',
            'leave_validation_type': 'no_validation',
            'request_unit': 'day',
            'requires_allocation': 'no',
            'sequence': 2,
            'color': 2,
        },
        {
            'name': 'اجازة مرضي',
            'time_type': 'other',
            'leave_validation_type': 'no_validation',
            'request_unit': 'day',
            'requires_allocation': 'no',
            'sequence': 3,
            'color': 3,
        },
        {
            'name': 'اجازة تعويض بدل',
            'time_type': 'other',
            'leave_validation_type': 'no_validation',
            'request_unit': 'day',
            'requires_allocation': 'no',
            'sequence': 4,
            'color': 4,
        },
        {
            'name': 'غياب',
            'time_type': 'leave',
            'leave_validation_type': 'no_validation',
            'request_unit': 'day',
            'requires_allocation': 'no',
            'sequence': 5,
            'color': 5,
        },
        {
            'name': 'مامورية',
            'time_type': 'other',
            'leave_validation_type': 'no_validation',
            'request_unit': 'hour',
            'requires_allocation': 'no',
            'sequence': 6,
            'color': 6,
        },
        {
            'name': 'اذن مدفوع',
            'time_type': 'other',
            'leave_validation_type': 'no_validation',
            'request_unit': 'hour',
            'requires_allocation': 'no',
            'sequence': 7,
            'color': 7,
        },
        {
            'name': 'اذن غير مدفوع',
            'time_type': 'other',
            'leave_validation_type': 'no_validation',
            'request_unit': 'hour',
            'requires_allocation': 'no',
            'sequence': 8,
            'color': 8,
        },
    ]

    existing = LeaveType.with_context(active_test=False).search([])
    existing.write({'active': False})

    for lt_vals in LEAVE_TYPES:
        match = LeaveType.with_context(active_test=False).search(
            [('name', 'ilike', lt_vals['name'])], limit=1)
        if match:
            safe_vals = {k: v for k, v in lt_vals.items()
                         if k != 'requires_allocation'}
            safe_vals['active'] = True
            match.write(safe_vals)
        else:
            LeaveType.create(lt_vals)

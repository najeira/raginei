# -*- coding: utf-8 -*-
"""
raginei.ext.csrf
================

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import uuid
import base64
from raginei.app import session, abort, template_func, view_middleware
from raginei.helpers import to_markup, input_tag, form_tag as form_tag_base
from raginei.util import jinja2


_exempts = []

def exempt(f):
  _exempts.append(f)
  return f


@template_func
def csrf_token():
  if '_csrf' not in session:
    session['_csrf'] = base64.b32encode(uuid.uuid4().bytes)[:8].lower()
  return session['_csrf']


@template_func
@jinja2.environmentfunction
def csrf_tag(env, **kwds):
  return input_tag(env, 'hidden', '_csrf', csrf_token(), **kwds)


@template_func
@jinja2.environmentfunction
def form_tag(env, *args, **kwds):
  result = form_tag_base(env, *args, **kwds)
  result += csrf_tag(env)
  return to_markup(env, result)


@view_middleware
def protect_from_csrf(request, view_func, view_args):
  if not request.is_post or request.is_taskqueue:
    return
  csrf_token = session.get('_csrf')
  if csrf_token:
    form_token = request.form.get('_csrf')
    if csrf_token == form_token:
      return
  if view_func not in _exempts:
    abort('CSRF detected.', 400)

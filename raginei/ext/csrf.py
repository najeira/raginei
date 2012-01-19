# -*- coding: utf-8 -*-

import uuid
import base64

import jinja2

from raginei.app import session, abort, template_func
from raginei.helpers import to_markup, input_tag, form_tag as form_tag_base


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


def register(server):
  @server.request_middleware
  def protect(request):
    if request.is_get or request.is_taskqueue:
      return
    csrf_token = session.get('_csrf')
    if csrf_token:
      form_token = request.form.get('_csrf')
      if csrf_token == form_token:
        return
    view_func = server.view_functions.get(request.endpoint)
    if view_func not in _exempts:
      abort('CSRF detected.', 400)

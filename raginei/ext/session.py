# -*- coding: utf-8 -*-
"""
raginei.ext.session
===================

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import datetime
from werkzeug.contrib.securecookie import SecureCookie
from raginei.app import current_app, request, local, template_func, \
  request_middleware, response_middleware
from raginei.ext.csrf import csrf_token


@request_middleware
def load_session_from_cookie(request):
  secret = current_app.config.get('session_secret')
  if secret:
    session_name = current_app.config.get('session_cookie_name') or 'session'
    local.session = SecureCookie.load_cookie(request, session_name, secret_key=secret)
    request._flash = local.session.pop('_flash', {})
    csrf_token() # all session should have csrf token
  else:
    local.session = {}
  local.session['_flash'] = {}


@response_middleware
def save_session_to_cookie(response):
  secret = current_app.config.get('session_secret')
  if secret:
    session = local.session
    if session:
      if not isinstance(session, SecureCookie):
        session = SecureCookie(session, secret)
      expires = None
      lifetime = current_app.config.get('session_lifetime')
      if lifetime:
        expires = datetime.datetime.utcnow() + datetime.timedelta(seconds=lifetime)
      session_name = current_app.config.get('session_cookie_name') or 'session'
      session.save_cookie(response, session_name, expires=expires)


def flash(message, category=''):
  local.session['_flash'][category] = message


@template_func
def get_flashed_message(category=''):
  try:
    return request._flash[category]
  except (AttributeError, KeyError):
    return ''

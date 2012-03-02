# -*- coding: utf-8 -*-

import datetime
from werkzeug.contrib.securecookie import SecureCookie
from raginei.app import current_app, request, local, template_func, \
  request_middleware, response_middleware
from raginei.ext.csrf import csrf_token


@request_middleware
def load_session_from_cookie(request):
  secret = current_app.config.get('session_secret')
  if secret:
    local.session = SecureCookie.load_cookie(request,
      current_app.config.get('session_cookie_name') or 'session', secret_key=secret)
    request._flash = local.session.pop('_flash', '')
    csrf_token() # all session should have csrf token
  else:
    local.session = {}


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
      session.save_cookie(response,
        current_app.config.get('session_cookie_name') or 'session', expires=expires)


def flash(message):
  local.session['_flash'] = message


@template_func
def get_flashed_message():
  try:
    return request._flash
  except AttributeError:
    return ''

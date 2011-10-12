# -*- coding: utf-8 -*-

import uuid
import base64
from raginei.app import session, abort

_exempts = []

def exempt(f):
  _exempts.append(f)
  return f

def gen_token():
  if '_csrf' not in session:
    session['_csrf'] = base64.b32encode(uuid.uuid4().bytes)[:8].lower()
  return session['_csrf']

def register(server):
  
  csrf_callback = server.config.get('csrf_callback')
  
  @server.request_middleware
  def protect(request):
    if not request.is_get and not request.is_taskqueue:
      csrf_token = session.get('_csrf')
      if not csrf_token or csrf_token != request.form.get('_csrf'):
        if server.view_functions.get(request.endpoint) not in _exempts:
          if csrf_callback:
            csrf_callback(request)
          abort('CSRF detected.', 400)

# -*- coding: utf-8 -*-
"""
raginei.app
===========

:copyright: (c) 2011 by najeira <najeira@gmail.com>, All rights reserved.
:license: Apache License 2.0, see LICENSE for more details.
"""

from __future__ import with_statement

import sys
import os
import logging
import functools
import time
import threading

from google.appengine.ext.ndb.tasklets import tasklet as tasklet_ndb
from google.appengine.ext.ndb.context import toplevel as toplevel_ndb

from jinja2 import Environment

from werkzeug import exceptions
from werkzeug.utils import import_string, cached_property
from werkzeug.routing import Map, Rule, RequestRedirect
from werkzeug.local import Local, LocalManager, LocalProxy

from .wrappers import Request, Response, Found, MovedPermanently
from .util import funcname

local = Local()
local_manager = LocalManager([local])

current_app = local('current_app')
request = local('request')
session = local('session')
url_adapter = local('url_adapter')
config = LocalProxy(lambda: current_app.config)

_lock = threading.RLock()
_routes = []
_context_processors = []
_template_filters = {}
_template_funcs = {}


def is_debug():
  return 'localhost' == os.environ.get('SERVER_NAME', '') or \
    os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')


def measure_time(f):
  
  if not is_debug():
    return f
  
  callee_name = funcname(f)
  
  @functools.wraps(f)
  def wrapper(*args, **kwds):
    start = time.clock()
    try:
      return f(*args, **kwds)
    finally:
      if current_app.config.get('logging_internal'):
        logging.info('%s: %.6f' % (callee_name, time.clock() - start))
  return wrapper


class Application(object):
  
  def __init__(self, config=None, **kwds):
    self.config = self.load_config(config, **kwds)
    self.view_functions = {}
    self.url_map = Map()
    self.url_map.strict_slashes = self.config.get('url_strict_slashes', False)
    self.request_class = self.config.get('request_class') or Request
    self.response_class = self.config.get('response_class') or Response
    self.template_funcs = {}
    self.template_context_processors = [_default_template_context_processor]
    self.request_middlewares = []
    self.view_middlewares = []
    self.response_middlewares = []
    self.exception_middlewares = []
    self.routing_middlewares = []
    self.error_handlers = {}
    self.jinja2_extensions = self.config.get('jinja2_extensions') or []
    self.jinja2_environment_kwargs = self.config.get('jinja2_environment_kwargs') or {}
    self.logging_internal = self.config.get('logging_internal') or False
    self.register_extensions(self.config.get('register_extensions'))
    self.load_modules(self.config.get('load_modules'))
    self.init_routes()
    self.init_templates()
  
  def load_config(self, config, **kwds):
    if not config:
      config = {}
    else:
      if isinstance(config, basestring):
        config = import_string(config)
      config = dict([(key, getattr(config, key)) for key in dir(config) if not key.startswith('_')])
    if kwds:
      config.update(kwds)
    return config
  
  def load_modules(self, modules):
    if modules:
      for name in modules:
        import_string(name)
  
  def register_extension(self, name):
    if name:
      func = import_string(name)
      func(self)
  
  def register_extension_session(self):
    self.register_extension(self.config.get(
      'extension_session', 'raginei.ext.session.register'))
  
  def register_extension_csrf(self):
    self.register_extension(self.config.get(
      'extension_csrf', 'raginei.ext.csrf.register'))
  
  def register_extensions(self, funcs):
    self.register_extension_session()
    self.register_extension_csrf()
    if funcs:
      for name in funcs:
        func = import_string(name)
        func(self)
  
  def init_routes(self):
    with _lock:
      for args, kwds, endpoint, func in _routes:
        kwds['endpoint'] = endpoint
        kwds['view_func'] = func
        self.add_url_rule(*args, **kwds)
  
  def init_templates(self):
    with _lock:
      for f in _context_processors:
        self.context_processor(f)
      for name, f in _template_filters.iteritems():
        self.template_filter(name)(f)
      for name, f in _template_funcs.iteritems():
        self.template_func(name)(f)
  
  def add_url_rule(self, rule, endpoint, view_func, **options):
    if not rule.startswith('/'):
      rule = '/' + rule
    options.setdefault('methods', ('GET', 'POST', 'OPTIONS'))
    options['endpoint'] = endpoint
    with _lock:
      self.url_map.add(Rule(rule, **options))
      self.view_functions[endpoint] = (endpoint, view_func)
  
  def make_response(self, *args, **kwds):
    if 1 == len(args) and not isinstance(args[0], basestring):
      return args[0]
    return self.response_class(*args, **kwds)
  
  @measure_time
  def process_request(self):
    if self.request_middlewares:
      for mw in self.request_middlewares:
        response = mw(request)
        if response:
          return response
  
  @measure_time
  def process_response(self, response):
    if self.response_middlewares:
      for mw in self.response_middlewares:
        response = mw(response) or response
    return response
  
  @measure_time
  def process_routing(self, endpoint):
    if self.routing_middlewares:
      for mw in self.routing_middlewares:
        endpoint = mw(request, endpoint) or endpoint
    return endpoint
  
  @measure_time
  def process_view(self, view_func):
    if self.view_middlewares:
      for mw in self.view_middlewares:
        response = mw(request, view_func, **(request.view_args))
        if response:
          return response
  
  @measure_time
  def process_exception(self, e):
    if self.exception_middlewares:
      for mw in self.exception_middlewares:
        response = mw(request, e)
        if response:
          return response
  
  def load_view_func(self, endpoint, view_func):
    with _lock:
      if isinstance(view_func, tuple):
        if 2 == len(view_func):
          view_funcname, func = view_func
          try:
            view_func = import_string('views.' + view_funcname)
          except ImportError:
            view_func = func
        elif 3 == len(view_func):
          view_classname, args, kwargs = view_func
          view_cls = import_string('views.' + view_classname)
          view_func = view_cls(*args, **kwargs)
        else:
          raise NotImplementedError()
      elif isinstance(view_func, basestring):
        view_func = import_string('views.' + view_func)
      else:
        return view_func
      assert callable(view_func)
      self.view_functions[endpoint] = view_func
      return view_func
  
  def get_view_func(self, endpoint):
    local.endpoint = endpoint = self.process_routing(endpoint)
    view_func = self.view_functions[endpoint]
    if isinstance(view_func, (tuple, basestring)):
      view_func = self.load_view_func(endpoint, view_func)
    assert callable(view_func)
    return view_func
  
  def dispatch_request(self):
    try:
      if request.routing_exception:
        raise request.routing_exception
      view_func = self.get_view_func(request.url_rule.endpoint)
      response = self.process_view(view_func)
      if response:
        return response
      try:
        return self.process_view_func(view_func, request.view_args)
      except Exception, e:
        response = self.process_exception(e)
        if response:
          return response
        raise
    except (RequestRedirect, Found), e:
      return e.get_response(None)
    except SystemExit:
      raise # Allow sys.exit() to actually exit.
    except Exception, e:
      if self.debug:
        raise
      return self.handle_exception(e)
  
  @measure_time
  def process_view_func(self, view_func, context):
    result = view_func(**context)
    if not isinstance(result, self.response_class):
      if isinstance(result, (RequestRedirect, Found)):
        result = result.get_response(None)
      elif not isinstance(result, basestring):
        result = result.get_result()
    return self.view_func_result_to_response(result)
  
  def view_func_result_to_response(self, result):
    if isinstance(result, self.response_class):
      return result
    return self.make_response(result)
  
  def _setup_template(self, view_func, template):
    if not template:
      template = view_func.__name__
    if '.' not in template:
      template = template + '.html'
    return template
  
  def handle_exception(self, e):
    handler = self.error_handlers.get(getattr(e, 'code', 500))
    return handler(e) if handler else e
  
  def init_context(self, environ):
    local.current_app = self
    local.request = self.request_class(environ)
    self.init_url_adapter(environ)
  
  def init_url_adapter(self, environ):
    local.url_adapter = url_adapter = self.url_map.bind_to_environ(environ)
    try:
      request.url_rule, request.view_args = url_adapter.match(return_rule=True)
    except exceptions.HTTPException, e:
      request.routing_exception = e
  
  def release_context(self):
    local_manager.cleanup()
  
  def override_response(self, response):
    self.override_headers(response)
    self.override_cookies(response)
  
  @measure_time
  def override_headers(self, response):
    if hasattr(response, 'headers'):
      oh = getattr(local, 'override_headers', None)
      if oh is not None:
        response.headers.extend(oh)
        del local.override_headers
  
  @measure_time
  def override_cookies(self, response):
    if hasattr(response, 'set_cookie'):
      oc = getattr(local, 'override_cookies', None)
      if oc is not None:
        for d in oc:
          response.set_cookie(d.pop('key'), **d)
        del local.override_cookies
  
  def do_run(self, environ, start_response):
    self.init_context(environ)
    try:
      ret = self.process_request()
      if not ret:
        ret = self.dispatch_request()
      response = self.make_response(ret)
      response = self.process_response(response)
      self.override_response(response)
      return response(environ, start_response)
    finally:
      self.release_context()
  
  def __call__(self, environ, start_response):
    return self.do_run(environ, start_response)
  
  @classmethod
  def instance(cls, *args, **kwds):
    obj = cls(*args, **kwds)
    # wrap the application
    if obj.debug:
      return get_debugged_application_class()(obj, evalex=True)
    return obj
  
  def run(self):
    # wrap the application
    if self.debug:
      if not getattr(self, '_debugged_application', None):
        self._debugged_application = get_debugged_application_class()(
          self, evalex=True)
      app_obj = self._debugged_application
    else:
      app_obj = self
    from wsgiref.handlers import CGIHandler
    CGIHandler().run(app_obj)
  
  def _get_traceback(self, exc_info):
    import traceback
    ret = '\n'.join(traceback.format_exception(*(exc_info or sys.exc_info())))
    try:
      return ret.decode('utf-8')
    except UnicodeDecodeError:
      return ret
  
  @property
  def jinja2_env(self):
    if not hasattr(self, '_jinja2_env'):
      self.init_jinja2_environ()
    return self._jinja2_env
  
  def iter_jinja2_extensions(self):
    for ext_str in self.jinja2_extensions:
      try:
        ext = import_string(ext_str)
      except (ImportError, AttributeError), e:
        logging.warn('Failed to import jinja2 extension %s: "%s", skipped.'
                     % (ext_str, e))
        continue
      yield ext
  
  def init_jinja2_environ(self):
    loader_name = self.config.get('jinja2_loader') or \
      'raginei.jinja2loader.FileSystemLoader'
    loader_cls = import_string(loader_name)
    template_dir = self.config.get('template_dir') or 'templates'
    env_dict = {
      'loader': loader_cls(os.path.join(self.project_root, template_dir)),
      #'undefined': NullUndefined,
      'extensions': list(self.iter_jinja2_extensions()),
      }
    env_dict.update(self.jinja2_environment_kwargs)
    self._jinja2_env = Environment(**env_dict)
  
  @cached_property
  def debug(self):
    return is_debug()
  
  @cached_property
  def project_root(self):
    parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent.endswith('lib'):
      return os.path.dirname(parent)
    return parent
  
  @cached_property
  def static_dir(self):
    path = config.get('static_dir') or '/static/'
    if not path.startswith('/'):
      path = '/' + path
    if not path.endswith('/'):
      path = path + '/'
    return path
  
  def context_processor(self, f):
    with _lock:
      self.template_context_processors.append(f)
    return f
  
  def template_filter(self, name=None):
    def decorator(f):
      with _lock:
        self.jinja2_env.filters[name or f.__name__] = f
      return f
    return decorator
  
  def template_func(self, name=None):
    def decorator(f):
      with _lock:
        self.template_funcs[name or f.__name__] = f
      return f
    return decorator
  
  def request_middleware(self, f):
    with _lock:
      self.request_middlewares.append(f)
    return f
  
  def response_middleware(self, f):
    with _lock:
      self.response_middlewares.insert(0, f)
    return f


def soft_unicode(s, encoding='utf-8'):
  if isinstance(s, unicode):
    return s
  elif isinstance(s, basestring):
    return s.decode(encoding)
  elif isinstance(s, list):
    for i, v in enumerate(s):
      s[i] = soft_unicode(v)
    return s
  elif isinstance(s, tuple):
    return tuple([soft_unicode(_) for _ in s])
  elif isinstance(s, dict):
    for k in s.iterkeys():
      s[k] = soft_unicode(s[k])
    return s
  return s


def _default_template_context_processor(request):
  values = dict(
    config=config,
    request=request,
    session=session,
  )
  values.update(current_app.template_funcs)
  return values


@measure_time
def fetch(template, **values):
  for processor in current_app.template_context_processors:
    ret = processor(request)
    if ret:
      values.update(ret)
  values['url'] = url
  return current_app.jinja2_env.get_template(
    get_template_path(template)).render(soft_unicode(values))


def render(template, **values):
  content_type = values.pop('_content_type', None) or 'text/html'
  return current_app.make_response(fetch(template, **values), content_type=content_type)


def make_redirect(endpoint, **values):
  code = values.pop('_code', 302)
  permanent = values.pop('_permanent', False)
  code = 301 if permanent else code
  cls = MovedPermanently if 301 == code else Found
  return cls(url(endpoint, **values))


def redirect(endpoint, **values):
  raise make_redirect(endpoint, **values)


def render_json(value, content_type='application/json'):
  return current_app.make_response(fetch_json(value), content_type=content_type)


def render_text(value, content_type='text/plain'):
  return current_app.make_response(value, content_type=content_type)


_BLANK_IMAGE = 'GIF89a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff!\xf9'\
  '\x04\x01\x00\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02L\x01\x00;'


def render_blank_image():
  return current_app.make_response(_BLANK_IMAGE, content_type='image/gif')


def fetch_json(value, sort_keys=True, **kwds):
  try:
    import json
  except ImportError:
    try:
      import simplejson as json
    except ImportError:
      from django.utils import simplejson as json
  return json.dumps(value, sort_keys=sort_keys, **kwds)


_EXCEPTION_MAP = {
  400: exceptions.BadRequest,
  404: exceptions.NotFound,
}


def abort(code=404, message=None):
  raise _EXCEPTION_MAP.get(code, exceptions.InternalServerError)(message)


def abort_if(condition, code=404, message=None):
  if condition:
    abort(code, message)


def get_template_path(template):
  """
  welcome.index
  /foo => /foo.html
  /foo/bar => /foo/bar.html
  /foo/bar/baz => /foo/bar/baz.html
  foo => /welcome/foo.html
  foo/bar => /welcome/foo/bar.html
  foo/bar/baz => /welcome/foo/bar/baz.html
  ..foo => /foo.html
  """
  paths = local.endpoint.split('.')
  if template:
    if template.startswith('..'):
      template = '%s/%s' % ('/'.join(paths[1:-2]), template[2:])
    elif not template.startswith('/'):
      template = '%s/%s' % ('/'.join(paths[1:-1]), template)
  else:
    template = '/'.join(paths[1:])
  if '.' not in template:
    template = template + '.html'
  return template


def get_debugged_application_class():
  from werkzeug.debug import DebuggedApplication
  return DebuggedApplication


def url(endpoint, **values):
  external = values.pop('_external', False)
  if endpoint.startswith('/'):
    ret = endpoint
  else:
    if endpoint.startswith('.'):
      endpoint = endpoint[1:]
    ret = url_adapter.build(endpoint, values, force_external=external)
    if not ret.startswith('/'):
      ret = '/' + ret
  if external:
    scheme = 'https' if request.is_secure else 'http'
    ret = '%s://%s%s' % (scheme, request.environ['SERVER_NAME'], ret)
  return ret


def tasklet(func):
  if getattr(func, '_is_tasklet_', None):
    return func
  if getattr(func, '_is_toplevel_', None):
    return func
  flet = tasklet_ndb(func)
  flet._is_tasklet_ = True
  return flet


def toplevel(func):
  if getattr(func, '_is_toplevel_', None):
    return func
  flet = toplevel_ndb(func)
  flet.__module__ = func.__module__
  flet._is_toplevel_ = True
  return flet


def route(*args, **kwds):
  def decorator(f):
    with _lock:
      flet = toplevel(f)
      endpoint = '.'.join(funcname(f).split('.')[1:])
      _routes.append( (args, kwds, endpoint, flet) )
      if current_app:
        kwds['endpoint'] = endpoint
        kwds['view_func'] = flet
        current_app.add_url_rule(*args, **kwds)
      return flet
  return decorator


def context_processor(f):
  with _lock:
    _context_processors.append(f)
  return f


def template_filter(name=None):
  def decorator(f):
    with _lock:
      _template_filters[name or f.__name__] = f
    return f
  return decorator


def template_func(name=None):
  def decorator(f):
    with _lock:
      _template_funcs[name or f.__name__] = f
    return f
  return decorator

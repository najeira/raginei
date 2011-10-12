# -*- coding: utf-8 -*-
"""
raginei.app
===========

:copyright: (c) 2011 by najeira <najeira@gmail.com>, All rights reserved.
:license: Apache License 2.0, see LICENSE for more details.
"""

import sys
import os
import logging

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
session = LocalProxy(lambda: current_app.session)
request = LocalProxy(lambda: current_app.request)
config = LocalProxy(lambda: current_app.config)

_routes = []
_context_processors = []
_template_filters = {}
_template_funcs = {}


class Application(object):
  
  def __init__(self, config=None, **kwds):
    self.config = self.load_config(config, **kwds)
    self.session = {}
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
    self.load_modules(self.config.get('load_modules'))
    self.init_functions(self.config.get('init_functions'))
  
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
  
  def init_functions(self, funcs):
    if funcs:
      for name in funcs:
        func = import_string(name)
        func(self)
    
    #defaults
    self.init_routes()
    self.init_templates()
  
  def init_routes(self):
    for args, kwds, f in _routes:
      self.route(*args, **kwds)(f)
  
  def init_templates(self):
    for f in _context_processors:
      self.context_processor(f)
    
    for name, f in _template_filters.iteritems():
      self.template_filter(name)(f)
    
    for name, f in _template_funcs.iteritems():
      self.template_func(name)(f)
  
  def add_url_rule(self, rule, endpoint, view_func=None, **options):
    options['endpoint'] = endpoint
    options.setdefault('methods', ('GET',))
    self.url_map.add(Rule(rule, **options))
    self.view_functions[endpoint] = view_func or endpoint
  
  def make_response(self, *args, **kwds):
    if 1 == len(args) and not isinstance(args[0], basestring):
      return args[0]
    return self.response_class(*args, **kwds)
  
  def process_request(self):
    if self.request_middlewares:
      for mw in self.request_middlewares:
        response = mw(self.request)
        if response:
          return response
  
  def process_response(self, response):
    if self.response_middlewares:
      for mw in self.response_middlewares:
        response = mw(response) or response
    return response
  
  def process_routing(self, endpoint):
    if self.routing_middlewares:
      for mw in self.routing_middlewares:
        endpoint = mw(self.request, endpoint) or endpoint
    return endpoint
  
  def process_view(self, view_func):
    if self.view_middlewares:
      for mw in self.view_middlewares:
        response = mw(self.request, view_func, **self.request.view_args)
        if response:
          return response
  
  def process_exception(self, e):
    if self.exception_middlewares:
      for mw in self.exception_middlewares:
        response = mw(self.request, e)
        if response:
          return response
  
  def get_view_func(self, endpoint):
    local.endpoint = endpoint = self.process_routing(endpoint)
    view_func = self.view_functions[endpoint]
    if isinstance(view_func, tuple):
      view_classname, args, kwargs = view_func
      view_cls = import_string('views.' + view_classname)
      view_func = view_cls(*args, **kwargs)
    elif isinstance(view_func, basestring):
      view_func = import_string('views.' + view_func)
    assert callable(view_func)
    self.view_functions[endpoint] = view_func
    return view_func
  
  def dispatch_request(self):
    try:
      if self.request.routing_exception:
        raise self.request.routing_exception
      view_func = self.get_view_func(self.request.url_rule.endpoint)
      response = self.process_view(view_func)
      if response:
        return response
      try:
        return self.process_view_func(view_func, self.request.view_args)
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
      return self.handle_exception(e)
  
  def process_view_func(self, view_func, context):
    value = view_func(**context)
    if isinstance(value, (tuple, list)):
      template, context = value
    elif isinstance(value, dict):
      template, context = None, value
    elif isinstance(value, basestring):
      template, context= value, None
    elif value:
      return value
    else:
      template, context= None, None
    return render(self._setup_template(view_func, template), context)
  
  def _setup_template(self, view_func, template):
    if not template:
      template = view_func.__name__
    if '.' not in template:
      template = template + '.html'
    return template
  
  def handle_exception(self, e):
    if self.debug:
      raise
    handler = self.error_handlers.get(getattr(e, 'code', 500))
    return handler(e) if handler else e
  
  def init_context(self, environ):
    local.current_app = self
    self.request = self.request_class(environ)
    self.init_url_adapter(environ)
  
  def init_url_adapter(self, environ):
    self.url_adapter = self.url_map.bind_to_environ(environ)
    try:
      self.request.url_rule, self.request.view_args = \
        self.url_adapter.match(return_rule=True)
    except exceptions.HTTPException, e:
      self.request.routing_exception = e
  
  def release_context(self):
    local_manager.cleanup()
  
  def override_response(self, response):
    self.override_headers(response)
    self.override_cookies(response)
  
  def override_headers(self, response):
    if hasattr(response, 'headers'):
      oh = getattr(local, 'override_headers', None)
      if oh is not None:
        response.headers.extend(oh)
        del local.override_headers
  
  def override_cookies(self, response):
    if hasattr(response, 'set_cookie'):
      oc = getattr(local, 'override_cookies', None)
      if oc is not None:
        for d in oc:
          response.set_cookie(d.pop('key'), **d)
        del local.override_cookies
  
  def __call__(self, environ, start_response):
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
    template_dir = self.config.get('template_dir') or 'templates'
    from .jinja2loader import FileSystemLoader, FileSystemLoaderBase
    if self.debug:
      loader = FileSystemLoaderBase
    else:
      loader = FileSystemLoader
    env_dict = {
      'loader': loader(os.path.join(self.project_root, template_dir)),
      #'undefined': NullUndefined,
      'extensions': list(self.iter_jinja2_extensions()),
      }
    env_dict.update(self.jinja2_environment_kwargs)
    self._jinja2_env = Environment(**env_dict)
  
  @cached_property
  def debug(self):
    return 'localhost' == os.environ.get('SERVER_NAME', '') or \
      os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')
  
  @cached_property
  def project_root(self):
    parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent.endswith('lib'):
      return os.path.dirname(parent)
    return parent
  
  def route(self, rule, **options):
    if not rule.startswith('/'):
      rule = '/' + rule
    options.setdefault('methods', ('GET', 'POST', 'OPTIONS'))
    def decorator(f):
      self.add_url_rule(rule, '.'.join(funcname(f).split('.')[1:]), f, **options)
      return f
    return decorator
  
  def context_processor(self, f):
    self.template_context_processors.append(f)
    return f
  
  def template_filter(self, name=None):
    def decorator(f):
      self.jinja2_env.filters[name or f.__name__] = f
      return f
    return decorator
  
  def template_func(self, name=None):
    def decorator(f):
      self.template_funcs[name or f.__name__] = f
      return f
    return decorator
  
  def request_middleware(self, f):
    self.request_middlewares.append(f)
    return f
  
  def response_middleware(self, f):
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

def fetch(template, values=None):
  values = values or {}
  for processor in current_app.template_context_processors:
    ret = processor(current_app.request)
    if ret:
      values.update(ret)
  values['url'] = url
  return current_app.jinja2_env.get_template(
    get_template_path(template)).render(soft_unicode(values))

def render(template, **values):
  content_type = values.pop('_content_type', None) or 'text/html'
  return current_app.make_response(fetch(template, values), content_type=content_type)

def redirect(endpoint, **values):
  code = values.pop('_code', 302)
  permanent = values.pop('_permanent', False)
  code = 301 if permanent else code
  cls = MovedPermanently if 301 == code else Found
  raise cls(url(endpoint, **values))

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
    import simplejson
  except ImportError:
    from django.utils import simplejson
  return simplejson.dumps(value, sort_keys=sort_keys, **kwds)

_EXCEPTION_MAP = {
  400: exceptions.BadRequest,
  404: exceptions.NotFound,
}

def abort(message=None, code=404):
  raise _EXCEPTION_MAP.get(code, exceptions.InternalServerError)(message)

def abort_if(condition, message=None, code=404):
  if condition:
    abort(message, code)

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
  import inspect
  inspect.getsourcefile = inspect.getfile
  
  from werkzeug.debug.console import HTMLStringO
  def seek(self, n, mode=0):
    pass
  def readline(self):
    if not len(self._buffer):
      return ''
    ret = self._buffer[0]
    del self._buffer[0]
    return ret
  # Apply all other patches.
  HTMLStringO.seek = seek
  HTMLStringO.readline = readline
  
  from werkzeug.debug import DebuggedApplication
  return DebuggedApplication

def url(endpoint, **values):
  external = values.pop('_external', False)
  if endpoint.startswith('/'):
    ret = endpoint
    if external:
      scheme = 'https' if request.is_secure else 'http'
      ret = '%s://%s%s' % (scheme, os.environ['SERVER_NAME'], ret)
  else:
    if endpoint.startswith('.'):
      endpoint = endpoint[1:]
    ret = current_app.url_adapter.build(endpoint, values, force_external=external)
  return ret


def route(*args, **kwds):
  def decorator(f):
    _routes.append( (args, kwds, f) )
    return f
  return decorator


def context_processor(f):
  _context_processors.append(f)
  return f


def template_filter(name=None):
  def decorator(f):
    _template_filters[name or f.__name__] = f
    return f
  return decorator


def template_func(name=None):
  def decorator(f):
    _template_funcs[name or f.__name__] = f
    return f
  return decorator

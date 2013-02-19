# -*- coding: utf-8 -*-
"""
raginei.app
===========

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

from __future__ import with_statement

import sys
import os
import time
import logging
import threading

from werkzeug import exceptions
from werkzeug.utils import import_string, cached_property
from werkzeug.urls import Href
from werkzeug.routing import Map, Rule, RequestRedirect
from werkzeug.local import Local, LocalManager, LocalProxy
from werkzeug.wsgi import get_host

from .wrappers import Request, Response, Found, MovedPermanently
from .util import funcname, json_module, is_debug, measure_time
from .ctx import Context

__all__ = [
  # classes and functions
  'toplevel', 'tasklet', 'synctasklet', 'Application', 'to_unicode',
  'route', 'template_filter', 'template_func', 'context_processor',
  'request_middleware', 'response_middleware', 'routing_middleware',
  'view_middleware', 'exception_middleware', 'fetch', 'render', 'redirect',
  'render_json', 'render_text', 'render_blank_image', 'fetch_json', 'abort',
  'abort_if', 'url',
  # variables
  'local', 'current_app', 'request', 'session', 'url_adapter', 'config',
  # external identifiers
  'import_string', 'cached_property',
]

local = Local()
local_manager = LocalManager([local])

current_app = local('current_app')
request = local('request')
session = local('session')
url_adapter = local('url_adapter')
config = LocalProxy(lambda: current_app.config)

_lock = threading.RLock()


try:
  from google.appengine.ext.ndb import toplevel as toplevel_ndb, \
    tasklet as tasklet_ndb, synctasklet as synctasklet_ndb
except ImportError:
  tasklet_ndb = toplevel_ndb = synctasklet_ndb = None


def toplevel(func):
  if not toplevel_ndb:
    return func
  return wrap_tasklet(toplevel_ndb, func)


def tasklet(func):
  if not tasklet_ndb:
    return func
  return wrap_tasklet(tasklet_ndb, func)


def synctasklet(func):
  if not synctasklet_ndb:
    return func
  return wrap_tasklet(synctasklet_ndb, func)


def wrap_tasklet(wrapper, func):
  name = '__is_%s__' % wrapper.__name__
  if getattr(func, name, None):
    return func
  flet = wrapper(func)
  flet.__module__ = func.__module__
  setattr(flet, name, True)
  return flet


class Application(object):
  
  def __init__(self, config=None, **kwds):
    self.config = self.load_config(config, **kwds)
    self.view_functions = {}
    self.url_map = Map()
    self.url_map.strict_slashes = self.config.get('url_strict_slashes', False)
    self.request_class = self.config.get('request_class') or Request
    self.response_class = self.config.get('response_class') or Response
    self.error_handlers = {}
    self.jinja2_extensions = self.config.get('jinja2_extensions') or []
    self.jinja2_environment_kwargs = self.config.get('jinja2_environment_kwargs') or {}
    self.logging_exception = self.config.get('logging_exception') or True
    self.is_first_request = True
  
  def load_config(self, config, **kwds):
    if not config:
      config = {}
    else:
      if isinstance(config, basestring):
        config = import_string(config)
      config = dict([(key, getattr(config, key))
        for key in dir(config) if not key.startswith('_')])
    if kwds:
      config.update(dict([(key, val)
        for key, val in kwds.iteritems() if not key.startswith('_')]))
    return config
  
  def init_routes(self):
    self.add_url_rule('/static/<path:filename>', endpoint='static',
      view_func=self.send_static_file)
    for endpoint, value in Context.get_routes().iteritems():
      self.add_url_rule(value[0], endpoint=endpoint, **value[1])
  
  def add_url_rule(self, rules, endpoint, view_func, **options):
    options.setdefault('methods', ('GET', 'POST', 'OPTIONS'))
    options['endpoint'] = endpoint
    if isinstance(rules, basestring):
      rules = [rules]
    for rule in rules:
      if not rule.startswith('/'):
        rule = '/' + rule
      self.url_map.add(Rule(rule, **options))
    self.view_functions[endpoint] = view_func
  
  def make_response(self, *args, **kwds):
    if 1 != len(args) or isinstance(args[0], basestring):
      return self.response_class(*args, **kwds)
    if isinstance(args[0], exceptions.HTTPException):
      return args[0].get_response(request.environ)
    return args[0]
  
  @measure_time
  def process_request(self):
    mws = Context.get_request_middlewares()
    if mws:
      for mw in mws:
        response = mw(request)
        if response:
          return response
  
  @measure_time
  def process_response(self, response):
    mws = Context.get_response_middlewares()
    if mws:
      for mw in mws:
        response = mw(response) or response
    return response
  
  @measure_time
  def process_routing(self, endpoint):
    mws = Context.get_routing_middlewares()
    if mws:
      for mw in mws:
        endpoint = mw(request, endpoint) or endpoint
    return endpoint
  
  @measure_time
  def process_view(self, view_func):
    mws = Context.get_view_middlewares()
    if mws:
      for mw in mws:
        response = mw(request, view_func, request.view_args)
        if response:
          return response
  
  @measure_time
  def process_exception(self, e):
    mws = Context.get_exception_middlewares()
    if mws:
      for mw in mws:
        response = mw(request, e)
        if response:
          return response
  
  def load_view_func(self, endpoint):
    view_func = self.view_functions[endpoint]
    if not isinstance(view_func, (tuple, basestring)):
      return view_func
    with _lock:
      view_func = self.view_functions[endpoint]
      if isinstance(view_func, tuple):
        if 3 == len(view_func):
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
    view_func = self.load_view_func(endpoint)
    assert callable(view_func)
    return view_func
  
  def dispatch_request(self):
    try:
      if request.routing_exception:
        return request.routing_exception
      view_func = self.get_view_func(request.url_rule.endpoint)
      response = self.process_view(view_func)
      if response:
        return response
      try:
        return self.call_view_func(view_func, request.view_args)
      except Exception, e:
        response = self.process_exception(e)
        if response:
          return response
        raise
    except (RequestRedirect, Found), e:
      return e.get_response(request.environ)
    except SystemExit, e:
      logging.exception(e)
      raise # Allow sys.exit() to actually exit.
    except Exception, e:
      if self.debug and not self.test:
        raise
      return self.handle_exception(e)
  
  @measure_time
  def call_view_func(self, view_func, context):
    result = view_func(**context)
    if not result:
      result = self.make_response('')
    elif not isinstance(result, self.response_class):
      if isinstance(result, (RequestRedirect, Found)):
        result = result.get_response(request.environ)
      elif not isinstance(result, basestring):
        result = result.get_result() #Future
    if isinstance(result, self.response_class):
      return result
    return self.make_response(result)
  
  def _setup_template(self, view_func, template):
    if not template:
      template = view_func.__name__
    return template
  
  def handle_exception(self, e):
    code = getattr(e, 'code', 500)
    if 500 <= code <= 599:
      if self.logging_exception:
        logging.exception(e)
    handler = self.error_handlers.get(code)
    if handler:
      return handler(e)
    if hasattr(e, 'get_response'):
      return e.get_response(request.environ)
    return exceptions.InternalServerError()
  
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
    wait_futures()
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
  
  def init_on_first_request(self):
    if self.is_first_request:
      with _lock:
        if self.is_first_request:
          self.init_routes()
          self.init_template_filters()
        self.is_first_request = False
  
  @toplevel
  def do_run(self, environ, start_response):
    self.init_on_first_request()
    self.init_context(environ)
    try:
      ret = self.process_request()
      if not ret:
        ret = self.dispatch_request()
      response = self.make_response(ret)
      response = self.process_response(response)
      response = self.make_response(response)
      self.override_response(response)
      return response(environ, start_response)
    finally:
      self.release_context()
  
  def __call__(self, environ, start_response):
    return self.do_run(environ, start_response)
  
  @classmethod
  def instance(cls, *args, **kwds):
    obj = cls(*args, **kwds)
    if obj.debug and not obj.test:
      return get_debugged_application_class()(obj, evalex=True)
    return obj
  
  def run(self, host='127.0.0.1', port=5000, **options):
    from werkzeug import run_simple
    options.setdefault('use_reloader', self.debug)
    options['use_debugger'] = False
    return run_simple(host, port, self, **options)
  
  def get_traceback(self, exc_info):
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
    try:
      from jinja2 import Environment
    except ImportError:
      self._jinja2_env = None
      return
    if self.debug or self.test:
      default_loader = 'jinja2.FileSystemLoader'
    else:
      default_loader = 'raginei.jinja2loader.FileSystemLoader'
    loader_name = self.config.get('jinja2_loader') or default_loader
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
    val = self.config.get('debug')
    if val is not None:
      return val
    return is_debug()
  
  @property
  def test(self):
    return self.config.get('test')
  
  @cached_property
  def project_root(self):
    parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent.endswith('lib'):
      return os.path.dirname(parent)
    return parent
  
  @cached_property
  def static_dir(self):
    path = self.config.get('static_dir') or '/static/'
    if not path.startswith('/'):
      path = '/' + path
    if not path.endswith('/'):
      path = path + '/'
    return path
  
  def init_template_filters(self):
    env = self.jinja2_env
    if env:
      for name, f in Context.get_template_filters().iteritems():
        env.filters[name] = f
  
  def send_static_file(self, filename, mimetype=None, attachment=None, add_etags=True):
    import mimetypes
    from werkzeug.wsgi import wrap_file
    from zlib import adler32
    
    abort_if('..' in filename)
    filename = os.path.normpath(filename)
    filename = os.path.join(self.project_root, 'static', filename)
    abort_if(not os.path.isfile(filename))
    
    file = open(filename, 'rb')
    data = wrap_file(request.environ, file)
    
    if not mimetype:
      mimetype = mimetypes.guess_type(attachment or filename)[0] or 'application/octet-stream'
    
    rv = self.make_response(data, mimetype=mimetype, direct_passthrough=True)
    
    if attachment:
      rv.headers.add('Content-Disposition', 'attachment', filename=attachment)
    
    if not self.debug:
      
      mtime = request.environ.get('CURRENT_VERSION_ID')
      if not mtime:
        mtime = os.path.getmtime(filename)
        if mtime:
          rv.last_modified = rv.date = int(mtime)
      
      rv.cache_control.public = True
      
      cache_timeout = self.config.get('static_cache_timeout', 3600) or 0
      if cache_timeout:
        rv.cache_control.max_age = cache_timeout
        rv.expires = int(time.time() + cache_timeout)
      
      if add_etags:
        rv.set_etag('%s-%s-%s' % (
          mtime, os.path.getsize(filename), adler32(
            filename.encode('utf8') if isinstance(filename, unicode) else filename
          ) & 0xffffffff))
      
      rv = rv.make_conditional(request)
    return rv


def to_unicode(s, encoding='utf-8', errors='strict'):
  if isinstance(s, unicode):
    return s
  elif isinstance(s, basestring):
    return s.decode(encoding, errors)
  elif isinstance(s, list):
    for i, v in enumerate(s):
      s[i] = to_unicode(v, encoding, errors)
    return s
  elif isinstance(s, tuple):
    return tuple([to_unicode(_, encoding, errors) for _ in s])
  elif isinstance(s, dict):
    for k in s.iterkeys():
      s[k] = to_unicode(s[k], encoding, errors)
    return s
  return s


def route(*rules, **kwds):
  def decorator(f):
    flet = synctasklet(f)
    endpoint = '.'.join(funcname(f).split('.')[1:])
    kwds['view_func'] = flet
    Context.add_route(endpoint, (rules, kwds))
    return flet
  return decorator


def template_filter(name=None):
  return _get_template_decorator(Context.add_template_filter, name)


def template_func(name=None):
  return _get_template_decorator(Context.add_template_func, name)


def _get_template_decorator(store, name):
  if name and not isinstance(name, basestring):
    store(name.__name__, name)
    return name
  def decorator(f):
    store(name or f.__name__, f)
    return f
  return decorator


def default_template_context_processor(request):
  values = dict(
    config=config,
    request=request,
    session=session,
  )
  values.update(Context.get_template_funcs())
  return values


def context_processor(f):
  Context.add_template_context_processor(f)
  return f


def request_middleware(f):
  Context.add_request_middleware(f)
  return f


def response_middleware(f):
  Context.add_response_middleware(f)
  return f


def routing_middleware(f):
  Context.add_routing_middleware(f)
  return f


def view_middleware(f):
  Context.add_view_middleware(f)
  return f


def exception_middleware(f):
  Context.add_exception_middleware(f)
  return f


@measure_time
def fetch(template, **values):
  ret = default_template_context_processor(request)
  if ret:
    values.update(ret)
  for processor in Context.get_template_context_processors():
    ret = processor(request)
    if ret:
      values.update(ret)
  values['url'] = url
  return current_app.jinja2_env.get_template(
    get_template_path(template)).render(to_unicode(values))


def render(template, **values):
  mimetype = values.pop('_mimetype', None) or 'text/html'
  content_type = values.pop('_content_type', None)
  return current_app.make_response(fetch(template, **values),
    content_type=content_type, mimetype=mimetype)


def make_redirect(endpoint, **values):
  code = values.pop('_code', 302)
  permanent = values.pop('_permanent', False)
  code = 301 if permanent else code
  cls = MovedPermanently if 301 == code else Found
  if endpoint.startswith('/'):
    url_to = Href(endpoint)(**values)
  else:
    url_to = url(endpoint, **values)
  return cls(url_to)


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
  return json_module().dumps(value, sort_keys=sort_keys, **kwds)


_EXCEPTION_MAP = {
  400: exceptions.BadRequest,
  404: exceptions.NotFound,
  503: exceptions.ServiceUnavailable,
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
  DebuggedApplication.__getattr__ = lambda x, y: getattr(x.app, y)
  return DebuggedApplication


def url(endpoint, **values):
  external = values.pop('_external', False)
  if endpoint.startswith('http://') or \
    endpoint.startswith('https://') or \
    endpoint.startswith('//'):
    return endpoint
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
    ret = '%s://%s%s' % (scheme, get_host(request.environ), ret)
  return ret


def register_future(future):
  try:
    local.futures
  except AttributeError:
    local.futures = []
  local.futures.append(future)


def wait_futures():
  try:
    for f in local.futures:
      f.wait()
    local.futures = []
  except AttributeError:
    pass


#load default modeles to register toplevel context
import helpers
import ext.session
import ext.csrf


if is_debug():
  def _enable_ctypes():
    # Enable ctypes for Jinja debugging
    try:
      from google.appengine.tools.dev_appserver import HardenedModulesHook
      assert isinstance(sys.meta_path[0], HardenedModulesHook)
      sys.meta_path[0]._white_list_c_modules.extend(['_ctypes', 'gestalt'])
    except ImportError:
      pass
  _enable_ctypes()

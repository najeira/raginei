# -*- coding:utf-8 -*-

import unittest
from base import GaeTestCase
from werkzeug.test import Client


class MyTest(GaeTestCase):
  
  def setUp(self):
    super(MyTest, self).setUp()
  
  def tearDown(self):
    super(MyTest, self).tearDown()
  
  def init_app(self, **kwds):
    from raginei import Application, Response
    app = Application.instance(test=True, **kwds)
    c = Client(app, Response)
    return app, c
  
  def test_hello_world(self):
    from raginei import route
    app, c = self.init_app()
    msg = 'Hello World!'
    @route('/')
    def hello_world():
      return msg
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, msg)
  
  def test_config(self):
    from raginei import Application
    msg = 'this_is_config'
    app = Application(this_is_config=msg)
    val = app.config['this_is_config']
    self.assertEqual(val, msg)
  
  def test_config_underscore_ignored(self):
    from raginei import Application
    msg = '_starts_with_unserscore'
    app = Application(_starts_with_unserscore=msg)
    val = app.config.get('_starts_with_unserscore')
    self.assertFalse(val)
  
  def test_make_response(self):
    app, c = self.init_app(url_strict_slashes=True)
    res = app.make_response('aaa')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'aaa')
    self.assertTrue(res.content_type.startswith('text/html'))
    res = app.make_response('bbb', content_type='text/plain')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'bbb')
    self.assertEqual(res.content_type, 'text/plain')
  
  def test_request_middleware(self):
    from raginei import request_middleware
    app, c = self.init_app()
    @request_middleware
    def middleware(req):
      self.assertTrue(req)
      return 'request_middleware'
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'request_middleware')
  
  def test_response_middleware(self):
    from raginei import route, response_middleware
    app, c = self.init_app()
    @route('/')
    def foo():
      return 'foo'
    @response_middleware
    def middleware(res):
      self.assertTrue(res)
      self.assertEqual(res.status_code, 200)
      self.assertEqual(res.data, 'foo')
      return 'response_middleware'
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'response_middleware')
  
  def test_routing_middleware(self):
    from raginei import route, routing_middleware
    app, c = self.init_app()
    @route('/')
    def foo():
      return 'foo'
    @route('/bar')
    def bar():
      return 'bar'
    @routing_middleware
    def middleware(request, endpoint):
      self.assertEqual(endpoint, 'foo')
      return 'bar'
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'bar')
  
  def test_view_middleware(self):
    from raginei import route, view_middleware
    app, c = self.init_app()
    @route('/')
    def foo():
      return 'foo'
    @view_middleware
    def middleware(request, view_func, view_args):
      self.assertTrue(request)
      self.assertTrue(view_func)
      self.assertEqual(view_func.__name__, 'foo')
      self.assertFalse(view_args)
      return 'view_middleware'
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'view_middleware')
  
  def test_exception_middleware(self):
    from raginei import route, exception_middleware
    app, c = self.init_app()
    @route('/')
    def foo():
      raise ValueError('foo')
    @exception_middleware
    def middleware(request, e):
      self.assertTrue(request)
      self.assertTrue(e)
      self.assertEqual(e.args[0], 'foo')
      return 'exception_middleware'
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'exception_middleware')
  
  def test_multi_route(self):
    from raginei import route
    app, c = self.init_app()
    @route('/foo')
    def foo():
      return 'foo'
    @route('/bar')
    def bar():
      return 'bar'
    res = c.get('/foo')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'foo', res.data)
    res = c.get('/bar')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'bar')
  
  def test_not_found(self):
    app, c = self.init_app()
    res = c.get('/unknown')
    self.assertEqual(res.status_code, 404)
  
  def test_redirect(self):
    from raginei import route, redirect
    app, c = self.init_app()
    @route('/')
    def bar():
      redirect('/foo')
    res = c.get('/')
    self.assertEqual(res.status_code, 302)
    self.assertTrue(res.headers['Location'].endswith('/foo'))
  
  def test_abort(self):
    from raginei import route, abort
    app, c = self.init_app()
    @route('/')
    def bar():
      abort()
    res = c.get('/')
    self.assertEqual(res.status_code, 404)
  
  def test_abort_with_code(self):
    from raginei import route, abort
    app, c = self.init_app()
    app.logging_exception = False
    @route('/')
    def bar():
      abort(503)
    res = c.get('/')
    self.assertEqual(res.status_code, 503)
  
  def test_abort_if_true(self):
    from raginei import route, abort_if
    app, c = self.init_app()
    @route('/')
    def bar():
      abort_if(True)
    res = c.get('/')
    self.assertEqual(res.status_code, 404)
  
  def test_abort_if_false(self):
    from raginei import route, abort_if
    app, c = self.init_app()
    @route('/')
    def bar():
      abort_if(False)
      return 'finished'
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, 'finished')
  
  def test_abort_url_for(self):
    from raginei import route, url
    app, c = self.init_app()
    @route('/')
    def bar():
      return url('bar')
    @route('/piyo')
    def piyo():
      return url('piyo')
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, '/', res.data)
    res = c.get('/piyo')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, '/piyo')
  
  def test_project_root(self):
    import os
    app, c = self.init_app()
    self.assertEqual(app.project_root, os.path.dirname(
      os.path.dirname(os.path.abspath(__file__))), app.project_root)
  
  def test_static_dir(self):
    app, c = self.init_app()
    self.assertEqual(app.static_dir, '/static/')
    app, c = self.init_app(static_dir='hoge')
    self.assertEqual(app.static_dir, '/hoge/')
    app, c = self.init_app(static_dir='/fuga')
    self.assertEqual(app.static_dir, '/fuga/')
    app, c = self.init_app(static_dir='/piyo')
    self.assertEqual(app.static_dir, '/piyo/')
  
  def test_local(self):
    from raginei import local
    app, c = self.init_app()
    self.assertTrue(local)
  
  def test_request(self):
    from raginei import route, request
    app, c = self.init_app()
    self.assertFalse(request)
    @route('/')
    def foo():
      self.assertTrue(request)
      return ''
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
  
  def test_session(self):
    from raginei import route, session
    app, c = self.init_app()
    self.assertFalse(session)
    @route('/')
    def foo():
      self.assertFalse(session)
      self.assertIsNotNone(session)
      self.assertFalse(session.get('hoge'))
      session['hoge'] = 'fuga'
      self.assertTrue(session)
      self.assertEqual(session['hoge'], 'fuga')
      return ''
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertFalse(res.headers.get('Set-Cookie'))
  
  def test_session_cookie(self):
    from raginei import route, session
    app, c = self.init_app(session_secret='session_secret')
    @route('/')
    def foo():
      self.assertTrue(session)
      self.assertTrue(session['_csrf'])
      self.assertFalse(session.get('hoge'))
      session['hoge'] = 'fuga'
      self.assertTrue(session)
      self.assertEqual(session['hoge'], 'fuga')
      return ''
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    cookie = res.headers.get('Set-Cookie', '')
    self.assertTrue(cookie)
    self.assertTrue(cookie.startswith('session="'))
  
  def test_session_cookie_keep(self):
    from raginei import route, session
    app, c = self.init_app(session_secret='session_secret')
    @route('/')
    def foo():
      return ''
    res = c.get('/')
    res2 = c.get('/')
    self.assertEqual(res.headers.get('Set-Cookie', ''), res2.headers.get('Set-Cookie', ''))


if __name__ == '__main__':
  unittest.main()

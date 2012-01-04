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
    from raginei.app import Application
    from raginei.wrappers import Response
    app = Application.instance(test=True, **kwds)
    c = Client(app, Response)
    return app, c
  
  def test_hello_world(self):
    app, c = self.init_app()
    msg = 'Hello World!'
    @app.route('/')
    def hello_world():
      return msg
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == msg, res.data
  
  def test_config(self):
    from raginei.app import Application
    msg = 'this_is_config'
    app = Application(this_is_config=msg)
    val = app.config['this_is_config']
    assert val == msg, val
  
  def test_config_underscore_ignored(self):
    from raginei.app import Application
    msg = '_starts_with_unserscore'
    app = Application(_starts_with_unserscore=msg)
    val = app.config.get('_starts_with_unserscore')
    assert not val, val

  def test_make_response(self):
    app, c = self.init_app(url_strict_slashes=True)
    res = app.make_response('aaa')
    assert res.status_code == 200, res.status_code
    assert res.data == 'aaa', res.data
    assert res.content_type.startswith('text/html'), res.content_type
    res = app.make_response('bbb', content_type='text/plain')
    assert res.status_code == 200, res.status_code
    assert res.data == 'bbb', res.data
    assert res.content_type == 'text/plain', res.content_type

  def test_request_middleware(self):
    app, c = self.init_app()
    @app.request_middleware
    def middleware(req):
      assert req
      return 'request_middleware'
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == 'request_middleware', res.data

  def test_response_middleware(self):
    app, c = self.init_app()
    @app.route('/')
    def foo():
      return 'foo'
    @app.response_middleware
    def middleware(res):
      assert res
      assert res.status_code == 200, res.status_code
      assert res.data == 'foo', res.data
      return 'response_middleware'
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == 'response_middleware', res.data
  
  def test_routing_middleware(self):
    app, c = self.init_app()
    @app.route('/')
    def foo():
      return 'foo'
    @app.route('/bar')
    def bar():
      return 'bar'
    @app.routing_middleware
    def middleware(request, endpoint):
      assert endpoint == 'foo', endpoint
      return 'bar'
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == 'bar', res.data
  
  def test_view_middleware(self):
    app, c = self.init_app()
    @app.route('/')
    def foo():
      return 'foo'
    @app.view_middleware
    def middleware(request, view_func):
      assert request
      assert view_func
      assert view_func.__name__ == 'foo'
      return 'view_middleware'
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == 'view_middleware', res.data
  
  def test_exception_middleware(self):
    app, c = self.init_app()
    @app.route('/')
    def foo():
      raise ValueError('foo')
    @app.exception_middleware
    def middleware(request, e):
      assert request
      assert e
      assert e.args[0] == 'foo'
      return 'exception_middleware'
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == 'exception_middleware', res.data
  
  def test_multi_route(self):
    app, c = self.init_app()
    @app.route('/foo')
    def foo():
      return 'foo'
    @app.route('/bar')
    def bar():
      return 'bar'
    res = c.get('/foo')
    assert res.status_code == 200, res.status_code
    assert res.data == 'foo', res.data
    res = c.get('/bar')
    assert res.status_code == 200, res.status_code
    assert res.data == 'bar', res.data
  
  def test_not_found(self):
    app, c = self.init_app()
    res = c.get('/unknown')
    assert res.status_code == 404, res.status_code
  
  def test_redirect(self):
    from raginei.app import redirect
    app, c = self.init_app()
    @app.route('/')
    def bar():
      redirect('/foo')
    res = c.get('/')
    assert res.status_code == 302, res.status_code
    assert res.headers['Location'].endswith('/foo'), res.headers
  
  def test_abort(self):
    from raginei.app import abort
    app, c = self.init_app()
    @app.route('/')
    def bar():
      abort()
    res = c.get('/')
    assert res.status_code == 404, res.status_code
  
  def test_abort_with_code(self):
    from raginei.app import abort
    app, c = self.init_app()
    @app.route('/')
    def bar():
      abort(503)
    res = c.get('/')
    assert res.status_code == 503, res.status_code
  
  def test_abort_if_true(self):
    from raginei.app import abort_if
    app, c = self.init_app()
    @app.route('/')
    def bar():
      abort_if(True)
    res = c.get('/')
    assert res.status_code == 404, res.status_code
  
  def test_abort_if_false(self):
    from raginei.app import abort_if
    app, c = self.init_app()
    @app.route('/')
    def bar():
      abort_if(False)
      return 'finished'
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == 'finished', res.data
  
  def test_abort_url_for(self):
    from raginei.app import url
    app, c = self.init_app()
    @app.route('/')
    def bar():
      return url('bar')
    @app.route('/piyo')
    def piyo():
      return url('piyo')
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == '/', res.data
    res = c.get('/piyo')
    assert res.status_code == 200, res.status_code
    assert res.data == '/piyo', res.data
  
  def test_project_root(self):
    import sys, os
    app, c = self.init_app()
    assert app.project_root == os.path.dirname(
      os.path.dirname(os.path.abspath(__file__))), app.project_root
  
  def test_static_dir(self):
    app, c = self.init_app()
    assert app.static_dir == '/static/', app.static_dir
    app, c = self.init_app(static_dir='hoge')
    assert app.static_dir == '/hoge/', app.static_dir
    app, c = self.init_app(static_dir='/fuga')
    assert app.static_dir == '/fuga/', app.static_dir
    app, c = self.init_app(static_dir='/piyo')
    assert app.static_dir == '/piyo/', app.static_dir


if __name__ == '__main__':
    unittest.main()

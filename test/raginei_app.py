﻿# -*- coding:utf-8 -*-

import unittest
from base import GaeTestCase
from werkzeug.test import Client


class MyTest(GaeTestCase):
  
  def setUp(self):
    super(MyTest, self).setUp()
  
  def tearDown(self):
    super(MyTest, self).tearDown()
  
  def init_app(self):
    from raginei.app import Application
    from raginei.wrappers import Response
    app = Application.instance(test=True)
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


if __name__ == '__main__':
    unittest.main()

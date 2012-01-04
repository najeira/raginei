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
    app = Application.instance(test=True, template_dir='test/templates', **kwds)
    c = Client(app, Response)
    return app, c
  
  def test_fetch(self):
    from raginei.app import fetch, render
    app, c = self.init_app()
    msg = 'Hello World!'
    @app.route('/')
    def hello_world():
      return fetch('test_fetch', msg=msg)
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == msg, res.data


if __name__ == '__main__':
    unittest.main()

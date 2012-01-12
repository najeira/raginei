# -*- coding:utf-8 -*-

import unittest
import datetime
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
      ret = fetch('test_fetch', msg=msg)
      assert isinstance(ret, basestring)
      return ret
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == msg, res.data
  
  def test_render(self):
    from raginei.app import fetch, render
    app, c = self.init_app()
    msg = 'Hello World!'
    @app.route('/')
    def hello_world():
      ret = render('test_fetch', msg=msg)
      assert not isinstance(ret, basestring)
      return ret
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == msg, res.data
  
  def test_helper_date(self):
    from raginei.app import fetch, render
    now = datetime.datetime.utcnow()
    app, c = self.init_app()
    @app.route('/')
    def hello_world():
      return render('test_helper_date', now=now)
    res = c.get('/')
    assert res.status_code == 200, res.status_code
    assert res.data == ('%s,%s' % (
      now.strftime('%Y/%m/%d %H:%M'), now.strftime('%Y/%m/%d'))), res.data


if __name__ == '__main__':
    unittest.main()

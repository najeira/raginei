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
    from raginei.app import route, fetch, render
    app, c = self.init_app()
    msg = 'Hello World!'
    @route('/')
    def hello_world():
      ret = fetch('test_fetch', msg=msg)
      self.assertTrue(isinstance(ret, basestring))
      return ret
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, msg)
    self.assertEqual(res.mimetype, 'text/html')
    self.assertEqual(res.content_type, 'text/html; charset=utf-8')
  
  def test_render(self):
    from raginei.app import route, fetch, render
    app, c = self.init_app()
    msg = 'Hello World!'
    @route('/')
    def hello_world():
      ret = render('test_fetch', msg=msg)
      self.assertFalse(isinstance(ret, basestring))
      return ret
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, msg)
    self.assertEqual(res.mimetype, 'text/html')
    self.assertEqual(res.content_type, 'text/html; charset=utf-8')
  
  def test_helper_date(self):
    from raginei.app import route, fetch, render
    now = datetime.datetime.utcnow()
    app, c = self.init_app()
    @route('/')
    def hello_world():
      return render('test_helper_date', now=now)
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, ('%s,%s' % (
      now.strftime('%Y/%m/%d %H:%M'), now.strftime('%Y/%m/%d'))))
  
  def test_fetch_json(self):
    from raginei.app import route, fetch_json
    app, c = self.init_app()
    @route('/')
    def hello_world():
      ret = fetch_json({'foo': 'bar', 1: 2})
      self.assertTrue(isinstance(ret, basestring))
      return ret
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, '{"1": 2, "foo": "bar"}')
    self.assertEqual(res.mimetype, 'text/html')
    self.assertEqual(res.content_type, 'text/html; charset=utf-8')
  
  def test_render_json(self):
    from raginei.app import route, render_json
    app, c = self.init_app()
    @route('/')
    def hello_world():
      ret = render_json({'foo': 'bar', 1: 2})
      self.assertFalse(isinstance(ret, basestring))
      return ret
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, '{"1": 2, "foo": "bar"}')
    self.assertEqual(res.mimetype, 'application/json')
    self.assertEqual(res.content_type, 'application/json')
  
  def test_render_text(self):
    from raginei.app import route, render_text
    app, c = self.init_app()
    msg = 'Hello World!'
    @route('/')
    def hello_world():
      ret = render_text(msg)
      self.assertFalse(isinstance(ret, basestring))
      return ret
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data, msg)
    self.assertEqual(res.mimetype, 'text/plain')
    self.assertEqual(res.content_type, 'text/plain')
  
  def test_render_blank_image(self):
    from raginei.app import route, render_blank_image
    app, c = self.init_app()
    @route('/')
    def hello_world():
      ret = render_blank_image()
      self.assertFalse(isinstance(ret, basestring))
      return ret
    res = c.get('/')
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.mimetype, 'image/gif')
    self.assertEqual(res.content_type, 'image/gif')


if __name__ == '__main__':
  unittest.main()

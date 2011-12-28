# -*- coding:utf-8 -*-

import unittest
from base import GaeTestCase

import hashlib
import datetime

from werkzeug.test import Client


class MyTest(GaeTestCase):
  
  def setUp(self):
    super(MyTest, self).setUp()
  
  def tearDown(self):
    super(MyTest, self).tearDown()
  
  def test_hello_world(self):
    from raginei.app import Application, route
    from raginei.wrappers import Response
    
    msg = 'Hello World!'
    
    @route('/')
    def hello_world():
      return msg
    
    app = Application.instance()
    
    c = Client(app, Response)
    res = c.get('/')
    
    assert res.status_code == 200, res.status_code
    assert res.data == msg, res.data
    


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-

import os
import sys
import unittest

def setup_path(gae_home):
  PROJECT_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  for v in [gae_home, os.path.join(gae_home, 'lib', 'yaml', 'lib'),
    PROJECT_HOME, os.path.join(PROJECT_HOME, 'lib')]:
    if v not in sys.path:
      sys.path.insert(0, v)
  for v in ('antlr3', 'fancy_urllib', 'graphy', 'ipaddr', 'protorpc',
    'simplejson', 'webob'):
    v = os.path.join(gae_home, 'lib', v)
    if v not in sys.path:
      sys.path.insert(0, v)


def get_base(gae_home):
  
  setup_path(gae_home)
  
  from google.appengine.ext import testbed
  
  class GaeTestCase(unittest.TestCase):
    
    def __init__(self, *args, **kwargs):
      """
      from http://code.google.com/p/appengine-py-testhelper/source/browse/trunk/gae_test_base.py
      """
      unittest.TestCase.__init__(self, *args, **kwargs)
      if hasattr(self, 'setUp'):
        self.test_setup = self.setUp
        def setup_env_and_test():
          self._env_setUp()
          self.test_setup()
        self.setUp = setup_env_and_test
      else:
        self.setUp = self._env_setUp
      if hasattr(self, 'tearDown'):
        self.test_teardown = self.tearDown
        def teardown_test_and_env():
          try:
            self.test_teardown()
          finally:
            self._env_tearDown()
        self.tearDown = teardown_test_and_env
      else:
        self.tearDown = self._env_tearDown
    
    def _env_setUp(self):
      self.testbed = testbed.Testbed()
      self.testbed.activate()
      self.testbed.init_datastore_v3_stub()
      self.testbed.init_memcache_stub()
      self.testbed.init_images_stub()
      self.testbed.init_mail_stub()
      self.testbed.init_taskqueue_stub()
      self.testbed.init_urlfetch_stub()
    
    def _env_tearDown(self):
      self.testbed.deactivate()
  
  return GaeTestCase

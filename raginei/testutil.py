# -*- coding: utf-8 -*-
"""
raginei.testutil
================

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import os
import sys
import unittest


def setup_path(DIR_PATH):
  
  if DIR_PATH:
    from .util import setup_gae_path
    setup_gae_path(DIR_PATH)
  
  PROJECT_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  sys.path.insert(0, PROJECT_HOME)
  
  LIB_PATH = os.path.join(PROJECT_HOME, 'lib')
  sys.path.insert(0, LIB_PATH)


def get_base(gae_home=None):
  
  setup_path(gae_home)
  
  import raginei.app
  
  try:
    from google.appengine.ext import testbed
  except ImportError:
    testbed = None
  
  class GaeTestCase(unittest.TestCase):
    
    def __init__(self, *args, **kwargs):
      """
      from http://code.google.com/p/appengine-py-testhelper/source/browse/trunk/gae_test_base.py
      """
      os.environ['HTTP_HOST'] = 'example.com'
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
      if testbed:
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        self.testbed.init_images_stub()
        self.testbed.init_mail_stub()
        self.testbed.init_taskqueue_stub()
        self.testbed.init_urlfetch_stub()
        
        #set mode to high replication
        from google.appengine.datastore import datastore_stub_util
        datastore_stub = self.testbed.get_stub(testbed.DATASTORE_SERVICE_NAME)
        datastore_stub.SetConsistencyPolicy(
          datastore_stub_util.TimeBasedHRConsistencyPolicy())
      
      from .ctx import Context
      Context.push()
    
    def _env_tearDown(self):
      from .ctx import Context
      Context.pop()
      if testbed:
        self.testbed.deactivate()
  
  return GaeTestCase

# -*- coding: utf-8 -*-

import os
import sys
import unittest


def setup_path(DIR_PATH):
  
  ### from dev_appserver.py
  
  SCRIPT_DIR = os.path.join(DIR_PATH, 'google', 'appengine', 'tools')
  GOOGLE_SQL_DIR = os.path.join(
      DIR_PATH, 'google', 'storage', 'speckle', 'python', 'tool')
  
  EXTRA_PATHS = [
    DIR_PATH,
    os.path.join(DIR_PATH, 'lib', 'antlr3'),
    os.path.join(DIR_PATH, 'lib', 'django_0_96'),
    os.path.join(DIR_PATH, 'lib', 'fancy_urllib'),
    os.path.join(DIR_PATH, 'lib', 'ipaddr'),
    os.path.join(DIR_PATH, 'lib', 'protorpc'),
    os.path.join(DIR_PATH, 'lib', 'webob'),
    os.path.join(DIR_PATH, 'lib', 'webapp2'),
    os.path.join(DIR_PATH, 'lib', 'yaml', 'lib'),
    os.path.join(DIR_PATH, 'lib', 'simplejson'),
    os.path.join(DIR_PATH, 'lib', 'google.appengine._internal.graphy'),
  ]
  
  GOOGLE_SQL_EXTRA_PATHS = [
    os.path.join(DIR_PATH, 'lib', 'enum'),
    os.path.join(DIR_PATH, 'lib', 'google-api-python-client'),
    os.path.join(DIR_PATH, 'lib', 'grizzled'),
    os.path.join(DIR_PATH, 'lib', 'httplib2'),
    os.path.join(DIR_PATH, 'lib', 'oauth2'),
    os.path.join(DIR_PATH, 'lib', 'prettytable'),
    os.path.join(DIR_PATH, 'lib', 'python-gflags'),
    os.path.join(DIR_PATH, 'lib', 'sqlcmd'),
  ]
  
  SCRIPT_EXCEPTIONS = {
    "dev_appserver.py" : "dev_appserver_main.py"
  }
  
  SCRIPT_DIR_EXCEPTIONS = {
    'google_sql.py': GOOGLE_SQL_DIR,
  }
  
  extra_paths = EXTRA_PATHS[:]
  if False: #FIXME
    extra_paths.extend(GOOGLE_SQL_EXTRA_PATHS)
  sys.path = extra_paths + sys.path
  
  PROJECT_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  sys.path.insert(0, PROJECT_HOME)
  
  LIB_PATH = os.path.join(PROJECT_HOME, 'lib')
  sys.path.insert(0, LIB_PATH)


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
      
      #set mode to high replication
      from google.appengine.datastore import datastore_stub_util
      datastore_stub = self.testbed.get_stub(testbed.DATASTORE_SERVICE_NAME)
      datastore_stub.SetConsistencyPolicy(
        datastore_stub_util.TimeBasedHRConsistencyPolicy())
    
    def _env_tearDown(self):
      self.testbed.deactivate()
  
  return GaeTestCase

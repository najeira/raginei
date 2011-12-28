# -*- coding: utf-8 -*-
"""
raginei.util
============

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import os
import sys


def to_str(v):
  if isinstance(v, basestring):
    return v
  elif isinstance(v, (list, tuple, set)):
    return '&'.join([to_str(x) for x in v])
  elif isinstance(v, dict):
    return '&'.join(['%s=%s' % (to_str(k), to_str(v[k])) for k in sorted(v.keys())])
  return repr(v)


def funcname(f):
  try:
    if isinstance(f.im_self, type):
      return '%s.%s.%s' % (
        f.__module__, f.im_self.__name__, f.__name__)
    return '%s.%s.%s' % (
      f.__module__, f.im_self.__class__.__name__, f.__name__)
  except AttributeError:
    return '%s.%s' % (f.__module__, getattr(f, '__name__', str(f)))


def json_module():
  try:
    try:
      import json as simplejson
    except ImportError:
      import simplejson
  except ImportError:
    from django.utils import simplejson
  return simplejson


def setup_gae_path(DIR_PATH, include_google_sql_libs=False):
  
  ### from dev_appserver.py
  
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
  
  extra_paths = EXTRA_PATHS[:]
  if include_google_sql_libs:
    extra_paths.extend(GOOGLE_SQL_EXTRA_PATHS)
  sys.path = extra_paths + sys.path

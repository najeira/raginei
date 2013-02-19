# -*- coding: utf-8 -*-
"""
raginei.cache
=============

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import logging
import hashlib
import base64

try:
  from google.appengine.api import memcache
  from google.appengine.ext.ndb import Future, Return
except ImportError:
  Future = None
  try:
    import pylibmc as memcache
  except ImportError:
    try:
      import memcache
    except ImportError:
      memcache = None


from . import util


def cache_key(func, *args, **kwds):
  key = 'raginei.cache.cache_key:%s-%s-%s' % (
    util.funcname(func), util.to_str(args), util.to_str(kwds))
  if isinstance(key, unicode):
    key = key.encode('utf-8')
  return base64.b32encode(hashlib.sha1(key).digest())


def memoize(expiry=300):
  """A decorator to memoize functions in the memcache."""
  debug = util.is_debug()
  def _decorator(func):
    @util.wraps(func)
    def _wrapper(*args, **kwds):
      force = kwds.pop('_force', False)
      key = cache_key(func, *args, **kwds)
      data = None
      if not debug and not force and expiry and memcache:
        data = memcache.get(key)
      if data is None:
        data = func(*args, **kwds)
        if Future and isinstance(data, Future):
          data = data.get_result()
        if expiry and memcache:
          memcache.set(key, data, expiry)
      else:
        logging.debug('memcache: use cache of %s' % key)
      return data
    return _wrapper
  return _decorator


def memoize_tasklet(expiry=300):
  """A decorator to memoize functions in the memcache."""
  from .app import tasklet
  debug = util.is_debug()
  def _decorator(func):
    @util.wraps(func)
    @tasklet
    def _wrapper(*args, **kwds):
      force = kwds.pop('_force', False)
      key = cache_key(func, *args, **kwds)
      data = None
      if not debug and not force and expiry and memcache:
        data = memcache.get(key)
      if data is None:
        data = yield func(*args, **kwds)
        if expiry and memcache:
          memcache.set(key, data, expiry)
      else:
        logging.debug('memoize_tasklet hit: %s' % key)
      raise Return(data)
    return _wrapper
  return _decorator


def memoize_delete(func, *args, **kwds):
  if memcache:
    key = cache_key(func, *args, **kwds)
    memcache.delete(key)

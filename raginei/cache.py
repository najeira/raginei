# -*- coding: utf-8 -*-
"""
raginei.cache
=============

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import logging
import functools
import hashlib
from google.appengine.api import memcache
from . import util


def cache_key(func, *args, **kwds):
  key = 'raginei.cache.cache_key:%s-%s' % (
    util.funcname(func), util.to_str(*args, **kwds))
  if isinstance(key, unicode):
    key = key.encode('utf-8')
  return hashlib.sha1(key).hexdigest()


def memoize(expiry=300):
  """A decorator to memoize functions in the memcache."""
  def _decorator(func):
    @functools.wraps(func)
    def _wrapper(*args, **kwds):
      force = kwds.pop('_force', False)
      #If the key is longer then max key size, it will be hashed with sha1
      #and will be replaced with the hex representation of the said hash.
      key = cache_key(func, *args, **kwds)
      data = None if force and expiry else memcache.get(key)
      if data is None:
        data = func(*args, **kwds)
        if expiry:
          memcache.set(key, data, expiry)
      else:
        logging.debug('memcache: use cache of %s' % key)
      return data
    return _wrapper
  return _decorator


def memoize_delete(func, *args, **kwds):
  key = cache_key(func, *args, **kwds)
  memcache.delete(key)

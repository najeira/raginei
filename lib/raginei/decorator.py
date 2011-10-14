# -*- coding: utf-8 -*-

import logging
import functools
import time
from google.appengine.ext import db
from google.appengine.runtime import apiproxy_errors
from . import util


def is_datastore_timeout(ex):
  return isinstance(ex, (db.Timeout, apiproxy_errors.DeadlineExceededError)) \
    or (isinstance(ex, apiproxy_errors.ApplicationError) and 5 == ex.application_error)


def retry_on_timeout(retries=5, interval=0.1):
  """A decorator to retry a given function performing db operations."""
  return retry_on_error(retries, interval, is_datastore_timeout)


def retry_on_error(retries=5, interval=0.1, error=Exception):
  """A decorator to retry a given function performing db operations."""
  
  def is_target(e):
    if issubclass(error, Exception):
      return isinstance(e, error)
    return error(e)
  
  def _decorator(func):
    @functools.wraps(func)
    def _wrapper(*args, **kwds):
      tries = 0
      while True:
        try:
          tries += 1
          return func(*args, **kwds)
        except Exception, e:
          if not is_target(e):
            raise
          elif tries > retries:
            raise
        wait_secs = interval * tries ** 2
        logging.warning('Retrying function %r in %f secs'
          % (func, wait_secs))
        time.sleep(wait_secs)
    return _wrapper
  return _decorator


def memcache(expiry=300):
  """A decorator to memoize functions in the memcache."""
  from google.appengine.api import memcache
  def _decorator(func):
    @functools.wraps(func)
    def _wrapper(*args, **kwds):
      force = kwds.pop('_force', False)
      #If the key is longer then max key size, it will be hashed with sha1
      #and will be replaced with the hex representation of the said hash.
      key = 'memcache:%s:%s' % (util.funcname(func), util.to_str(*args, **kwds))
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

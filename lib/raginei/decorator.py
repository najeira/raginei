# -*- coding: utf-8 -*-

import logging
import functools
import time
from google.appengine.ext import db
from google.appengine.runtime import apiproxy_errors


def is_datastore_timeout(ex):
  return isinstance(ex, (db.Timeout, apiproxy_errors.DeadlineExceededError)) \
    or (isinstance(ex, apiproxy_errors.ApplicationError) and 5 == ex.application_error)


def retry_on_timeout(retries=5, interval=0.1):
  """A decorator to retry a given function performing db operations."""
  return retry_on_error(retries, interval, is_datastore_timeout)


def retry_on_error(retries=5, interval=0.1, error=Exception):
  """A decorator to retry a given function performing db operations."""
  
  def is_target(e):
    if type(error).__name__ != 'function':
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

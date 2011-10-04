# -*- coding: utf-8 -*-

from google.appengine.ext import db


def to_str(v):
  if isinstance(v, basestring):
    return v
  elif isinstance(v, db.Model):
    return str(v.key())
  elif isinstance(v, db.Key):
    return str(v)
  elif isinstance(v, (list, tuple)):
    return '&'.join([to_str(x) for x in v])
  elif isinstance(v, dict):
    return '&'.join(['%s=%s' % (to_str(k), to_str(v[k])) for k in sorted(v.keys())])
  return str(v)


def funcname(f):
  try:
    if isinstance(f.im_self, type):
      return '%s.%s.%s' % (
        f.__module__, f.im_self.__name__, f.__name__)
    return '%s.%s.%s' % (
      f.__module__, f.im_self.__class__.__name__, f.__name__)
  except Exception:
    return '%s.%s' % (f.__module__, getattr(f, '__name__', str(f)))

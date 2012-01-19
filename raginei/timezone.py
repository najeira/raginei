# -*- coding: utf-8 -*-

import datetime


class JstTzinfo(datetime.tzinfo):
  def utcoffset(self, dt):
    return datetime.timedelta(hours=9)
  def dst(self, dt):
    return datetime.timedelta(0)
  def tzname(self, dt):
    return 'JST'


class UtcTzinfo(datetime.tzinfo):
  def utcoffset(self, dt):
    return datetime.timedelta(0)
  def dst(self, dt):
    return datetime.timedelta(0)
  def tzname(self, dt):
    return 'UTC'


JST_TZ = JstTzinfo()
UTC_TZ = UtcTzinfo()
JST_OFFSET = JST_TZ.utcoffset(None)
UTC_OFFSET = UTC_TZ.utcoffset(None)


def utc(val):
  return astimezone(val, UTC_TZ)


def jst(val):
  return astimezone(val, JST_TZ)


def astimezone(val, tzinfo):
  if not tzinfo:
    return val
  if val.tzinfo is None:
    val = val.replace(tzinfo=UTC_TZ)
  return val.astimezone(tzinfo)

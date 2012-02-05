# -*- coding: utf-8 -*-

import datetime


class TzInfo(datetime.tzinfo):
  def __init__(self, name, offset):
    super(TzInfo, self).__init__()
    self._offset = datetime.timedelta(hours=offset)
    self._name = name
  def utcoffset(self, dt):
    return self._offset
  def dst(self, dt):
    return datetime.timedelta(0)
  def tzname(self, dt):
    return self._name


UTC_TZ = TzInfo('UTC', 0)
JST_TZ = TzInfo('JST', 9)


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

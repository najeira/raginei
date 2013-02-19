# -*- coding: utf-8 -*-
"""
raginei.taskutil
================

:copyright: 2012 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import logging
import time
import uuid
from google.appengine.api import taskqueue
from google.appengine.api import memcache
from google.appengine.ext.ndb import in_transaction, Future
from .app import request
from .util import wraps

__all__ = [
  'Error', 'TaskCollisionError', 'add', 'task_func', 'task_retry_limit',
  'task_fail_on_error',
]

class Error(Exception):
  pass


class TaskCollisionError(Error):
  pass


def add(url, name=None, queue_name='default', transactional=False,
  ignore_already=False, fail_fast=False, headers=None, **kwds):
  """Adds a task to a TaskQueue."""
  
  is_in_tx = transactional and in_transaction()
  transactional = transactional or is_in_tx
  
  if not name and not is_in_tx:
    name = uuid.uuid4().hex
  
  headers = headers or {}
  if fail_fast:
    headers['X-AppEngine-FailFast'] = 'true'
  
  if not url.startswith('/'):
    url = '/' + url
  
  task = taskqueue.Task(url=url, name=name, headers=headers, **kwds)
  
  try:
    task.add(queue_name, transactional=transactional)
  except (taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
    if not ignore_already:
      raise
  return task


def _call_func(func, *args, **kwds):
  ret = func(*args, **kwds)
  if ret and isinstance(ret, Future):
    ret = ret.get_result()
  return ret


def task_func(func):
  """TaskQueueの前処理と後処理を自動で行う"""
  @wraps(func)
  def _wrapper(*args, **kwds):
    key = 'raginei.taskutil.task_func.' + str(request.task_name or time.time())
    
    if not memcache.add(key, 1, 30):
      #addに失敗した場合は他のプロセスがタスクの処理を開始している
      #memcacheの値が1以外の場合は他プロセスが処理成功しているので終了
      if 1 != memcache.get(key):
        return 'ok'
      
      #ここの来るのは、同じタスクの多重起動か、
      #前のタスク実行がエラー終了かつmemcache.deleteに失敗した場合。
      #これらは区別できないので、エラーを投げてリトライさせる。
      #タスクの多重起動の場合は、他プロセスが処理完了すれば、
      #いずれフラグが1以外になって終了する。
      #前のタスクがエラーの場合は、いずれロックがタイムアウトして再処理となる。
      logging.warn('task_func: %s' % key)
      raise TaskCollisionError()
    
    try:
      ret = _call_func(func, *args, **kwds)
    except:
      #タスクが失敗した場合はmemcacheのロックを削除してリトライ可能にする
      memcache.delete(key)
      raise
    else:
      #タスクが成功した場合はロックの状態を処理成功に変更する。
      #ロックを削除すると他のプロセスが同じ処理を実施可能になるので削除しない。
      #フラグを処理成功にしておくと、多重起動した他プロセスは何もせずに終了する。
      memcache.set(key, 2, 86400) #処理成功フラグ
    return ret or 'ok'
  return _wrapper


def task_retry_limit(limit):
  """無限リトライしないよう、プログラム側でのfail-safe"""
  def _decorator(func):
    @wraps(func)
    def _wrapper(*args, **kwds):
      if limit < request.task_retry_count:
        logging.warn('task_retry_limit: %s (%s)' % (
          request.task_name, request.task_retry_count))
        return 'task_retry_limit'
      return _call_func(func, *args, **kwds)
    return _wrapper
  return _decorator


def task_fail_on_error(*errors):
  """プログラム側のバグ等によるエラーをリトライする必要は無いので、
  一部の例外が発生した場合はキャッチして正常終了させるためのデコレータを返します"""
  def _decorator(func):
    @wraps(func)
    def _wrapper(*args, **kwds):
      try:
        return _call_func(func, *args, **kwds)
      except Exception, e:
        logging.exception(e)
        if type(e) in errors:
          return 'task_fail_on_error'
        raise
    return _wrapper
  return _decorator

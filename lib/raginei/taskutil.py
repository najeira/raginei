# -*- coding: utf-8 -*-

import logging
from google.appengine.api import taskqueue
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext import db


def Task(url, name=None, **kwds):
  if not name:
    import uuid
    name = uuid.uuid4().hex
  return taskqueue.Task(url=url, name=name, **kwds)


def add(url, name=None, queue_name='default', transactional=False, retries=3, ignore_already=False, **kwds):
  import time
  is_in_tx = transactional and db.is_in_transaction()
  task = Task(url=url, name=name, **kwds)
  tries = 0
  while True:
    try:
      tries += 1
      task.add(queue_name, transactional=transactional)
      return task
    except (taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
      if ignore_already:
        return task
      elif 1 >= tries or is_in_tx:
        raise
      return task
    except (taskqueue.TransientError, apiproxy_errors.DeadlineExceededError), e2:
      if retries < tries or is_in_tx:
        raise
    wait_secs = 0.1 * tries ** 2
    logging.warning('Retrying function taskutil.add in %f secs: %r' % (wait_secs, e2))
    time.sleep(wait_secs)

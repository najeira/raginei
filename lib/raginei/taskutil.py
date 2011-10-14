# -*- coding: utf-8 -*-

import time
import uuid
import logging
from google.appengine.api import taskqueue
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext import db


def add(url, name=None, queue_name='default', transactional=False, retries=3,
  ignore_already=False, **kwds):
  is_in_tx = transactional and db.is_in_transaction()
  if not name and not is_in_tx:
    name = uuid.uuid4().hex
  task = taskqueue.Task(url=url, name=name, **kwds)
  for tries in xrange(retries):
    try:
      task.add(queue_name, transactional=transactional)
      return task
    except (taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
      if not ignore_already and (0 >= tries or is_in_tx):
        raise
      return task
    except (taskqueue.TransientError, apiproxy_errors.DeadlineExceededError), e2:
      if is_in_tx:
        raise
    wait_secs = 0.1 * (tries + 1) ** 2
    logging.warning('Retrying function taskutil.add in %f secs: %r' % (wait_secs, e2))
    time.sleep(wait_secs)
  raise

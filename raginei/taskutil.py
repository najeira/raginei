# -*- coding: utf-8 -*-
"""
raginei.taskutil
================

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import uuid
from google.appengine.api import taskqueue
from google.appengine.ext.ndb import in_transaction


def add(url, name=None, queue_name='default', transactional=False,
  ignore_already=False, fail_fast=False, headers=None, **kwds):
  
  is_in_tx = transactional and in_transaction()
  
  if not name and not is_in_tx:
    name = uuid.uuid4().hex
  
  headers = headers or {}
  if fail_fast:
    headers['X-AppEngine-FailFast'] = 'true'
  
  task = taskqueue.Task(url=url, name=name, headers=headers, **kwds)
  
  try:
    task.add(queue_name, transactional=transactional)
  except (taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
    if not ignore_already:
      raise
  return task

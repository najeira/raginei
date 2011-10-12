# -*- coding: utf-8 -*-

import os
import sys
import threading


_sys_path = None
_lock = threading.RLock()

def setup_path(gae_home=None):
  global _sys_path
  _lock.acquire()
  try:
    if _sys_path is None:
      if gae_home:
        setup_gae_path(gae_home)
      project_home = os.path.abspath(__file__)
      for _ in range(3):
        project_home = os.path.dirname(project_home)
      for v in (project_home, os.path.join(project_home, 'lib')):
        if v not in sys.path:
          sys.path.insert(0, v)
      _sys_path = list(sys.path)
    else:
      sys.path[:] = _sys_path
  finally:
    _lock.release()


def setup_gae_path(gae_home):
  ### from kay
  sys.path.insert(0, gae_home)
  lib = os.path.join(gae_home, 'lib')
  # Automatically add all packages in the SDK's lib folder:
  for dir in os.listdir(lib):
    path = os.path.join(lib, dir)
    # SDK 1.4.2 introduced Django 1.2, and renamed django to django_0_96
    if dir == 'django_0_96':
      sys.path.insert(0, path)
      continue
    # Package can be under 'lib/<pkg>/<pkg>/' or 'lib/<pkg>/lib/<pkg>/'
    detect = (os.path.join(path, dir), os.path.join(path, 'lib', dir))
    for path in detect:
      if os.path.isdir(path):
        sys.path.insert(0, os.path.dirname(path))
        break

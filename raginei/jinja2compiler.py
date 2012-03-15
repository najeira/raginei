# -*- coding: utf-8 -*-
"""
raginei.jinja2compiler
======================

from gaefy.jinja2.compiler
:copyright: 2009 by tipfy.org.
:license: BSD, see LICENSE.txt for more details.

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import os
import sys
import re
from os import path, listdir, makedirs
import threading
import Queue
import logging
import imp, marshal

py_header = imp.get_magic() + u'\xff\xff\xff\xff'.encode('iso-8859-15')


def compile_file(env, src_path, dst_path, encoding='utf-8', base_dir='', bytecode=False):
  """Compiles a Jinja2 template to python code.
  Params:
    `env`: a Jinja2 Environment instance.
    `src_path`: path to the source file.
    `dst_path`: path to the destination file.
    `encoding`: template encoding.
    `base_dir`: the base path to be removed from the compiled template
      filename.
  """
  # Read the template file.
  src_file = file(src_path, 'rb')
  try:
    source = src_file.read().decode(encoding)
  except Exception:
    sys.stderr.write("Failed compiling %s. Perhaps you can check the character"
                     " set of this file.\n" % src_path)
    raise
  finally:
    src_file.close()
  
  if src_path.endswith( ('.html', '.htm', '.xhtml', '.xhtm') ):
    from raginei.jinja2loader import TemplateStrip
    source = TemplateStrip.strip(source)
  
  # Compile the template to raw Python code..
  name = src_path.replace(base_dir, '')
  if bytecode:
    code = env.compile(source, name=name, filename=name, raw=False)
    raw = py_header + marshal.dumps(code)
  else:
    raw = env.compile(source, name=name, filename=name, raw=True)
  
  # Save to the destination.
  dst_file = open(dst_path, 'wb')
  dst_file.write(raw)
  dst_file.close()
  print dst_path


def compile_dir(env, src_path, dst_path, pattern=r'^[^\.].*\..*[^~]$',
                encoding='utf-8', base_dir=None, bytecode=False,
                negative_pattern=r'^.*(\.swp|\.png|\.jpg|\.gif|\.pdf)$'):
  """Compiles a directory of Jinja2 templates to python code.
  Params:
    `env`: a Jinja2 Environment instance.
    `src_path`: path to the source directory.
    `dst_path`: path to the destination directory.
    `encoding`: template encoding.
    `pattern`: a regular expression to match template file names.
    `base_dir`: the base path to be removed from the compiled template
      filename.
  """
  if base_dir is None:
    # In the first call, store the base dir.
    base_dir = src_path
  
  for filename in listdir(src_path):
    if filename.startswith("."):
      continue
    src_name = path.join(src_path, filename)
    dst_name = path.join(dst_path, filename)
    
    if path.isdir(src_name):
      if not path.isdir(dst_name):
        makedirs(dst_name)
      for dir_params in compile_dir(env, src_name, dst_name, encoding=encoding,
        base_dir=base_dir, bytecode=bytecode):
        yield dir_params
    elif path.isfile(src_name) and re.match(pattern, filename) and \
      not re.match(negative_pattern, filename):
      yield (compile_file, (env, src_name, dst_name),
        dict(encoding=encoding, base_dir=base_dir, bytecode=bytecode))


class ThreadPool(object):
  def __init__(self, count):
    self._queue = Queue.Queue(0) # infinite sized queue
    self._threads = [threading.Thread(target=self._run) for _ in xrange(count)]
    for thread in self._threads:
      thread.start()
  
  def _run(self):
    while 1:
      func = self._queue.get()
      if func is None:
        break
      try:
        func[0](*func[1], **func[2])
      except Exception as ex:
        logging.exception(ex)
  
  def submit(self, func, *args, **kwds):
    self._queue.put((func, args, kwds))
  
  def shutdown(self):
    for _ in self._threads:
      self._queue.put(None) # terminator
    for thread in self._threads:
      thread.join()


def compile_templates(jinja2_env, templates_dir, dest_dir, threads=1, bytecode=False):
  thread_pool = ThreadPool(threads)
  try:
    for func, args, kwds in compile_dir(
      jinja2_env, templates_dir, dest_dir, bytecode=bytecode):
      thread_pool.submit(func, *args, **kwds)
  finally:
    thread_pool.shutdown()


def main():
  from optparse import OptionParser
  parser = OptionParser()
  
  parser.add_option('--app', type='string')
  parser.add_option('--gae', type='string')
  parser.add_option('--src', type='string', default='templates')
  parser.add_option('--dest', type='string')
  parser.add_option('--root', type='string', default='.')
  parser.add_option('--threads', type='int', default=1)
  parser.add_option('--bytecode', action='store_true', default=False)
  
  options, args = parser.parse_args()
  options = dict([(k, v) for k, v in options.__dict__.iteritems()
    if not k.startswith('_') and v is not None])
  
  errors = []
  
  if not options.get('gae'):
    errors.append('--gae required.')
  
  if not options.get('app'):
    errors.append('--app required.')
  
  if errors:
    print ', '.join(errors)
    return
  
  root_dir = os.path.abspath(options['root'])
  sys.path.insert(0, root_dir)
  
  lib_dir = os.path.join(root_dir, 'lib')
  if path.isdir(lib_dir):
    sys.path.insert(0, lib_dir)
  
  src_dir = os.path.join(root_dir, options['src'])
  dest_dir = os.path.join(root_dir,
    options.get('dest') or '%s_compiled' % options['src'])
  
  from raginei.util import setup_gae_path
  
  setup_gae_path(options['gae'])
  
  os.environ["APPLICATION_ID"] = 'raginei-jinja2compiler'
  
  from werkzeug.utils import import_string
  
  application = import_string(options['app'])
  application.init_on_first_request()
  
  if not path.isdir(dest_dir):
    makedirs(dest_dir)
  
  compile_templates(application.jinja2_env, src_dir, dest_dir,
    options['threads'], options['bytecode'])


if __name__ == '__main__':
  main()

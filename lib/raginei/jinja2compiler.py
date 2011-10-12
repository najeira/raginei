# -*- coding: utf-8 -*-

"""
from gaefy.jinja2.compiler
:copyright: 2009 by tipfy.org.
:license: BSD, see LICENSE.txt for more details.
"""

import os
import sys
import re
from os import path, listdir, makedirs
import threading
import Queue


def compile_file(env, src_path, dst_path, encoding='utf-8', base_dir=''):
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
  src_file = file(src_path, 'r')
  try:
    source = src_file.read().decode(encoding)
  except Exception:
    sys.stderr.write("Failed compiling %s. Perhaps you can check the character"
                     " set of this file.\n" % src_path)
    raise
  finally:
    src_file.close()
  
  if src_path.endswith(('.html', '.htm')):
    source = TemplateStrip.strip(source)
  
  # Compile the template to raw Python code..
  name = src_path.replace(base_dir, '')
  raw = env.compile(source, name=name, filename=name, raw=True)
  
  # Save to the destination.
  dst_file = open(dst_path, 'w')
  dst_file.write(raw)
  dst_file.close()
  print dst_path


def compile_dir(env, src_path, dst_path, pattern=r'^[^\.].*\..*[^~]$',
                encoding='utf-8', base_dir=None,
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
      compile_dir(env, src_name, dst_name, encoding=encoding, base_dir=base_dir)
    elif path.isfile(src_name) and re.match(pattern, filename) and \
      not re.match(negative_pattern, filename):
      #compile_file(env, src_name, dst_name, encoding=encoding,
      #             base_dir=base_dir)
      yield (compile_file, (env, src_name, dst_name),
        dict(encoding=encoding, base_dir=base_dir))


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
      func[0](*func[1], **func[2])
  
  def submit(self, func, *args, **kwds):
    self._queue.put((func, args, kwds))
  
  def shutdown(self):
    for thread in self._threads:
      self._queue.put(None) # terminator
    for thread in self._threads:
      thread.join()


class TemplateStrip(object):

  SCRIPT_RE = re.compile('(</script.*?>|^)(.*?)(<script.*?>|$)', re.IGNORECASE | re.DOTALL)
  TEXTAREA_RE = re.compile('(</textarea.*?>|^)(.*?)(<textarea.*?>|$)', re.IGNORECASE | re.DOTALL)
  TAG_RE = re.compile('(>|^)(.*?)(<|$)', re.DOTALL)
  SPACE_RE = re.compile(r'[\t\s]*[\r\n]+[\t\s]*', re.MULTILINE)
  
  @classmethod
  def strip(cls, source):
    return cls.SCRIPT_RE.sub(cls.repl1, source)
  
  @classmethod
  def repl1(cls, matchobj):
    start = matchobj.group(1)
    target = matchobj.group(2)
    end = matchobj.group(3)
    target = cls.TEXTAREA_RE.sub(cls.repl2, target)
    return start + target + end
  
  @classmethod
  def repl2(cls, matchobj):
    start = matchobj.group(1)
    target = matchobj.group(2)
    end = matchobj.group(3)
    target = cls.TAG_RE.sub(cls.repl3, target)
    return start + target + end
  
  @classmethod
  def repl3(cls, matchobj):
    start = matchobj.group(1)
    target = matchobj.group(2)
    end = matchobj.group(3)
    target = cls.SPACE_RE.sub('', target)
    return start + target + end


def compile(app, templates_dir, dest_dir, threads=1):
  thread_pool = ThreadPool(threads)
  try:
    for func, args, kwds in compile_dir(
      app.jinja2_env, templates_dir, dest_dir):
      thread_pool.submit(func, *args, **kwds)
  finally:
    thread_pool.shutdown()


def main():
  from optparse import OptionParser
  parser = OptionParser()
  
  parser.add_option('--gae', type='string')
  parser.add_option('--templates', type='string', default='templates')
  parser.add_option('--root', type='string', default='.')
  parser.add_option('--threads', type='int', default=1)
  parser.add_option('--config', type='string')
  
  options, args = parser.parse_args()
  options = dict([(k, v) for k, v in options.__dict__.iteritems()
    if not k.startswith('_') and v is not None])
  
  if not options or not options.get('gae'):
    print 'gae required.'
    return
  
  root_dir = os.path.abspath(options['root'])
  templates_dir = os.path.join(root_dir, options['templates'])
  dest_dir = os.path.join(root_dir, '%s_compiled' % options['templates'])
  if not path.isdir(dest_dir):
    makedirs(dest_dir)
  
  try:
    from raginei.path import setup_path
  except ImportError:
    sys.path.insert(0, os.path.join(root_dir, 'lib'))
    from raginei.path import setup_path
  
  setup_path(gae_home=options['gae'])
  
  os.environ["APPLICATION_ID"] = 'raginei'
  
  config = options.get('config') or None
  if config:
    from werkzeug.utils import import_string
    config = import_string(config)
  
  from raginei.app import Application
  application = Application(config)
  
  compile(application, templates_dir, dest_dir, options['threads'])


if __name__ == '__main__':
  main()

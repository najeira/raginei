# -*- coding: utf-8 -*-
"""
raginei.jinja2loader
====================

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import re
from jinja2 import FileSystemLoader as FileSystemLoaderBase, BaseLoader, TemplateNotFound
from jinja2.utils import internalcode

_strip_extentions = ('.html', '.htm', '.xml', '.xhtml')


class LoaderMixin(object):
  
  def __init__(self, *args, **kwds):
    super(LoaderMixin, self).__init__(*args, **kwds)
    self._code_cache = {}
  
  @internalcode
  def load(self, environment, name, globals=None):
    if name in self._code_cache:
      code, uptodate = self._code_cache[name]
    else:
      source, filename, uptodate = self.get_source(environment, name)
      if filename.endswith(_strip_extentions):
        source = TemplateStrip.strip(source)
      code = self.compile(environment, source, name, filename)
      self._code_cache[name] = (code, uptodate)
    return environment.template_class.from_code(
      environment, code, globals or {}, uptodate)
  
  def compile(self, environment, source, name, filename):
    return environment.compile(source, name, filename)


class FileSystemLoader(LoaderMixin, FileSystemLoaderBase):
  pass


class FileSystemCodeLoader(FileSystemLoader):
  
  def compile(self, environment, source, name, filename):
    return compile(source, filename, 'exec')


class DatastoreLoader(LoaderMixin, BaseLoader):
  
  def __init__(self, model_class, encoding='utf-8'):
    super(DatastoreLoader, self).__init__(self)
    self.model_class = model_class
    self.encoding = encoding
    self._code_cache = {}
  
  def get_source(self, environment, template):
    obj = self.model_class.get_by_key_name(template)
    if not obj:
      raise TemplateNotFound(template)
    return obj.source, template, obj.uptodate


class DatastoreCodeLoader(DatastoreLoader):
  
  def compile(self, environment, source, name, filename):
    return compile(source, filename, 'exec')


class TemplateStrip(object):
  
  E_BRACKET_OPEN = re.escape('{')
  E_BRACKET_CLOSE = re.escape('}')
  E_LT = re.escape('<')
  E_GT = re.escape('>')
  E_PERCENT = re.escape('%')
  E_HASH = re.escape('#')
  
  SPACE_RE = re.compile(r'(%s|(?:%s|%s|%s)%s)[\s\r\n]+((?:%s|%s(?:%s|%s|%s)))' % (
    E_GT, E_PERCENT, E_HASH, E_BRACKET_CLOSE, E_BRACKET_CLOSE,
    E_LT, E_BRACKET_OPEN, E_BRACKET_OPEN, E_PERCENT, E_HASH,
  ), re.MULTILINE)
  
  @classmethod
  def strip(cls, source):
    return cls.SPACE_RE.sub('\\1\\2', source)

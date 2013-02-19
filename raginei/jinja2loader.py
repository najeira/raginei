# -*- coding: utf-8 -*-
"""
raginei.jinja2loader
====================

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import re
from jinja2 import FileSystemLoader as JinjaFileSystemLoader
from jinja2.utils import internalcode


class TemplateStripMixin(object):
  
  strip_extentions = ('.html', '.htm', '.xml', '.xhtml')

  def get_source(self, environment, template):
    #noinspection PyUnresolvedReferences
    source, filename, uptodate = super(
      TemplateStripMixin, self).get_source(environment, template)
    if filename.endswith(self.strip_extentions):
      source = TemplateStrip.strip(source)
    return source, filename, uptodate


class LoaderMixin(TemplateStripMixin):
  
  def __init__(self, *args, **kwds):
    self._code_cache = {}
  
  @internalcode
  def load(self, environment, name, globals=None):
    if name in self._code_cache:
      code, uptodate = self._code_cache[name]
    else:
      source, filename, uptodate = self.get_source(environment, name)
      code = self.compile(environment, source, name, filename)
      self._code_cache[name] = (code, uptodate)
    return environment.template_class.from_code(
      environment, code, globals or {}, uptodate)
  
  def compile(self, environment, source, name, filename):
    return environment.compile(source, name, filename)


class CodeLoaderMixin(LoaderMixin):
  
  def compile(self, environment, source, name, filename):
    return compile(source, filename, 'exec')


class ByteCodeLoaderMixin(LoaderMixin):
  
  def compile(self, environment, source, name, filename):
    return source


class FileSystemLoaderBase(TemplateStripMixin, JinjaFileSystemLoader):
  pass


class FileSystemLoader(LoaderMixin, JinjaFileSystemLoader):
  pass


class FileSystemCodeLoader(CodeLoaderMixin, JinjaFileSystemLoader):
  pass


class FileSystemByteCodeLoader(ByteCodeLoaderMixin, FileSystemLoader):
  pass


class TemplateStrip(object):
  
  E_BRACKET_OPEN = re.escape('{')
  E_BRACKET_CLOSE = re.escape('}')
  E_LT = re.escape('<')
  E_GT = re.escape('>')
  E_PERCENT = re.escape('%')
  E_HASH = re.escape('#')
  
  SPACE_RE = re.compile(r'(%s|(?:%s|%s|%s)%s)[\s\t]*[\r\n]+[\s\t\r\n]*' % (
    E_GT, E_PERCENT, E_HASH, E_BRACKET_CLOSE, E_BRACKET_CLOSE,
  ), re.MULTILINE)
  
  SPACE_RE2 = re.compile(r'([^%s])[\s\t]*[\r\n]+[\s\t\r\n]*(%s|%s(?:%s|%s|%s))' % (
    E_BRACKET_OPEN, E_LT, E_BRACKET_OPEN, E_BRACKET_OPEN, E_PERCENT, E_HASH,
  ), re.MULTILINE)
  
  @classmethod
  def strip(cls, source):
    return cls.SPACE_RE2.sub('\\1\\2', cls.SPACE_RE.sub('\\1', source))

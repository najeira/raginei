# -*- coding: utf-8 -*-

import re
from jinja2 import FileSystemLoader as FileSystemLoaderBase, BaseLoader, TemplateNotFound
from jinja2.utils import internalcode

_strip_extentions = ('.html', '.htm', '.xml', '.xhtml')


class LoaderMixin(object):
  
  @internalcode
  def load(self, environment, name, globals=None):
    if name in self._code_cache:
      code, uptodate = self._code_cache[name]
    else:
      source, filename, uptodate = self.get_source(environment, name)
      if filename.endswith(_strip_extentions):
        source = _strip_template(source)
      code = environment.compile(source, name, filename)
      self._code_cache[name] = (code, uptodate)
    return environment.template_class.from_code(
      environment, code, globals or {}, uptodate)


class FileSystemLoader(LoaderMixin, FileSystemLoaderBase):
  
  def __init__(self, searchpath, encoding='utf-8'):
    super(FileSystemLoader, self).__init__(searchpath, encoding)
    self._code_cache = {}


class DatastoreLoader(LoaderMixin, BaseLoader):
  
  def __init__(self, model_class, encoding='utf-8'):
    self.model_class = model_class
    self.encoding = encoding
    self._code_cache = {}
  
  def get_source(self, environment, template):
    obj = self.model_class.get_by_key_name(template)
    if not obj:
      raise TemplateNotFound(template)
    return obj.source, template, obj.uptodate


_content_repl_script_re = re.compile('(</script.*?>|^)(.*?)(<script.*?>|$)',
  re.IGNORECASE | re.DOTALL)
_content_repl_textarea_re = re.compile('(</textarea.*?>|^)(.*?)(<textarea.*?>|$)',
  re.IGNORECASE | re.DOTALL)
_content_repl_tag_re = re.compile('(>|^)(.*?)(<|$)', re.DOTALL)
_content_repl_space_re = re.compile(r'[\t\s]*[\r\n]+[\t\s]*', re.MULTILINE)


def _strip_template(source):
  return _content_repl_script_re.sub(_content_repl_func1, source)


def _content_repl_func1(matchobj):
  start = matchobj.group(1)
  target = matchobj.group(2)
  end = matchobj.group(3)
  target = _content_repl_textarea_re.sub(_content_repl_func2, target)
  return start + target + end


def _content_repl_func2(matchobj):
  start = matchobj.group(1)
  target = matchobj.group(2)
  end = matchobj.group(3)
  target = _content_repl_tag_re.sub(_content_repl_func3, target)
  return start + target + end


def _content_repl_func3(matchobj):
  start = matchobj.group(1)
  target = matchobj.group(2)
  end = matchobj.group(3)
  target = _content_repl_space_re.sub('', target)
  return start + target + end

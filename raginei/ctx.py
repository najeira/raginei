# -*- coding: utf-8 -*-
"""
raginei.ctx
===========

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

from __future__ import with_statement


class Context(object):
  
  context_stack = []
  
  def __init__(self):
    self.routes = {}
    self.template_funcs = {}
    self.template_filters = {}
    self.template_context_processors = []
    self.request_middlewares = []
    self.view_middlewares = []
    self.response_middlewares = []
    self.exception_middlewares = []
    self.routing_middlewares = []
  
  @classmethod
  def push(cls):
    obj = cls()
    cls.context_stack.append(obj)
    return obj
  
  @classmethod
  def pop(cls):
    assert 2 <= len(cls.context_stack)
    return cls.context_stack.pop()
  
  def __enter__(self):
    return self.push()
  
  def __exit__(self, exc_type, exc_value, tb):
    ret = self.pop()
    assert ret == self
  
  @classmethod
  def add_route(cls, key, value):
    return cls.set_to_dict('routes', key, value)
  
  @classmethod
  def add_template_func(cls, key, value):
    return cls.set_to_dict('template_funcs', key, value)
  
  @classmethod
  def add_template_filter(cls, key, value):
    return cls.set_to_dict('template_filters', key, value)
  
  @classmethod
  def set_to_dict(cls, name, key, value):
    getattr(cls.context_stack[-1], name)[key] = value

  @classmethod
  def add_template_context_processor(cls, value):
    return cls.append_to_list('template_context_processors', value)
  
  @classmethod
  def add_request_middleware(cls, value):
    return cls.append_to_list('request_middlewares', value)
  
  @classmethod
  def add_view_middleware(cls, value):
    return cls.append_to_list('view_middlewares', value)
  
  @classmethod
  def add_response_middleware(cls, value):
    return cls.append_to_list('response_middlewares', value)
  
  @classmethod
  def add_exception_middleware(cls, value):
    return cls.append_to_list('exception_middlewares', value)
  
  @classmethod
  def add_routing_middleware(cls, value):
    return cls.append_to_list('routing_middlewares', value)
  
  @classmethod
  def append_to_list(cls, name, value):
    getattr(cls.context_stack[-1], name).append(value)
  
  @classmethod
  def get_routes(cls):
    return cls.get_merged_dict('routes')
  
  @classmethod
  def get_template_funcs(cls):
    return cls.get_merged_dict('template_funcs')
  
  @classmethod
  def get_template_filters(cls):
    return cls.get_merged_dict('template_filters')
  
  @classmethod
  def get_template_context_processors(cls):
    return cls.get_merged_list('template_context_processors')
  
  @classmethod
  def get_request_middlewares(cls):
    return cls.get_merged_list('request_middlewares')
  
  @classmethod
  def get_view_middlewares(cls):
    return cls.get_merged_list('view_middlewares')
  
  @classmethod
  def get_response_middlewares(cls):
    return cls.get_merged_list('response_middlewares')
  
  @classmethod
  def get_exception_middlewares(cls):
    return cls.get_merged_list('exception_middlewares')
  
  @classmethod
  def get_routing_middlewares(cls):
    return cls.get_merged_list('routing_middlewares')
  
  @classmethod
  def get_merged_dict(cls, name):
    return cls.get_merged({}, name, lambda x, y: x.update(y))
  
  @classmethod
  def get_merged_list(cls, name):
    return cls.get_merged([], name, lambda x, y: x.extend(y))
  
  @classmethod
  def get_merged(cls, ret, name, merger):
    if 1 == len(cls.context_stack):
      return getattr(cls.context_stack[0], name)
    for c in cls.context_stack:
      v = getattr(c, name)
      if v:
        merger(ret, v)
    return ret

toplevel_context = Context.push()

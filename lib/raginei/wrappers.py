# -*- coding: utf-8 -*-

from werkzeug.wrappers import Request as RequestBase, Response as ResponseBase
from werkzeug.utils import cached_property, redirect
from werkzeug.contrib.wrappers import DynamicCharsetResponseMixin
from werkzeug.exceptions import HTTPException
from .util import json_module


class Request(RequestBase):
  url_rule = None
  view_args = None
  routing_exception = None
  
  @property
  def endpoint(self):
    if self.url_rule is not None:
      return self.url_rule.endpoint
  
  @cached_property
  def is_get(self):
    return 'get' == self.method.lower()
  
  @cached_property
  def is_post(self):
    return 'post' == self.method.lower()
  
  @cached_property
  def is_taskqueue(self):
    return self.headers.get('X-AppEngine-TaskName')
  
  @cached_property
  def json(self):
    if self.mimetype == 'application/json':
      return json_module().loads(self.data)
  
  @cached_property
  def user_agent_str(self):
    return self.environ.get('HTTP_USER_AGENT')
  
  @cached_property
  def is_smartphone(self):
    ua = (self.user_agent_str or '').lower()
    return 'iphone' in ua or 'android' in ua


class Response(DynamicCharsetResponseMixin, ResponseBase):
  default_mimetype = 'text/html'


class Found(HTTPException):
  code = 302
  
  def get_response(self, environ):
    return redirect(self.description, self.code)


class MovedPermanently(Found):
  code = 301

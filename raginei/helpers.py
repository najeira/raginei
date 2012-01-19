# -*- coding: utf-8 -*-
"""
raginei.helpers
===============

:copyright: 2011 by najeira <najeira@gmail.com>.
:license: Apache License 2.0, see LICENSE for more details.
"""

import datetime
import re

import jinja2
from werkzeug.urls import url_quote_plus

from raginei.app import request, url, current_app


def to_unicode(s, encoding='utf-8', errors='replace'):
  if s is None:
    return u''
  elif not isinstance(s, basestring):
    return unicode(s)
  elif not isinstance(s, unicode):
    return unicode(s, encoding, errors)
  return s


def to_str(s, encoding='utf-8', errors='replace'):
  if s is None:
    return ''
  elif not isinstance(s, basestring):
    return unicode(s)
  elif isinstance(s, unicode):
    return s.encode(encoding, errors)
  return s


class _FormList(list):
  pass


def _to_form(value):
  if isinstance(value, (int, long, float)):
    return unicode(value)
  elif isinstance(value, datetime.date):
    return format_date(value, 'date')
  elif not value:
    return ''
  return to_unicode(value)


def _to_form_list(value):
  if isinstance(value, _FormList):
    return value
  elif not isinstance(value, (list, tuple)):
    ret = [_to_form(value)]
  else:
    ret = filter(None, map(_to_form, value))
  return _FormList(ret)


def _form_get(name, value):
  form_value = request.form.get(name)
  if form_value is not None:
    return form_value
  return _to_form(value)


def _form_get_list(name, value):
  form_value = request.form.getlist(name)
  if form_value:
    return _FormList(form_value)
  return _to_form_list(value)


def to_markup(env, value):
  if env.autoescape:
    value = jinja2.Markup(value)
  return value


FORMAT_DATE_MAP = {
  'full': '%Y/%m/%d (%a) %H:%M:%S',
  'long': '%Y/%m/%d (%a) %H:%M',
  'short': '%Y/%m/%d %H:%M',
  'date_long': '%Y/%m/%d (%a)',
  'date': '%Y/%m/%d',
  'monthday_long': '%m/%d (%a)',
  'monthday_short': '%m/%d',
  'monthday': '%m/%d',
  'time_long': '%H:%M',
  'time': '%H:%M',
  'daytime_long': '%m/%d (%a) %H:%M',
  'daytime': '%m/%d %H:%M',
  'rfc822': '%a, %d %b %Y %H:%M:%S',
  'html5': '%Y-%m-%d %H:%M:%S',
  }

def format_date(dt, format=None):
  ### from aha coreblog3
  #TODO: i18n
  
  if dt is None:
    return u''
  
  if not isinstance(dt, datetime.datetime):
    dt = datetime.datetime(dt.year, dt.month, dt.day)
    if not format:
      format = 'date_short'
  
  if not format:
    format = 'short'
  elif 'auto' == format:
    today = datetime.date.today()
    if dt.date() == today:
      format = 'time'
    elif dt.year == today.year:
      format = 'monthday'
    else:
      format = 'date'
  
  if format in FORMAT_DATE_MAP:
    format = FORMAT_DATE_MAP[format]
  
  return to_unicode(dt.strftime(to_str(format)))


@jinja2.environmentfilter
def nl2br(env, s, arg=u'<br />'):
  if not s:
    return s
  result = arg.join(to_unicode(s).split(u'\n'))
  return to_markup(env, result)


@jinja2.environmentfunction
def obfuscate(env, value, js=False):
  value = to_unicode(value)
  ret = []
  for c in value:
    c = c.encode('utf-8')
    if 2 <= len(c):
      ret.append(c)
    elif js:
      ret.append('%%%s' % c.encode('hex'))
    else:
      ret.append('&#%d;' % ord(c))
  result = ''.join(ret)
  return to_markup(env, result)


@jinja2.environmentfunction
def mail_tag(env, mail, encode=None, **kwds):
  ### from symfony
  
  options = {
    'cc':      None,
    'bcc':     None,
    'subject': None,
    'body':    None,
    }
  options.update(kwds)
  
  name = mail
  extras = []
  htmloptions = []
  for key, value in options.iteritems():
    if not value:
      continue
    elif 'cc' == key or 'bcc' == key:
      value = value.strip()
      if value:
        value = url_quote_plus(value)
        value = value.replace('+', '%20')
        value = value.replace('%40', '@')
        value = value.replace('%2C', ',')
        extras.append('%s=%s' % (key, value))
    elif 'body' == key or 'subject' == key:
      value = to_str(value).strip()
      if value:
        value = url_quote_plus(value)
        value = value.replace('+', '%20')
        extras.append('%s=%s' % (key, value))
    elif 'name' == key:
      name = value
    else:
      htmloptions.append('%s=%s' % (jinja2.escape(key), jinja2.escape(value)))
  
  extras = ('?' + '&'.join(extras)) if extras else ''
  htmloptions = (' ' + ' '.join(htmloptions)) if htmloptions else ''
  
  if encode is None:
    e_mail = jinja2.escape(mail)
    e_name = jinja2.escape(name)
    result = '<a href="mailto:%s%s"%s>%s</a>' % (e_mail, extras, htmloptions, e_name)
  else:
    o_mail = obfuscate(env, 'mailto:%s' % mail)
    o_name = obfuscate(env, name)
    result = '<a href="%s%s"%s>%s</a>' % (o_mail, extras, htmloptions, o_name)
    if 'js' == encode:
      o_str = obfuscate(env, 'document.write(\'%s\');' % result, js=True)
      result = '<script type="text/javascript">eval(unescape(\'%s\'));</script>' % o_str
  
  return to_markup(env, result)


def _iter_choices(choices):
  for elem in choices:
    if isinstance(choices, dict):
      choice = choices[elem]
    elif isinstance(elem, (list, tuple)):
      elem, choice = elem
    else:
      choice = elem
    yield elem, choice


@jinja2.environmentfunction
def select_tag(env, name, choices, value=None, blank=True, **kwds):
  value = _form_get_list(name, value)
  
  e_name = jinja2.escape(name)
  options = html_options(env, **kwds)
  
  output = [u'<select id="%s" name="%s"%s>' % (e_name, e_name, options)]
  if blank:
    output.append(u'  <option value=""></option>')
  
  choices = choices or []
  for elem, choice in _iter_choices(choices):
    elem = to_unicode(elem)
    choice = to_unicode(choice)
    e_elem = jinja2.escape(elem)
    e_choice = jinja2.escape(choice)
    selected_html = u' selected="selected"' if elem in value else u''
    output.append(u'  <option value="%s"%s>%s</option>' % (
      e_elem, selected_html, e_choice))
    
  output.append(u'</select>')
  
  result = u'\n'.join(output)
  return to_markup(env, result)


def check_or_radio_tag(env, type, name, choices, value=None):
  value = _form_get_list(name, value)
  output = []
  for elem, choice in _iter_choices(choices):
    output.append(check_or_radio_tag_one(
      env, type, name, (elem, choice), value))
  
  result = u'\n'.join(output)
  return to_markup(env, result)


def check_or_radio_tag_one(env, type, name, choices, value=None):
  elem, choice = choices
  elem = to_unicode(elem)
  choice = to_unicode(choice)
  value = _to_form_list(value)
  tag_id = u'%s-%s' % (name, elem)
  
  params = {'id': tag_id}
  if elem in value:
    params['checked'] = u'checked'
  
  label = label_tag(env, tag_id, choice)
  input = input_tag(env, type, name, elem, **params)
  
  result = input + label
  return to_markup(env, result)


@jinja2.environmentfunction
def label_tag(env, id, value):
  e_id = jinja2.escape(id)
  e_value = jinja2.escape(value)
  result = u'<label for="%s">%s</label>' % (e_id, e_value)
  return to_markup(env, result)


@jinja2.environmentfunction
def checkbox_tag(env, name, choices, value=None):
  return check_or_radio_tag(env, 'checkbox', name, choices, value)


@jinja2.environmentfunction
def radio_tag(env, name, choices, value=None):
  return check_or_radio_tag(env, 'radio', name, choices, value)


_USTRING_RE = re.compile(u'([\u0080-\uffff])')

@jinja2.environmentfilter
def escape_js(env, s, quote_double_quotes=False):
  s = to_unicode(s)
  s = s.replace('\\', '\\\\')
  s = s.replace('\r', '\\r')
  s = s.replace('\n', '\\n')
  s = s.replace('\t', '\\t')
  s = s.replace("'", "\\'")
  if quote_double_quotes:
    s = s.replace('"', '&quot;')
  return str(_USTRING_RE.sub(lambda _: r"\u%04x" % ord(_.group(1)), s))


@jinja2.environmentfunction
def link_options(env, **kwds):
  ### from symfony
  
  confirm = kwds.pop('confirm', None)
  post = kwds.pop('post', None)
  popup = kwds.pop('popup', None)
  
  def _popup_js(p, u='this.href'):
    if isinstance(p, list):
      if 2 <= len(p):
        return "var w=window.open(%s,'%s','%s');w.focus();" % (u, p[0], p[1])
      return "var w=window.open(%s,'%s');w.focus();" % (u, p[0])
    return "var w=window.open(%s);w.focus();" % (u,)
  
  def _post_js():
    from raginei.ext.csrf import csrf_token
    return ''.join([
      "var f = document.createElement('form'); f.style.display = 'none';"
      "this.parentNode.appendChild(f); f.method = 'post'; f.action = this.href;",
      "var m = document.createElement('input'); m.setAttribute('type', 'hidden');",
      "m.setAttribute('name', '_csrf'); m.setAttribute('value', '%s'); f.appendChild(m);" % (
        csrf_token(),),
      "f.submit();",
      ])
  
  def _confirm_js(msg):
    return "confirm('%s')" % escape_js(env, msg)
  
  onclick = kwds.get('onclick', '')
  if popup and post:
    raise ValueError('You can not use "popup" and "post" in the same link.')
  elif confirm and popup:
    kwds['onclick'] = onclick + (";if(%s){%s};return false;" % (_confirm_js(confirm), _popup_js(popup)))
  elif confirm and post:
    kwds['onclick'] = onclick + (";if(%s){%s};return false;" % (_confirm_js(confirm), _post_js()))
  elif confirm:
    if onclick:
      kwds['onclick'] = "if(%s){return %s}else{return false;}" % (_confirm_js(confirm), onclick)
    else:
      kwds['onclick'] = "return %s;" % _confirm_js(confirm)
  elif post:
    kwds['onclick'] = "%s return false;" % _post_js()
  elif popup:
    kwds['onclick'] = "%s return false;" % _popup_js(popup)
  
  return html_options(env, **kwds)


@jinja2.environmentfunction
def html_options(env, **kwds):
  if not kwds:
    return u''
  opts = []
  for n, v in kwds.iteritems():
    opts.append(u'%s="%s"' % (jinja2.escape(n), jinja2.escape(v)))
  result = u' %s ' % u' '.join(opts)
  return to_markup(env, result)


def limit_width(s, num, end=u'...'):
  if not s:
    return s
  length = int(num)
  if length <= 0:
    return u''
  s = to_unicode(s)
  if num >= len(s):
    return s
  return s[:num] + end


def format_number(s):
  if isinstance(s, basestring):
    s = long(s)
  s = ('%d' if isinstance(s, (int, long)) else '%f') % s
  slen = len(s)
  return ','.join(reversed([s[max(slen - (i + 3), 0):max(slen - i, 0)]
    for i in range(0, slen + ((3 - (slen % 3)) % 3), 3)]))


@jinja2.environmentfunction
def input_tag(env, type, name, value='', **kwds):
  value = _form_get(name, value)
  e_name = jinja2.escape(name)
  e_type = jinja2.escape(type)
  e_value = jinja2.escape(value)
  tag_id = kwds.pop('id', None) or ('form_' + e_name)
  options = html_options(env, **kwds)
  if 'textarea' == type:
    result = u'<textarea id="%s" name="%s" %s >%s</textarea>' % (
      tag_id, e_name, options, e_value)
  else:
    result = u'<input id="%s" type="%s" name="%s" value="%s" %s />' % (
      tag_id, e_type, e_name, e_value, options)
  return to_markup(env, result)


@jinja2.environmentfunction
def link(env, name, path, **kwds):
  options = dict([(k[1:], kwds.pop(k)) for k in kwds.keys() if k.startswith('_')])
  options_str = link_options(env, **options) if options else u''
  if not path.startswith('/') and not path.startswith('http'):
    path = url(path, **kwds)
  result = '<a href="%s"%s>%s</a>' % (
    jinja2.escape(path), options_str, jinja2.escape(name))
  return to_markup(env, result)


@jinja2.environmentfunction
def link_if(env, condition, name, *args, **kwds):
  if condition:
    return link(env, name, *args, **kwds)
  result = '<span>%s</span>' % jinja2.escape(name)
  return to_markup(env, result)


@jinja2.environmentfunction
def image_tag(env, src, **kwds):
  if not src.startswith('/') and not src.startswith('http'):
    src = current_app.static_dir + src
  result = u'<img src="%s"%s />' % (jinja2.escape(src), html_options(env, **kwds))
  return to_markup(env, result)


@jinja2.environmentfunction
def form_tag(env, path=None, **kwds):
  kwds.setdefault('method', 'post')
  if not path:
    path = request.path
  result = u'<form action="%s"%s>' % (path, html_options(env, **kwds))
  if kwds['method'] in ('delete', 'put'):
    result += ('<input type="hidden" name="_method" value="%s" />' % kwds['method'])
  return to_markup(env, result)


@jinja2.environmentfunction
def form_tag_close(env):
  return to_markup(env, '</form>')


def register(server):
  server.template_filter('date')(format_date)
  server.template_filter(nl2br)
  server.template_filter(obfuscate)
  server.template_filter(escape_js)
  server.template_filter('limit')(limit_width)
  server.template_filter('number')(format_number)
  server.template_func(mail_tag)
  server.template_func(select_tag)
  server.template_func(label_tag)
  server.template_func(checkbox_tag)
  server.template_func(radio_tag)
  server.template_func(link_options)
  server.template_func(html_options)
  server.template_func('input')(input_tag)
  server.template_func(link)
  server.template_func(link_if)
  server.template_func(image_tag)
  server.template_func(form_tag)
  server.template_func(form_tag_close)
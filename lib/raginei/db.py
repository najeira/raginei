# -*- coding: utf-8 -*-
"""
raginei.db
==========

:copyright: (c) 2011 by najeira <najeira@gmail.com>, All rights reserved.
:license: Apache License 2.0, see LICENSE for more details.
"""

from google.appengine.ext.db import *

import os
import string
import random
import pickle
import zlib
import datetime
import array
import copy
import functools
import threading
from google.appengine.datastore import entity_pb
from google.appengine.runtime import apiproxy_errors
from . import decorator
from . import timezone
from . import util


_local = threading.local()

_local.default_config = {
  'get': {'deadline': 5, 'interval': 0.1, 'retries': 0},
  'put': {'deadline': 10, 'interval': 0.1, 'retries': 0},
  }


def set_default_config(**kwds):
  """デフォルトの設定を変更します。
  
  Args:
    get_deadline: get時のdeadline
    get_interval: get時のinterval
    get_retries: get時のリトライ回数
    put_deadline: put時のdeadline
    put_interval: put時のinterval
    put_retries: put時のリトライ回数
  """
  for k, v in kwds.iteritems():
    if v is not None:
      typ, column = k.split('_')
      _local.default_config[typ][column] = v


def run_in_config_get_decorator(deadline=None, interval=None, retries=None):
  """getの設定を一時的に変更して関数を実行するためのデコレータを返します。
  
  >>> @db.run_in_config_get_decorator(...)
  >>> def func():
  >>>   ...
  >>> func()
  """
  return _run_in_config_onetime_decorator(
    'get', deadline=deadline, interval=interval, retries=retries)


def run_in_config_put_decorator(deadline=None, interval=None, retries=None):
  """putの設定を一時的に変更して関数を実行するためのデコレータを返します。
  
  >>> @db.run_in_config_get_decorator(...)
  >>> def func():
  >>>   ...
  >>> func()
  """
  return _run_in_config_onetime_decorator(
    'put', deadline=deadline, interval=interval, retries=retries)


def _run_in_config_onetime_decorator(config_type, deadline=None, interval=None, retries=None):
  def _decorator(func):
    @functools.wraps(func)
    def _wrapper(*args, **kwds):
      before = _local.default_config[config_type].copy()
      try:
        set_default_config(**{
          '%s_deadline' % config_type: deadline,
          '%s_interval' % config_type: interval,
          '%s_retries' % config_type: retries})
        return func(*args, **kwds)
      finally:
        _local.default_config[config_type] = before
    return _wrapper
  return _decorator


def run_in_config_get(func):
  """getの設定に従って関数を実行します"""
  return _run_in_config_decorator(func, lambda: _local.default_config['get'])


def run_in_config_put(func):
  """putの設定に従って関数を実行します"""
  return _run_in_config_decorator(func, lambda: _local.default_config['put'])


def _run_in_config_decorator(func, get_default_config):
  """指定された設定で関数を呼び出すためのデコレータです。
  
  この関数はconfig引数を受け付けるdb.get、db.putに対して使用します。
  """
  funcname = util.funcname(func)
  
  @functools.wraps(func)
  def _wrapper(*args, **kwds):
    default = get_default_config() or {}
    config = kwds.get('config')
    
    deadline = default.get('deadline', 30)
    retries = default.get('retries', 0)
    interval = default.get('interval', 0.1)
    
    new_config = None
    if config:
      deadline = config.deadline or deadline
    elif deadline:
      new_config = create_config(deadline=deadline)
    
    tries = 0
    while True:
      tries += 1
      kwds['config'] = new_config or config
      
      try:
        return func(*args, **kwds)
      except (Timeout, apiproxy_errors.DeadlineExceededError,
        apiproxy_errors.ApplicationError), e:
        #raise or continue
        if tries > retries:
          raise
        if isinstance(e, apiproxy_errors.ApplicationError) and \
          5 != e.application_error:
          raise
      
      #sleep
      wait_secs = interval * tries ** 2
      logging.warning('Retrying function %s in %f secs: %r' % (
        funcname, wait_secs, e))
      if wait_secs:
        time.sleep(wait_secs)
      
      #next config
      new_config = create_config(deadline=min(deadline * (tries + 1), 30))
      if config:
        new_config = config.merge(new_config)
      
  return _wrapper


def run_in_deadline_get(func):
  """getのdeadline設定に従って関数を実行します"""
  return _run_in_deadline_decorator(func, lambda: _local.default_config['get'])


def run_in_deadline_put(func):
  """putのdeadline設定に従って関数を実行します"""
  return _run_in_deadline_decorator(func, lambda: _local.default_config['put'])


def _run_in_deadline_decorator(func, get_default_config):
  """指定されたdeadline設定で関数を呼び出すためのデコレータです。
  
  この関数はconfig引数を受け付けるdb.get、db.putに対して使用します。
  """
  @functools.wraps(func)
  def _wrapper(*args, **kwds):
    config = kwds.get('config')
    if not config or not config.deadline:
      default = get_default_config() or {}
      deadline = default.get('deadline', 30)
      new_config = create_config(deadline=deadline)
      if config:
        new_config = config.merge(new_config)
      kwds['config'] = new_config
    return func(*args, **kwds)
  return _wrapper


_orig_get = get
_orig_get_async = get_async


@run_in_deadline_get
def get_async(keys, **kwargs):
  return _orig_get_async(keys, **kwargs)


@run_in_config_get
def get(keys, **kwargs):
  """指定されたKeyのエンティティを取得します。
  
  この関数は、設定によってタイムアウト時にリトライを行います。
  
  Args:
    keys: KeyまたはKeyのリスト
  
  Returns:
    Keyを指定した場合、エンティティ。エンティティが存在しない場合はNoneです。
    Keyのリストを指定した場合、エンティティのリスト。
    エンティティが存在しない場合はリスト中にNoneが入ります。
  """
  if not is_in_transaction() and isinstance(keys, list) and 2 <= len(keys):
    config = kwargs.get('config')
    if config:
      if config.read_policy is None:
        config.read_policy = EVENTUAL_CONSISTENCY
    else:
      kwargs['config'] = create_config(read_policy=EVENTUAL_CONSISTENCY)
  return _orig_get(keys, **kwargs)


_orig_put = put
_orig_put_async = put_async


@run_in_config_put
def _put_in_config(models, **kwargs):
  return _orig_put(models, **kwargs)


@run_in_deadline_put
def _put_async_in_deadline(models, **kwargs):
  return _orig_put_async(models, **kwargs)


def _before_put(models):
  model_list = [models] if isinstance(models, Model) else models
  for model in model_list:
    if not isinstance(model, ModelEx):
      continue
    model._is_new = not model.is_saved()
    model.validate()


def put_async(models, **kwargs):
  if is_in_transaction():
    _before_put(models)
    return _orig_put_async(models, **kwargs)
  else:
    assign_keys(models)
    _before_put(models)
    return _put_async_in_deadline(models, **kwargs)


def put(models, **kwargs):
  """エンティティを保存します。
  
  この関数は、設定によってタイムアウト時にリトライを行います。
  Keyが割り当てられていないエンティティに対しては、
  保存の前にKeyを割り当てるため、リトライによる多重保存はありません。
  
  ただし、トランザクション中に呼び出された場合は、
  リトライもKeyの割り当ても行いません。
  トランザクションのリトライはアプリケーション側で行う必要があります。
  
  Args:
    models: エンティティまたはエンティティのリスト
  
  Returns:
    エンティティを指定した場合、Key。
    エンティティのリストを指定した場合、Keyのリスト。
  """
  
  if is_in_transaction():
    _before_put(models)
    return _orig_put(models, **kwargs)
  else:
    assign_keys(models)
    _before_put(models)
    return _put_in_config(models, **kwargs)


save = put


def run_in_transaction_retries(retries=3, interval=0.1):
  """関数をトランザクション内で実行します。
  処理が失敗した場合は、データストアに対する操作はロールバックされます。
  
  この関数は、設定によってタイムアウト時にリトライを行います。
  このリトライが不要な場合はrun_in_transactionを使ってください。
  
  run_in_transactionとの違いは、
  このデコレータはタイムアウトでリトライするということです。
  run_in_transactionはトランザクションのエラーのみリトライします。
  
  >>> @run_in_transaction_retries()
  >>> def some_func(arg):
  >>>  ...
  >>> some_func(arg)
  
  >>> def some_func(arg):
  >>>  ...
  >>> run_in_transaction_retries()(some_func)(arg)
  
  Args:
    function: トランザクション内で実行する関数
    *args: 関数に渡される位置引数
    **kwargs: 関数に渡されるキーワード引数
  
  Returns:
    指定された関数の戻り値を、そのまま返します。
  """
  def _decorator(func):
    @decorator.retry_on_timeout(retries, interval)
    @functools.wraps(func)
    def _wrapper(*args, **kwds):
      return run_in_transaction(func, *args, **kwds)
    return _wrapper
  return _decorator


_orig_allocate_ids = allocate_ids


@decorator.retry_on_timeout()
def allocate_ids(key, count):
  """ModelのIDを確保します。
  この関数で取得されたIDは、以降、データストアでの自動採番で使われることはありません。
  
  この関数はタイムアウト時にリトライを行います。
  
  Args:
    key: 対象のModelのKey。kindとparentの決定のために使われ、idやkey_nameは無視されます。
    count: 確保するIDの数
  
  Returns:
    確保したIDの先頭と末尾のタプル
  """
  return _orig_allocate_ids(key, count)


_allocated_keys = {}


def allocate_keys(cls, count, parent=None):
  """ModelのKeyを確保します。
  この関数で取得されたKeyは、以降、データストアでの自動採番で使われることはありません。
  
  Args:
    cls: 対象のModelのclass
    count: 確保するIDの数
    parent: Keyのparent
  
  Returns:
    確保したKeyのリスト
  """
  
  #fetch from cache
  kind = cls.kind()
  if kind in _allocated_keys and _allocated_keys[kind]:
    keys = _allocated_keys[kind][0:count]
    del _allocated_keys[kind][0:count]
  else:
    keys = []
  
  #cache exists?
  count = count - len(keys)
  if not count:
    return keys
  
  #allocate ids
  first, last = allocate_ids(
    Key.from_path(kind, 1, parent=parent),
    max(count, 10))
  
  #put keys to return
  for i in xrange(count):
    keys.append(Key.from_path(kind, first + i, parent=parent))
  
  #put keys to cache
  amari = last - first - count + 1
  if amari:
    if kind not in _allocated_keys:
      _allocated_keys[kind] = []
    for i in xrange(amari):
      _allocated_keys[kind].append(
        Key.from_path(kind, first + count + i, parent=parent))
  
  return keys


def allocate_key(cls, parent=None):
  """ModelのKeyを確保します。
  この関数で取得されたKeyは、以降、データストアでの自動採番で使われることはありません。
  
  Args:
    cls: 対象のModelのclass
    parent: Keyのparent
  
  Returns:
    確保したKey
  """
  keys = allocate_keys(cls, 1, parent=parent)
  return keys[0]


def assign_keys(models):
  """Keyの割り当てられていないエンティティに対してKeyを割り当てます。
  
  Args:
    models: エンティティまたはエンティティのリスト
  """
  if isinstance(models, Model):
    models = [models]
  for model in models:
    if not model.has_key():
      key = allocate_key(model.__class__)
      model._key = key
      model._key_name = None
      model._parent = None
      model._parent_key = None


def serialize_models(models):
  """エンティティを文字列に変換します。
  
  Args:
    models: エンティティまたはエンティティのリスト
  """
  if models is None:
    return None
  elif isinstance(models, Model):
    return model_to_protobuf(models).Encode()
  else:
    return [model_to_protobuf(x).Encode() for x in models]


def deserialize_models(data):
  """エンティティを文字列表現からオブジェクトに変換します。
  
  Args:
    data: エンティティの文字列表現
  """
  if data is None:
    return None
  elif isinstance(data, str):
    return model_from_protobuf(entity_pb.EntityProto(data))
  else:
    return [model_from_protobuf(entity_pb.EntityProto(x)) for x in data]


def get_value(entity, prop):
  """エンティティのプロパティの値をデータストアに保存される形式で取得します。
  
  ReferencePropertyで参照を解決せずにKeyを取得することが出来ます。
  
  Args:
    entity: エンティティ
    prop: プロパティまたはプロパティ名
  """
  if isinstance(prop, basestring):
    prop = getattr(entity.__class__, prop)
  return prop.get_value_for_datastore(entity)


def prefetch_refs(entities, *props):
  """ReferencePropertyの参照先を解決します。
  参照先の取得を一度のAPIで取得します。
  
  Args:
    entities: エンティティのリスト
    *props: プロパティ
  """
  fields = [(entity, prop) for entity in entities for prop in props]
  ref_keys = filter(None, [prop.get_value_for_datastore(x) for x, prop in fields if x])
  config = create_config(read_policy=EVENTUAL_CONSISTECY)
  ref_entities = dict([(x.key(), x) for x in get(set(ref_keys), config=config)])
  for entity, prop in fields:
    key = prop.get_value_for_datastore(entity)
    if key:
      prop.__set__(entity, ref_entities.get(key))
  return entities


class ModelMixin(object):
  """モデルの機能を拡張するMixinです。"""

  @classmethod
  def to_key(cls, *args, **kwds):
    """引数からKeyを生成します。
    
    Args:
      *args: 数値の場合はid、文字列の場合はkey_nameとなります。
      *kwds: キーワード引数を文字列表現にしたものをkey_nameとします。
      parent: 親となるエンティティ、Key、None(default)
    
    Returns:
      Key
    """
    parent = kwds.pop('parent', None)
    if args:
      ret = args[0]
    else:
      ret = util.to_str(kwds)
    return Key.from_path(cls.kind(), ret, parent=parent)

  @classmethod
  @run_in_config_get
  def get(cls, key, parent=None, **kwds):
    """指定されたKeyのエンティティを取得します。
    
    Args:
      key: Key、またはKeyの文字列表現、または数値ID、またはそれらのリスト
    
    Returns:
      エンティティ。引数がリストの場合はエンティティのリスト。
      エンティティが存在しない場合はNone、引数がリストの場合は、
      エンティティが存在しない場合はNoneを含むリスト。
    """
    if key is None:
      return None
    elif isinstance(key, list):
      if 0 >= len(key):
        return []
      keys = []
      for x in key:
        if isinstance(x, Key):
          keys.append(x)
        elif isinstance(x, Model):
          keys.append(x.key())
        elif isinstance(x, basestring):
          keys.append(Key(x))
        else:
          keys.append(cls.to_key(x, parent))
      return super(ModelMixin, cls).get(keys, **kwds)
    elif isinstance(key, Key):
      return super(ModelMixin, cls).get(key, **kwds)
    elif isinstance(key, Model):
      return super(ModelMixin, cls).get(key.key(), **kwds)
    elif isinstance(key, basestring):
      return super(ModelMixin, cls).get(key, **kwds)
    else:
      return super(ModelMixin, cls).get(cls.to_key(key, parent), **kwds)
  
  @classmethod
  @run_in_config_get
  def get_by_id(cls, ids, parent=None, **kwds):
    """指定された数値IDのエンティティを取得します。
    
    Args:
      ids: 数値ID、またはそれらのリスト
      parent: 親となるエンティティ、Key、None(default)
    
    Returns:
      エンティティ。引数がリストの場合はエンティティのリスト。
      エンティティが存在しない場合はNone、引数がリストの場合は、
      エンティティが存在しない場合はNoneを含むリスト。
    """
    return super(ModelMixin, cls).get_by_id(ids, parent, **kwds)

  @classmethod
  @run_in_config_get
  def get_by_key_name(cls, key_names, parent=None, **kwds):
    """指定されたキー名のエンティティを取得します。
    
    Args:
      key_names: 数値ID、またはそれらのリスト
      parent: 親となるエンティティ、Key、None(default)
    
    Returns:
      エンティティ。引数がリストの場合はエンティティのリスト。
      エンティティが存在しない場合はNone、引数がリストの場合は、
      エンティティが存在しない場合はNoneを含むリスト。
    """
    return super(ModelMixin, cls).get_by_key_name(key_names, parent, **kwds)

  @classmethod
  def insert(cls, **kwds):
    """エンティティを保存します。
    引数の値がエンティティのプロパティに設定されます。
    
    key、key_name、idのいずれかが指定された場合で、
    すでに保存されたエンティティがある場合は例外が発生します。
    
    key、key_name、idが指定されなかった場合は、
    新しいエンティティとして保存されます。
    この場合は自動採番による数値IDを持つKeyが使われます。
    
    Args:
      key: Key
      key_name: key_name
      id: id
      **kwds: プロパティに設定する値
    """
    return cls._insert(_method='insert', **kwds)

  @classmethod
  def insert_or_update(cls, **kwds):
    """エンティティを保存します。
    引数の値がエンティティのプロパティに設定されます。
    
    key、key_name、idのいずれが指定された場合で、
    すでに保存されたエンティティがある場合は、
    データストアから取得したエンティティを更新して保存します。
    
    Args:
      key: Key
      key_name: key_name
      id: id
      **kwds: プロパティに設定する値
    """
    return cls._insert(_method='insert_or_update', **kwds)

  @classmethod
  def update(cls, **kwds):
    """エンティティを保存します。
    引数の値がエンティティのプロパティに設定されます。
    
    データストアから取得したエンティティを更新して保存します。
    すでに保存されたエンティティがない場合は、例外が発生します。
    key、key_name、idのいずれかを指定する必要があります。
    
    Args:
      key: Key
      key_name: key_name
      id: id
      **kwds: プロパティに設定する値
    """
    return cls._insert(_method='update', **kwds)

  @classmethod
  def replace(cls, **kwds):
    """エンティティを保存します。
    引数の値がエンティティのプロパティに設定されます。
    
    データストアにエンティティが保存されているかどうかに関係なく、
    エンティティを保存します。同じKeyのエンティティが存在する場合は、
    上書きになります。
    key、key_name、idのいずれかを指定する必要があります。
    
    Args:
      key: Key
      key_name: key_name
      id: id
      **kwds: プロパティに設定する値
    """
    return cls._insert(_method='replace', **kwds)

  @classmethod
  def _insert(cls, key=None, key_name=None, id=None, parent=None,
    _method=None, **kwds):
    """エンティティを保存します。
    
    key、 key_name、idが指定された場合の動作は_methodによって異なります。
    
    モデルがRevisionPropertyを持ち、引数にそのプロパティの値が指定された場合、
    データストアから取得したエンティティと比較し、値が異なる場合はCollisionErrorが発生します。
    これにより、複数のHTTPリクエストにまたがった処理での楽観的排他制御が可能です。
    
    Args:
      key: Key
      key_name: key_name
      id: id
      parent: 
      _method: 
      **kwds: プロパティに設定する値
    
    Returns:
      保存されたエンティティ
    """
    
    #トランザクション内の場合はそのまま実行
    if is_in_transaction():
      return cls._insert_impl(key=key, key_name=key_name, id=id, parent=parent,
        method=_method, **kwds)
    
    #Keyがない場合は確保しておく
    #リトライ時に複数のエンティティが保存されることを防ぐため
    if not (key or key_name or id):
      assert _method not in ('replace', 'update')
      key = cls.allocate_key(parent=kwds.get('parent'))
    
    #トランザクション内で実行
    return cls._insert_impl_tx(key=key, key_name=key_name, id=id, parent=parent,
      method=_method, **kwds)
  
  @classmethod
  @run_in_transaction_retries()
  def _insert_impl_tx(cls, key=None, key_name=None, id=None, parent=None,
    method=None, **kwds):
    assert key or key_name or id
    return cls._insert_impl(key=key, key_name=key_name, id=id, parent=parent,
      method=method, **kwds)
  
  @classmethod
  def _insert_impl(cls, key=None, key_name=None, id=None, parent=None,
    method=None, **kwds):
    entity = None
    
    if key:
      if 'replace' != method:
        entity = cls.get(key)
      if entity is None:
        if 'update' == method:
          raise Error() #not found
        kwds['key'] = key
      elif 'insert' == method:
        raise Error() #already exists
      
    elif id:
      lid = long(id)
      if 'replace' != method:
        entity = cls.get_by_id(lid)
      if entity is None:
        if 'update' == method:
          raise Error() #not found
        kwds['key'] = Key.from_path(cls.kind(), lid, parent=parent)
      elif 'insert' == method:
        raise Error() #already exists
      
    elif key_name:
      if 'replace' != method:
        entity = cls.get_by_key_name(key_name, parent)
      if entity is None:
        if 'update' == method:
          raise Error() #not found
        kwds['key'] = Key.from_path(cls.kind(), key_name, parent=parent)
      elif 'insert' == method:
        raise Error() #already exists
    
    rev_prop = getattr(cls, '_revision_property', None)
    
    if entity is None:
      entity = cls(**kwds)
      
    else:
      #エンティティがある場合で引数にリビジョンが
      #指定されている場合はリビジョンによる排他のチェック
      if rev_prop:
        kwds_rev = kwds.get(rev_prop.name)
        if kwds_rev is not None:
          if kwds_rev != rev_prop.__get__(entity):
            raise CollisionError()
    
    #db.Property以外を更新するためのapply
    entity.apply(**kwds)
    
    #あればリビジョン番号をあげておく
    if rev_prop:
      rev_prop.__set__(entity, rev_prop.__get__(entity) + 1)
    
    entity.put()
    
    return entity
  
  @classmethod
  def unique_key_name(cls, value):
    if value.startswith('__'):
      return u'a' + value
    return value
  
  @classmethod
  def put_unique(cls, value, owner=None):
    """一意な値を保存します。
    
    処理が成功した場合、その名前が新規作成されたことが保証されます。
    すでに名前が存在した場合は、UniqueKeyErrorが発生します。
    
    このメソッドで一意な名前を保存したあとに処理が中断した場合は、
    delete_uniqueメソッドで名前を削除する必要があります。
    
    Args:
      value: 保存する値
      owner: 関連するエンティティもしくはKey
    
    Returns:
      保存された一意な値のエンティティ
    """
    value = cls.unique_key_name(value)
    if owner:
      owner = owner if isinstance(owner, Key) else owner.key()
    def txn():
      entity = RagineiUniqueKey.get_by_key_name(value)
      if entity:
        raise UniqueKeyError()
      entity = RagineiUniqueKey(key_name=value, owner_key=owner)
      entity.put()
      return entity
    return run_in_transaction_retries()(txn)()

  def put_flag(self, value):
    assert is_in_transaction()
    
    if isinstance(value, basestring):
      value = cls.unique_key_name(value)
    
    key = RagineiFlag.to_key(value, parent=self.key())
    
    entity = RagineiFlag.get(key)
    if entity:
      raise UniqueKeyError()
    
    entity = RagineiFlag(key=key)
    entity.put()
    return entity
  
  @classmethod
  @decorator.retry_on_timeout()
  def delete_unique(cls, value):
    """一意な値を削除します。
    
    Args:
      value: 削除する値
    """
    value = cls.unique_key_name(value)
    delete(Key.from_path(RagineiUniqueKey.kind(), value))

  @property
  def uniques(self):
    return RagineiUniqueKey.all().filter('owner_key =', self.key())

  def validate(self):
    """プロパティの値を検証するために継承できます。
    
    このメソッドはエンティティがデータストアに保存される直前に呼び出されます。
    メソッド内で必要に応じてプロパティの値を変更しても構いません。
    
    このメソッドはトランザクション内で呼び出される可能性があるため、
    ReferencePropertyなどで他のモデルを取得することは出来ません。
    
    Memo:
      Model._populate_entityをオーバーライドして呼び出すのがよさそう
    """
    pass

  _apply_exclude = ('all', 'app', 'copy', 'delete', 'entity', 'entity_type',
    'fields', 'from_entity', 'get', 'gql', 'id', 'instance_properties',
    'is_saved', 'key', 'key_name', 'kind', 'parent', 'parent_key',
    'properties', 'put', 'setdefault', 'to_xml', 'update')

  def apply(self, **kwds):
    """エンティティの値を引数の値に更新します。
    
    このメソッドはデータストアへの保存は行いません。
    """
    props = self.properties()
    for name, value in kwds.iteritems():
      if name in props:
        props[name].__set__(self, value)
      elif name not in self._apply_exclude:
        setattr(self, name, value)

  def put(self):
    """エンティティをデータストアに保存します。"""
    return put(self)

  def serialize(self):
    return serialize_models(self)

  @classmethod
  def deserialize(cls, data):
    return deserialize_models(data)

  @property
  def is_new(self):
    """エンティティが新規作成されたものかどうかを返します。"""
    try:
      return self._is_new
    except AttributeError:
      return not self.is_saved()

  @property
  def key_or_none(self):
    """エンティティがキーを持っていればキーを返します。
    そうでない場合はNoneが返ります。
    """
    try:
      return self.key()
    except Exception:
      return None
  
  @classmethod
  def allocate_key(cls, parent=None):
    """モデルのKeyを確保します。
    
    Keyはデータストアで使われていない数値IDを持ちます。
    """
    return allocate_key(cls, parent=parent)
  
  @classmethod
  def allocate_id(cls, parent=None):
    """モデルのKeyを確保します。
    
    Keyはデータストアで使われていない数値IDを持ちます。
    """
    return cls.allocate_key(parent=parent).id()

  @property
  def key_id(self):
    """エンティティのキーのidを返します。"""
    return self.key().id()

  @property
  def key_name(self):
    """エンティティのキーのnameを返します。"""
    return self.key().name()

  @property
  def key_id_or_name(self):
    """エンティティのキーのidかnameを返します。"""
    return self.key().id_or_name()


class ModelEx(ModelMixin, Model):
  """拡張されたモデルの基底クラス"""
  pass


def to_unicode(s, charset='utf-8'):
  """値がUnicodeにして返します。
  
  値がリストの場合は各要素を再帰的にUnicodeにします。
  値が文字列でもリストでもない場合はそのまま返します。
  """
  if s is None:
    return s
  elif isinstance(s, dict):
    for k in s.iterkeys():
      s[k] = to_unicode(s[k])
    return s
  elif isinstance(s, list):
    return [to_unicode(x, charset) for x in s]
  elif isinstance(s, tuple):
    return (to_unicode(x, charset) for x in s)
  elif not isinstance(s, basestring):
    return s
  if not isinstance(s, unicode):
    s = unicode(s, charset)
  return s


class UniqueKeyError(Error):
  pass


class CollisionError(Error):
  pass


"""
aetycoon provides a library of useful App Engine datastore property classes.

The property classes included here cover use cases that are too specialized to
be included in the SDK, or simply weren't included, but are nevertheless
generally useful. They include:

- DerivedProperty, which allows you to automatically generate values
  - LowerCaseProperty, which stores the lower-cased value of another property
  - LengthProperty, which stores the length of another property
- ChoiceProperty efficiently handles properties which may only be assigned a
  value from a limited set of choices
- CompressedBlobProperty and CompressedTextProperty store data/text in a
  compressed form
- ArrayProperty store array.array objects for lean and efficient POD type
  storage
With aetycoon, you'll have all the properties you're ever likely to need.
"""


def DerivedProperty(func=None, *args, **kwargs):
  """Implements a 'derived' datastore property.

  Derived properties are not set directly, but are instead generated by a
  function when required. They are useful to provide fields in the datastore
  that can be used for filtering or sorting in ways that are not otherwise
  possible with unmodified data - for example, filtering by the length of a
  BlobProperty, or case insensitive matching by querying the lower cased version
  of a string.

  DerivedProperty can be declared as a regular property, passing a function as
  the first argument, or it can be used as a decorator for the function that
  does the calculation, either with or without arguments.

  Example:

  >>> class DatastoreFile(db.Model):
  ...   name = db.StringProperty(required=True)
  ...   name_lower = DerivedProperty(lambda self: self.name.lower())
  ...
  ...   data = db.BlobProperty(required=True)
  ...   @DerivedProperty
  ...   def size(self):
  ...     return len(self.data)
  ...
  ...   @DerivedProperty(name='sha1')
  ...   def hash(self):
  ...     return hashlib.sha1(self.data).hexdigest()

  You can read derived properties the same way you would regular ones:

  >>> file = DatastoreFile(name='Test.txt', data='Hello, world!')
  >>> file.name_lower
  'test.txt'
  >>> file.hash
  '943a702d06f34599aee1f8da8ef9f7296031d699'

  Attempting to set a derived property will throw an error:

  >>> file.name_lower = 'foobar'
  Traceback (most recent call last):
      ...
  DerivedPropertyError: Cannot assign to a DerivedProperty

  When persisted, derived properties are stored to the datastore, and can be
  filtered on and sorted by:

  >>> file.put() # doctest: +ELLIPSIS
  datastore_types.Key.from_path(u'DatastoreFile', ...)

  >>> DatastoreFile.all().filter('size =', 13).get().name
  u'Test.txt'
  """
  if func:
    # Regular invocation, or used as a decorator without arguments
    return _DerivedProperty(func, *args, **kwargs)
  else:
    # We're being called as a decorator with arguments
    def decorate(decorated_func):
      return _DerivedProperty(decorated_func, *args, **kwargs)
    return decorate


class _DerivedProperty(Property):
  def __init__(self, derive_func, *args, **kwargs):
    """Constructor.

    Args:
      func: A function that takes one argument, the model instance, and
        returns a calculated value.
    """
    super(_DerivedProperty, self).__init__(*args, **kwargs)
    self.derive_func = derive_func

  def __get__(self, model_instance, model_class):
    if model_instance is None:
      return self
    return self.derive_func(model_instance)

  def __set__(self, model_instance, value):
    raise DerivedPropertyError("Cannot assign to a DerivedProperty")


class LengthProperty(_DerivedProperty):
  """A convenience class for recording the length of another field

  Example usage:

  >>> class TagList(db.Model):
  ...   tags = db.ListProperty(unicode, required=True)
  ...   num_tags = LengthProperty(tags)

  >>> tags = TagList(tags=[u'cool', u'zany'])
  >>> tags.num_tags
  2
  """
  def __init__(self, property, *args, **kwargs):
    """Constructor.

    Args:
      property: The property to lower-case.
    """
    super(LengthProperty, self).__init__(
        lambda self: len(property.__get__(self, type(self))),
        *args, **kwargs)


def TransformProperty(source, transform_func=None, *args, **kwargs):
  """Implements a 'transform' datastore property.

  TransformProperties are similar to DerivedProperties, but with two main
  differences:
  - Instead of acting on the whole model, the transform function is passed the
    current value of a single property which was specified in the constructor.
  - Property values are calculated when the property being derived from is set,
    not when the TransformProperty is fetched. This is more efficient for
    properties that have significant expense to calculate.

  TransformProperty can be declared as a regular property, passing the property
  to operate on and a function as the first arguments, or it can be used as a
  decorator for the function that does the calculation, with the property to
  operate on passed as an argument.

  Example:

  >>> class DatastoreFile(db.Model):
  ...   name = db.StringProperty(required=True)
  ...
  ...   data = db.BlobProperty(required=True)
  ...   size = TransformProperty(data, len)
  ...
  ...   @TransformProperty(data)
  ...   def hash(val):
  ...     return hashlib.sha1(val).hexdigest()

  You can read transform properties the same way you would regular ones:

  >>> file = DatastoreFile(name='Test.txt', data='Hello, world!')
  >>> file.size
  13
  >>> file.data
  'Hello, world!'
  >>> file.hash
  '943a702d06f34599aee1f8da8ef9f7296031d699'

  Updating the property being transformed automatically updates any
  TransformProperties depending on it:

  >>> file.data = 'Fubar'
  >>> file.data
  'Fubar'
  >>> file.size
  5
  >>> file.hash
  'df5fc9389a7567ddae2dd29267421c05049a6d31'

  Attempting to set a transform property directly will throw an error:

  >>> file.size = 123
  Traceback (most recent call last):
      ...
  DerivedPropertyError: Cannot assign to a TransformProperty

  When persisted, transform properties are stored to the datastore, and can be
  filtered on and sorted by:

  >>> file.put() # doctest: +ELLIPSIS
  datastore_types.Key.from_path(u'DatastoreFile', ...)

  >>> DatastoreFile.all().filter('size =', 13).get().hash
  '943a702d06f34599aee1f8da8ef9f7296031d699'
  """
  if transform_func:
    # Regular invocation
    return _TransformProperty(source, transform_func, *args, **kwargs)
  else:
    # We're being called as a decorator with arguments
    def decorate(decorated_func):
      return _TransformProperty(source, decorated_func, *args, **kwargs)
    return decorate


class _TransformProperty(Property):
  def __init__(self, source, transform_func, *args, **kwargs):
    """Constructor.

    Args:
      source: The property the transformation acts on.
      transform_func: A function that takes the value of source and transforms
        it in some way.
    """
    super(_TransformProperty, self).__init__(*args, **kwargs)
    self.source = source
    self.transform_func = transform_func

  def __orig_attr_name(self):
    return '_ORIGINAL' + self._attr_name()

  def __transformed_attr_name(self):
    return self._attr_name()

  def __get__(self, model_instance, model_class):
    if model_instance is None:
      return self
    last_val = getattr(model_instance, self.__orig_attr_name(), None)
    current_val = self.source.__get__(model_instance, model_class)
    if last_val == current_val:
      try:
        return getattr(model_instance, self.__transformed_attr_name())
      except AttributeError:
        pass
    transformed_val = self.transform_func(current_val)
    setattr(model_instance, self.__orig_attr_name(), current_val)
    setattr(model_instance, self.__transformed_attr_name(), transformed_val)
    return transformed_val

  def __set__(self, model_instance, value):
    raise DerivedPropertyError("Cannot assign to a TransformProperty")


class KeyProperty(Property):
  """A property that stores a key, without automatically dereferencing it.

  Example usage:

  >>> class SampleModel(db.Model):
  ...   sample_key = KeyProperty()

  >>> model = SampleModel()
  >>> model.sample_key = db.Key.from_path("Foo", "bar")
  >>> model.put() # doctest: +ELLIPSIS
  datastore_types.Key.from_path(u'SampleModel', ...)

  >>> model.sample_key # doctest: +ELLIPSIS
  datastore_types.Key.from_path(u'Foo', u'bar', ...)
  """
  def validate(self, value):
    """Validate the value.

    Args:
      value: The value to validate.
    Returns:
      A valid key.
    """
    if isinstance(value, basestring):
      value = Key(value)
    if value is not None:
      if not isinstance(value, Key):
        raise TypeError("Property %s must be an instance of db.Key"
                        % (self.name,))
    return super(KeyProperty, self).validate(value)


class SetProperty(ListProperty):
  """A property that stores a set of things.

  This is a parameterized property; the parameter must be a valid
  non-list data type, and all items must conform to this type.

  Example usage:

  >>> class SetModel(db.Model):
  ...   a_set = SetProperty(int)

  >>> model = SetModel()
  >>> model.a_set = set([1, 2, 3])
  >>> model.a_set
  set([1, 2, 3])
  >>> model.a_set.add(4)
  >>> model.a_set
  set([1, 2, 3, 4])
  >>> model.put() # doctest: +ELLIPSIS
  datastore_types.Key.from_path(u'SetModel', ...)

  >>> model2 = SetModel.all().get()
  >>> model2.a_set
  set([1L, 2L, 3L, 4L])
  """

  def validate(self, value):
    value = Property.validate(self, value)
    if value is not None:
      if not isinstance(value, (set, frozenset)):
        raise BadValueError('Property %s must be a set' % self.name)
      value = self.validate_list_contents(value)
    return value

  def default_value(self):
    return set(Property.default_value(self))

  def get_value_for_datastore(self, model_instance):
    return list(super(SetProperty, self).get_value_for_datastore(model_instance))

  def make_value_from_datastore(self, value):
    if value is not None:
      return set(super(SetProperty, self).make_value_from_datastore(value))

  def get_value_for_form(self, instance):
    value = super(SetProperty, self).get_value_for_form(instance)
    if not value:
      return None
    if isinstance(value, set):
      value = '\n'.join(value)
    return value

  def make_value_from_form(self, value):
    if not value:
      return []
    if isinstance(value, basestring):
      value = value.splitlines()
    return set(value)


class ChoiceProperty(IntegerProperty):
  """A property for efficiently storing choices made from a finite set.

  This works by mapping each choice to an integer.  The choices must be hashable
  (so that they can be efficiently mapped back to their corresponding index).

  Example usage:

  >>> class ChoiceModel(db.Model):
  ...   a_choice = ChoiceProperty(enumerate(['red', 'green', 'blue']))
  ...   b_choice = ChoiceProperty([(0,None), (1,'alpha'), (4,'beta')])

  You interact with choice properties using the choice values:

  >>> model = ChoiceModel(a_choice='green')
  >>> model.a_choice
  'green'
  >>> model.b_choice == None
  True
  >>> model.b_choice = 'beta'
  >>> model.b_choice
  'beta'
  >>> model.put() # doctest: +ELLIPSIS
  datastore_types.Key.from_path(u'ChoiceModel', ...)

  >>> model2 = ChoiceModel.all().get()
  >>> model2.a_choice
  'green'
  >>> model.b_choice
  'beta'

  To get the int representation of a choice, you may use either access the
  choice's corresponding attribute or use the c2i method:
  >>> green = ChoiceModel.a_choice.GREEN
  >>> none = ChoiceModel.b_choice.c2i(None)
  >>> (green == 1) and (none == 0)
  True

  The int representation of a choice is needed to filter on a choice property:
  >>> ChoiceModel.gql("WHERE a_choice = :1", green).count()
  1
  """
  def __init__(self, choices, make_choice_attrs=True, *args, **kwargs):
    """Constructor.

    Args:
      choices: A non-empty list of 2-tuples of the form (id, choice). id must be
        the int to store in the database.  choice may be any hashable value.
      make_choice_attrs: If True, the uppercase version of each string choice is
        set as an attribute whose value is the choice's int representation.
    """
    super(ChoiceProperty, self).__init__(*args, **kwargs)
    self.index_to_choice = dict(choices)
    self.choice_to_index = dict((c,i) for i,c in self.index_to_choice.iteritems())
    if make_choice_attrs:
      for i,c in self.index_to_choice.iteritems():
        if isinstance(c, basestring):
          setattr(self, c.upper(), i)

  def get_choices(self):
    """Gets a list of values which may be assigned to this property."""
    return self.choice_to_index.keys()

  def c2i(self, choice):
    """Converts a choice to its datastore representation."""
    return self.choice_to_index[choice]

  def __get__(self, model_instance, model_class):
    if model_instance is None:
      return self
    index = super(ChoiceProperty, self).__get__(model_instance, model_class)
    return self.index_to_choice[index]

  def __set__(self, model_instance, value):
    try:
      index = self.c2i(value)
    except KeyError:
      raise BadValueError('Property %s must be one of the allowed choices: %s' %
                          (self.name, self.get_choices()))
    super(ChoiceProperty, self).__set__(model_instance, index)

  def get_value_for_datastore(self, model_instance):
    # just use the underlying value from the parent
    return super(ChoiceProperty, self).__get__(model_instance, model_instance.__class__)

  def make_value_from_datastore(self, value):
    if value is None:
      return None
    return self.index_to_choice[value]


class CompressedProperty(UnindexedProperty):
  """A unindexed property that is stored in a compressed form.

  CompressedTextProperty and CompressedBlobProperty derive from this class.
  """
  def __init__(self, level, *args, **kwargs):
    """Constructor.

    Args:
    level: Controls the level of zlib's compression (between 1 and 9).
    """
    super(CompressedProperty, self).__init__(*args, **kwargs)
    self.level = level

  def get_value_for_datastore(self, model_instance):
    value = self.value_to_str(model_instance)
    if value is not None:
      return Blob(zlib.compress(value, self.level))

  def make_value_from_datastore(self, value):
    if value is not None:
      ds_value = zlib.decompress(value)
      return self.str_to_value(ds_value)

  # override value_to_str and str_to_value to implement a new CompressedProperty
  def value_to_str(self, model_instance):
    """Returns the value stored by this property encoded as a (byte) string,
    or None if value is None.  This string will be stored in the datastore.
    By default, returns the value unchanged."""
    return self.__get__(model_instance, model_instance.__class__)

  def str_to_value(self, s):
    """Reverse of value_to_str.  By default, returns s unchanged."""
    return s


class CompressedBlobProperty(CompressedProperty):
  """A byte string that will be stored in a compressed form.

  Example usage:

  >>> class CompressedBlobModel(db.Model):
  ...   v = CompressedBlobProperty()

  You can create a CompressedBlobProperty and set its value with your raw byte
  string (anything of type str).  You can also retrieve the (decompressed) value
  by accessing the field.

  >>> model = CompressedBlobModel(v='\x041\x9f\x11')
  >>> model.v = 'green'
  >>> model.v
  'green'
  >>> model.put() # doctest: +ELLIPSIS
  datastore_types.Key.from_path(u'CompressedBlobModel', ...)

  >>> model2 = CompressedBlobModel.all().get()
  >>> model2.v
  'green'

  Compressed blobs are not indexed and therefore cannot be filtered on:

  >>> CompressedBlobModel.gql("WHERE v = :1", 'green').count()
  0
  """
  data_type = Blob

  def __init__(self, level=6, *args, **kwargs):
    super(CompressedBlobProperty, self).__init__(level, *args, **kwargs)


class CompressedTextProperty(CompressedProperty):
  """A string that will be stored in a compressed form (encoded as UTF-8).

  Example usage:

  >>> class CompressedTextModel(db.Model):
  ...  v = CompressedTextProperty()

  You can create a CompressedTextProperty and set its value with your string.
  You can also retrieve the (decompressed) value by accessing the field.

  >>> ustr = u'\u043f\u0440\u043e\u0440\u0438\u0446\u0430\u0442\u0435\u043b\u044c'
  >>> model = CompressedTextModel(v=ustr)
  >>> model.put() # doctest: +ELLIPSIS
  datastore_types.Key.from_path(u'CompressedTextModel', ...)

  >>> model2 = CompressedTextModel.all().get()
  >>> model2.v == ustr
  True

  Compressed text is not indexed and therefore cannot be filtered on:

  >>> CompressedTextModel.gql("WHERE v = :1", ustr).count()
  0
  """
  data_type = Text

  def __init__(self, level=6, encoding='utf-8', *args, **kwargs):
    super(CompressedTextProperty, self).__init__(level, *args, **kwargs)
    self.encoding = encoding

  def validate(self, value):
    if value is not None and not isinstance(value, basestring):
      raise BadValueError(
        'Property %s must be convertible to a str or unicode instance (%s)'
        % (self.name, value))
    if value and not isinstance(value, unicode):
      value = unicode(value, self.encoding)
    return super(self.__class__, self).validate(value)

  def value_to_str(self, model_instance):
    value = self.__get__(model_instance, model_instance.__class__)
    if value is None:
      return value
    if isinstance(value, unicode):
      value = value.encode(self.encoding)
    return value

  def str_to_value(self, s):
    if s is None:
      return s
    if s and not isinstance(s, unicode):
      s = unicode(s, self.encoding)
    return s


class ArrayProperty(UnindexedProperty):
  """An array property that is stored as a string.

  Example usage:

  >>> class ArrayModel(db.Model):
  ...  v = ArrayProperty('i')
  >>> m = ArrayModel()

  If you do not supply a default the array will be empty.

  >>> m.v
  array('i')

  >>> m.v.extend(range(5))
  >>> m.v
  array('i', [0, 1, 2, 3, 4])
  >>> m.put() # doctest: +ELLIPSIS
  datastore_types.Key.from_path(u'ArrayModel', ...)
  >>> m2 = ArrayModel.all().get()
  >>> m2.v
  array('i', [0, 1, 2, 3, 4])
  """
  data_type = array.array

  def __init__(self, typecode, *args, **kwargs):
    self._typecode = typecode
    kwargs.setdefault('default', array.array(typecode))
    super(ArrayProperty, self).__init__(typecode, *args, **kwargs)

  def get_value_for_datastore(self, model_instance):
    value = super(ArrayProperty, self).get_value_for_datastore(model_instance)
    return Blob(value.tostring())

  def make_value_from_datastore(self, value):
    if value is not None:
      return array.array(self._typecode, value)

  def empty(self, value):
    return value is None

  def validate(self, value):
    if not isinstance(value, array.array) or value.typecode != self._typecode:
      raise BadValueError(
        "Property %s must be an array instance with typecode '%s'" % (
          self.name, self._typecode))
    return super(ArrayProperty, self).validate(value)

  def default_value(self):
    return array.array(self._typecode,
                       super(ArrayProperty, self).default_value())


class DictProperty(Property):
  """辞書を格納するプロパティです。"""

  data_type = Blob

  def __init__(self, compress=True, **kwargs):
    super(DictProperty, self).__init__(**kwargs)
    self.compress = compress

  def get_value_for_datastore(self, model_instance):
    value = super(DictProperty, self).get_value_for_datastore(model_instance)
    if not value:
      return None
    value = pickle.dumps(to_unicode(value), -1)
    if self.compress:
      value = zlib.compress(value)
    return Blob(value)

  def make_value_from_datastore(self, value):
    if not value:
      return dict()
    if self.compress:
      try:
        value = zlib.decompress(value)
      except zlib.error:
        pass
    return pickle.loads(value)

  def validate(self, value):
    if value is not None and not isinstance(value, dict):
      raise BadValueError(
        'Property %s must be convertible to a dict instance (%s)'
        % (self.name, value))
    return super(DictProperty, self).validate(value)

  def default_value(self):
    return copy.copy(self.default) if self.default else {}


class PickleProperty(Property):
  """任意のオブジェクトを格納するプロパティです。"""

  data_type = Blob

  def __init__(self, compress=True, **kwargs):
    super(PickleProperty, self).__init__(**kwargs)
    self.compress = compress

  def get_value_for_datastore(self, model_instance):
    value = super(PickleProperty, self).get_value_for_datastore(model_instance)
    if not value:
      return None
    value = pickle.dumps(value, -1)
    if self.compress:
      value = zlib.compress(value)
    return Blob(value)

  def make_value_from_datastore(self, value):
    if not value:
      return None
    if self.compress:
      try:
        value = zlib.decompress(value)
      except zlib.error:
        pass
    return pickle.loads(value)

  def default_value(self):
    return copy.copy(self.default)


class SerializeModelProperty(Property):
  """モデルのエンティティを永続化するプロパティです。"""

  data_type = Blob

  def get_value_for_datastore(self, model_instance):
    value = super(SerializeModelProperty, self).get_value_for_datastore(model_instance)
    if not value:
      return None
    return Blob(zlib.compress(serialize_models(value)))

  def make_value_from_datastore(self, value):
    if not value:
      return None
    return deserialize_models(zlib.decompress(value))


class DateTimeId(datetime.datetime):
  """時刻ID"""

  def __str__(self):
    return '%s%s_%s' % (self.strftime('%Y%m%d%H%M%S'),
      ('%06d' % self.microsecond)[:3], self.salt)

  @classmethod
  def fromdatetime(cls, value):
    obj = cls(
      year=value.year,
      month=value.month,
      day=value.day,
      hour=value.hour,
      minute=value.minute,
      second=value.second,
      microsecond=value.microsecond,
      tzinfo=value.tzinfo,
      )
    return obj

  @classmethod
  def fromstring(cls, value, tzinfo=None):
    date_string, salt = value.split('_')
    date_obj = cls.strptime(date_string[:-3], '%Y%m%d%H%M%S')
    date_obj = date_obj.replace(
      tzinfo=tzinfo, microsecond=int(date_string[-3:]) * 1000)
    ret = cls.fromdatetime(date_obj)
    ret._salt = salt
    return ret

  @property
  def salt(self):
    try:
      return self._salt
    except AttributeError:
      self._salt = _randstr()
      return self._salt


class DateTimeProperty(Property):
  """"""

  data_type = datetime.datetime

  def __init__(self, verbose_name=None, auto_now=False, auto_now_add=False,
    unique=False, tzinfo=None, precision=None, **kwds):
    super(DateTimeProperty, self).__init__(verbose_name, **kwds)
    self.auto_now = auto_now
    self.auto_now_add = auto_now_add
    self.unique = unique
    self.tzinfo = tzinfo
    self.precision = precision

  def get_value_for_datastore(self, model_instance):
    if self.auto_now:
      value = self.now()
    else:
      value = super(DateTimeProperty, self).get_value_for_datastore(model_instance)
      if not value:
        return None
    if not self.unique:
      return value
    if not isinstance(value, DateTimeId):
      value = DateTimeId.fromdatetime(value)
    return str(value)

  def make_value_from_datastore(self, value):
    if not value:
      return None
    if isinstance(value, basestring):
      return DateTimeId.fromstring(value, self.tzinfo)
    if self.tzinfo:
      value = timezone.astimezone(value, self.tzinfo)
    return value

  def default_value(self):
    if self.auto_now or self.auto_now_add:
      return self.now()
    return copy.copy(self.default)

  def validate(self, value):
    if value is not None and not isinstance(value, datetime.datetime):
      raise BadValueError(
        'Property %s must be datetime.datetime instance (%s)'
        % (self.name, value))
    if value:
      if self.precision:
        if 'hour' == self.precision:
          value = value.replace(minute=0, second=0, microsecond=0)
        elif 'minute' == self.precision:
          value = value.replace(second=0, microsecond=0)
        elif 'second' == self.precision:
          value = value.replace(microsecond=0)
      if self.tzinfo:
        timezone.astimezone(value, self.tzinfo)
      if self.unique and not isinstance(value, DateTimeId):
        value = DateTimeId.fromdatetime(value)
    return super(DateTimeProperty, self).validate(value)

  def now(self):
    dt = datetime.datetime.utcnow()
    if self.tzinfo:
      dt = timezone.astimezone(dt, self.tzinfo)
    if self.unique:
      dt = DateTimeId.fromdatetime(dt)
    return dt


class Score(object):
  """"""

  def __init__(self, value, prefix=None, salt=None):
    self.value = self.str_to_value(value)
    self.prefix = prefix
    self.salt = salt or _randstr()

  def __str__(self):
    if self.prefix:
      return '%s_%s_%s' % (self.prefix, self.value_to_str(self.value), self.salt)
    else:
      return '%s_%s' % (self.value_to_str(self.value), self.salt)

  @property
  def score(self):
    return self.value

  @classmethod
  def fromstring(cls, value):
    parts = value.split('_')
    if 3 <= len(parts):
      return cls(parts[1], prefix=parts[0], salt=parts[2])
    else:
      return cls(parts[0], prefix=None, salt=parts[1])

  @classmethod
  def value_to_str(cls, value):
    if isinstance(value, (int, long)):
      return '%020d' % value
    elif isinstance(value, float):
      return '%020f' % value
    raise NotInplementedError()

  def str_to_value(self, value):
    if not isinstance(value, basestring):
      return value
    if '.' in value:
      return float(value)
    return long(value)

  def __int__(self):
    return long(self.value)

  def __long__(self):
    return long(self.value)

  def __float__(self):
    return float(self.value)

  def __lt__(self, other):
    if isinstance(other, (int, long, float)):
      return self.value < value
    return self.value < other.value

  def __le__(self, other):
    if isinstance(other, (int, long, float)):
      return self.value <= value
    return self.value <= other.value

  def __eq__(self, other):
    if other is None:
      return False
    if isinstance(other, (int, long, float)):
      return self.value == value
    return self.value == other.value

  def __ne__(self, other):
    return not self.__eq__(other)

  def __gt__(self, other):
    if isinstance(other, (int, long, float)):
      return self.value > value
    return self.value > other.value

  def __ge__(self, other):
    if isinstance(other, (int, long, float)):
      return self.value >= value
    return self.value >= other.value


class ScoreProperty(Property):
  data_type = basestring

  def __init__(self, default=0, **kwargs):
    super(ScoreProperty, self).__init__(default=default, **kwargs)

  def get_value_for_datastore(self, model_instance):
    value = super(ScoreProperty, self).get_value_for_datastore(model_instance)
    if value is None:
      return None
    if not isinstance(value, Score):
      value = Score(value)
    return str(value)

  def make_value_from_datastore(self, value):
    if value is None:
      return None
    return Score.fromstring(value)

  def validate(self, value):
    if value is not None and not isinstance(value, Score):
      if not isinstance(value, (int, long, float)):
        raise BadValueError(
          'Property %s must be convertible to a (int, long, float) instance (%s)'
          % (self.name, value))
      value = Score(value)
    return super(ScoreProperty, self).validate(value)


class SaltProperty(Property):
  """ランダムな文字列のプロパティです。"""

  data_type = basestring

  def __init__(self, length=5, auto_gen=False, auto_gen_add=False, chars=None, **kwds):
    super(SaltProperty, self).__init__(**kwds)
    self.length = length
    self.auto_gen = auto_gen
    self.auto_gen_add = auto_gen_add
    self.chars = chars

  def get_value_for_datastore(self, model_instance):
    if self.auto_gen:
      return self.generate()
    return super(SaltProperty, self).get_value_for_datastore(model_instance)

  def validate(self, value):
    if True == value:
      return self.generate()
    return value

  def default_value(self):
    if self.auto_gen or self.auto_gen_add:
      return self.generate()
    return super(SaltProperty, self).default_value()

  def generate(self):
    return _randstr(self.length, self.chars)


_FloatProperty = FloatProperty


class FloatProperty(_FloatProperty):

  def __init__(self, auto_gen=False, auto_gen_add=False, **kwds):
    super(FloatProperty, self).__init__(**kwds)
    self.auto_gen = auto_gen
    self.auto_gen_add = auto_gen_add

  def get_value_for_datastore(self, model_instance):
    if self.auto_gen:
      return random.random()
    return super(FloatProperty, self).get_value_for_datastore(model_instance)

  def default_value(self):
    if self.auto_gen or self.auto_gen_add:
      return random.random()
    return super(FloatProperty, self).default_value()


class EnvironProperty(Property):
  """環境変数を保存するためのプロパティです。"""

  data_type = Blob

  HEADERS = ('HTTP_USER_AGENT','HTTP_X_FORWARDED_FOR','HTTP_X_REAL_IP',
    'REMOTE_ADDR','HTTP_CLIENT_IP','CURRENT_VERSION_ID','PATH_INFO',
    'QUERY_STRING','REQUEST_METHOD')

  def __init__(self, auto_now=False, auto_now_add=False, headers=None, **kwds):
    super(EnvironProperty, self).__init__(**kwds)
    self.auto_now = auto_now
    self.auto_now_add = auto_now_add
    self.headers = headers

  def get_value_for_datastore(self, model_instance):
    if self.auto_now:
      value = self.environ()
    else:
      value = super(EnvironProperty, self).get_value_for_datastore(model_instance)
    if not value:
      return None
    return Blob(zlib.compress(pickle.dumps(value, -1)))

  def make_value_from_datastore(self, value):
    if not value:
      return None
    try:
      value = zlib.decompress(value)
    except zlib.error:
      pass
    return pickle.loads(value)

  def default_value(self):
    if self.auto_now or self.auto_now_add:
      return self.environ()
    return super(EnvironProperty, self).default_value()

  def validate(self, value):
    if True == value:
      return self.environ()
    return value

  def environ(self):
    rets = {}
    for k in self.headers or self.HEADERS:
      v = os.environ.get(k)
      if v:
        try:
          rets[k] = unicode(v, 'utf-8')
        except UnicodeDecodeError:
          pass
    return rets


class RevisionProperty(IntegerProperty):
  def __init__(self, default=0, **kwds):
    super(RevisionProperty, self).__init__(default=default, **kwds)
  
  def __property_config__(self, model_class, property_name):
    super(RevisionProperty, self).__property_config__(model_class, property_name)
    if hasattr(model_class, '_revision_property'):
      raise DuplicatePropertyError('Duplicate RevisionProperty: %s and %s' % (
        model_class._revision_property.name, property_name))
    model_class._revision_property = self


_SALT_CHARS = string.ascii_lowercase + string.digits

def _randstr(length=9, chars=None):
  if length <= 0:
    raise ValueError()
  return ''.join(random.choice(chars or _SALT_CHARS) for _ in xrange(length))


class RagineiUniqueKey(Model):
  """一意な名前のためのクラス"""
  owner_key = KeyProperty()

  @property
  def owner(self):
    return get(self.owner_key)


class RagineiFlag(ModelEx):
  """"""

# -*- coding:utf-8 -*-

import unittest
from base import GaeTestCase
from raginei import db

import hashlib
import datetime


class Sample(db.ModelEx):
  
  data = db.TextProperty(default='')
  data2 = db.TextProperty(default='')
  
  @db.DerivedProperty
  def data_len(self):
    return len(self.data)
  
  data_len2 = db.LengthProperty(data)
  
  @db.TransformProperty(data)
  def data_hash(val):
    return hashlib.sha1(val or '').hexdigest()
  
  a_set = db.SetProperty(int)
  a_dict = db.DictProperty()
  a_dti = db.DateTimeProperty(unique=True)
  a_salt = db.SaltProperty(length=5, auto_gen_add=True)
  a_float = db.FloatProperty(auto_gen_add=True)
  a_score = db.ScoreProperty()
  
  a_key = db.KeyProperty()
  
  comp_blob = db.CompressedBlobProperty()
  comp_text = db.CompressedTextProperty()
  
  def validate(self):
    if 'this_is_fail_on_validate' == self.data:
      raise ValueError()
    elif 'should_be_applied_key' == self.data:
      assert self.has_key()


class MyTest(GaeTestCase):

  def setUp(self):
    super(MyTest, self).setUp()

  def tearDown(self):
    db.delete(Sample.all(keys_only=True).fetch(500))
    super(MyTest, self).tearDown()

  def test_ScoreProperty(self):
    obj = Sample(a_score=12345)
    self.assert_(obj.a_score.score == 12345)
    self.assert_(obj.a_score.value == 12345)
    obj.put()
    obj2 = db.get(obj.key())
    self.assert_(obj.a_score.score == obj2.a_score.score)
    self.assert_(obj.a_score.value == obj2.a_score.value)
    self.assert_(obj.a_score == obj2.a_score)

  def test_CompressedBlobProperty(self):
    f = open(__file__, 'rb')
    try:
      data = f.read()
      
      obj = Sample(comp_blob=data)
      self.assert_(obj.comp_blob == data)
      self.assert_(len(obj.comp_blob) != len(db.get_value(obj, 'comp_blob')))
      obj.put()
      
      obj2 = db.get(obj.key())
      self.assert_(obj.comp_blob == obj2.comp_blob)
      
    finally:
      f.close()

  def test_CompressedTextProperty(self):
    data2 = u'テスト文字列'
    obj = Sample(comp_text=data2)
    self.assert_(obj.comp_text == data2)
    self.assert_(len(obj.comp_text) != len(db.get_value(obj, 'comp_text')))
    obj.put()
    
    obj2 = db.get(obj.key())
    self.assert_(obj.comp_text == obj2.comp_text)

  def test_Model_replace(self):
    obj = Sample.insert(data='data', data2='data2')
    
    obj2 = Sample.replace(key=obj.key(), data='replaced')
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    self.assert_(obj2.data == 'replaced')
    self.assert_(obj2.data2 != 'data2')
    obj2 = db.get(obj2.key())
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())

  def test_Model_update(self):
    obj = Sample.insert(data='this_is_test')
    
    obj2 = Sample.update(key=obj.key(), data='this_is_updated')
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    self.assert_(obj2.data == 'this_is_updated')
    obj2 = db.get(obj2.key())
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    
    try:
      Sample.update(key_name='not_exists', data='this_is_updated')
      self.fail()
    except:
      pass

  def test_Model_insert_or_update(self):
    obj = Sample.insert(data='this_is_test')
    obj2 = Sample.insert_or_update(key=obj.key(), data='this_is_updated')
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    self.assert_(obj2.data == 'this_is_updated')
    obj2 = db.get(obj2.key())
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    
    obj2 = Sample.insert_or_update(id=obj.key_id,
      data='this_is_updated_by_id')
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    self.assert_(obj2.data == 'this_is_updated_by_id')
    obj2 = db.get(obj2.key())
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    
    obj = Sample.insert(key_name='hoge', data='this_is_test')
    obj2 = Sample.insert_or_update(key_name=obj.key_name,
      data='this_is_updated_by_key_name')
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    self.assert_(obj2.data == 'this_is_updated_by_key_name')
    obj2 = db.get(obj2.key())
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    
    obj = Sample.insert_or_update(key_name='fuga', data='this_is_inserted')
    self.assert_(obj)
    self.assert_(obj.data == 'this_is_inserted')
    obj2 = db.get(obj.key())
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())

  def test_Model_insert1(self):
    obj = Sample.insert(data='this_is_test')
    self.assert_(obj)
    self.assert_(obj.data == 'this_is_test')
    obj2 = db.get(obj.key())
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())

  def test_Model_insert2(self):
    key = Sample.allocate_key()
    obj = Sample.insert(key=key, data='this_is_test')
    self.assert_(obj)
    self.assert_(obj.data == 'this_is_test')
    obj2 = db.get(key)
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())

  def test_Model_insert3(self):
    key = Sample.allocate_key()
    obj = Sample.insert(id=key.id(), data='this_is_test')
    self.assert_(obj)
    self.assert_(obj.data == 'this_is_test')
    obj2 = db.get(key)
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())

  def test_Model_insert4(self):
    obj = Sample.insert(key_name='hoge', data='this_is_test')
    self.assert_(obj)
    self.assert_(obj.data == 'this_is_test')
    obj2 = db.get(Sample.to_key('hoge'))
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())

  def test_assign_keys(self):
    db.put(Sample(data='should_be_applied_key'))

  def test_assign_keys2(self):
    db.put([Sample(data='should_be_applied_key'),
      Sample(data='should_be_applied_key')])

  def test_assign_keys3(self):
    Sample(data='should_be_applied_key').put()

  def test_in_transaction(self):
    def txn():
      self.assert_(db.is_in_transaction())
    db.run_in_transaction(txn)

  def test_Model_validate(self):
    obj = Sample(data='this_is_fail_on_validate')
    try:
      obj.put()
      self.fail()
    except:
      pass

  def test_Model_query(self):
    obj = Sample(data='hogehoge')
    obj.put()
    obj2 = Sample.all().filter('data_len =', obj.data_len).get()
    self.assert_(obj.key() == obj2.key())
    obj2 = Sample.all().filter('data_len2 =', obj.data_len2).get()
    self.assert_(obj.key() == obj2.key())
    obj2 = Sample.all().filter('data_hash =', obj.data_hash).get()
    self.assert_(obj.key() == obj2.key())

  def test_Model_unique(self):
    db.put_unique('hoge')
    try:
      db.put_unique('hoge')
      self.fail()
    except db.UniqueKeyError:
      pass
    db.delete_unique('hoge')
    db.put_unique('hoge')

  def test_Model_unique2(self):
    db.put_unique('__hoge__')
    try:
      db.put_unique('__hoge__')
      self.fail()
    except db.UniqueKeyError:
      pass
    try:
      db.put_unique('a__hoge__')
      self.fail()
    except db.UniqueKeyError:
      pass
    db.delete_unique('__hoge__')
    db.put_unique('__hoge__')
    db.delete_unique('a__hoge__')
    db.put_unique('__hoge__')

  def test_Model_key_name(self):
    obj = Sample(key_name='hoge')
    self.assert_(obj.key_name == 'hoge')
    self.assert_(obj.key_id_or_name == 'hoge')

  def test_Model_key_id(self):
    obj = Sample()
    try:
      obj.key_id
      self.fail()
    except:
      pass
    obj.put()
    self.assert_(obj.key_id)
    self.assert_(obj.key_id_or_name)
    self.assert_(obj.key_id_or_name == obj.key_id)

  def test_Model_key_id_or_name(self):
    obj = Sample()
    try:
      obj.key_id_or_name
      self.fail()
    except:
      pass
    obj.put()
    self.assert_(obj.key_id)
    self.assert_(obj.key_id_or_name)
    self.assert_(obj.key_id_or_name == obj.key_id)

  def test_Model_key_id_or_name2(self):
    obj = Sample(key_name='hoge')
    try:
      obj.key_id_or_name
      self.fail()
    except:
      pass
    obj.put()
    self.assert_(obj.key_id_or_name == 'hoge')

  def test_Model_key_or_none(self):
    obj = Sample()
    self.assert_(obj.key_or_none is None)
    obj.put()
    self.assert_(obj.key_or_none is not None)
    obj2 = db.get(obj.key())
    self.assert_(obj2.key_or_none is not None)

  def test_apply(self):
    obj = Sample()
    self.assert_(obj.data == '')
    obj.apply(data='hoge')
    self.assert_(obj.data == 'hoge')
    obj.apply(parent='hoge')
    self.assert_(obj.parent != 'hoge')

  def test_to_key(self):
    key = Sample.to_key(123)
    self.assert_(key)
    self.assert_(isinstance(key, db.Key))
    self.assert_(key.kind() == Sample.kind())
    self.assert_(key.id() == 123)
    self.assert_(key.id_or_name() == 123)
    self.assert_(not key.name())

  def test_to_key2(self):
    key = Sample.to_key('hoge')
    self.assert_(key)
    self.assert_(isinstance(key, db.Key))
    self.assert_(key.kind() == Sample.kind())
    self.assert_(key.name() == 'hoge')
    self.assert_(key.id_or_name() == 'hoge')
    self.assert_(not key.id())

  def test_to_key3(self):
    key = Sample.to_key(hoge='fuga', foo='bar')
    self.assert_(key)
    self.assert_(isinstance(key, db.Key))
    self.assert_(key.kind() == Sample.kind())
    self.assert_(key.name() == 'foo=bar&hoge=fuga')
    self.assert_(key.id_or_name() == 'foo=bar&hoge=fuga')
    self.assert_(not key.id())

  def test_to_key4(self):
    key = Sample.to_key(hoge='fuga', foo=5)
    self.assert_(key.name() == 'foo=5&hoge=fuga')

  def test_allocate_ids(self):
    first, last = db.allocate_ids(db.Key.from_path(Sample.kind(), 1), 10)
    self.assert_((last - first) == 9)

  def test_allocate_keys(self):
    keys = db.allocate_keys(Sample, 10)
    self.assert_(keys)
    self.assert_(10 == len(keys))
    self.assert_(isinstance(keys[0], db.Key))
    self.assert_(keys[0].id() != keys[-1].id())

  def test_run_in_transaction(self):
    obj = Sample()
    key = db.run_in_transaction(db.put, obj)
    self.assert_(key)
    obj2 = db.get(key)
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    
    obj = Sample(key_name='hoge')
    def txn():
      obj.put()
      raise Exception()
    try:
      db.run_in_transaction(txn)
      self.fail()
    except:
      self.assert_(Sample.get_by_key_name('hoge') is None)

  def test_serialize_models(self):
    obj = Sample()
    obj.data = 'hoge'
    seri = db.serialize_models(obj)
    self.assert_(seri)
    self.assert_(isinstance(seri, basestring))
    deseri = db.deserialize_models(seri)
    self.assert_(deseri)
    self.assert_(isinstance(deseri, Sample))
    self.assert_(obj.data == deseri.data)

  def test_Model_get_by_id(self):
    obj = Sample()
    obj.put()
    obj2 = Sample.get_by_id(obj.key_id)
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())

  def test_Model_get_by_key_name(self):
    obj = Sample(key_name='hoge')
    obj.put()
    obj2 = Sample.get_by_key_name(obj.key_name)
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())

  def test_Model_get(self):
    obj = Sample()
    obj.put()
    
    obj2 = Sample.get(obj)
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    
    obj2 = Sample.get(obj.key())
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())
    
    obj2 = Sample.get(obj.key_id)
    self.assert_(obj2)
    self.assert_(obj2.key() == obj.key())

  def test_Model_put(self):
    obj = Sample()
    self.assert_(obj.is_new)
    obj.put()
    self.assert_(obj.is_new)
    obj2 = db.get(obj.key())
    self.assert_(obj2)
    self.assert_(obj.key() == obj2.key())
    self.assert_(not obj2.is_new)

  def test_get_put(self):
    obj = Sample()
    self.assert_(obj.key_or_none is None)
    db.put(obj)
    self.assert_(obj.key_or_none is not None)
    obj2 = db.get(obj.key())
    self.assert_(obj2)
    self.assert_(obj.key() == obj2.key())

  def test_get_put_multi(self):
    db.put([Sample(key_name='foo'), Sample(key_name='bar')])
    self.assert_(Sample.get_by_key_name('foo'))
    self.assert_(Sample.get_by_key_name('bar'))
    gets = db.get([Sample.to_key('foo'), Sample.to_key('bar')])
    self.assert_(gets and 2 == len(gets))

  def test_allocate_key(self):
    key = Sample.allocate_key()
    self.assert_(key)
    self.assert_(key.kind() == Sample.kind())
    self.assert_(isinstance(key.id(), (int, long)))
    self.assert_(key.id() == key.id_or_name())
    key = db.allocate_key(Sample)
    self.assert_(key)
    self.assert_(key.kind() == Sample.kind())
    self.assert_(isinstance(key.id(), (int, long)))
    self.assert_(key.id() == key.id_or_name())

  def test_FloatProperty(self):
    obj = Sample()
    self.assert_(isinstance(obj.a_float, float))
    obj.put()
    
    obj2 = obj.get(obj.key())
    self.assert_(isinstance(obj2.a_float, float))
    self.assert_(obj.a_float == obj2.a_float)

  def test_SaltProperty(self):
    obj = Sample()
    self.assert_(isinstance(obj.a_salt, basestring))
    obj.put()
    
    obj2 = obj.get(obj.key())
    self.assert_(isinstance(obj2.a_salt, basestring))
    self.assert_(obj.a_salt == obj2.a_salt)

  def test_DateTimeIdProperty(self):
    obj = Sample()
    self.assert_(obj.a_dti is None)
    obj.a_dti = datetime.datetime(2010, 12, 10, 17, 51, 30)
    self.assert_(isinstance(obj.a_dti, datetime.datetime))
    self.assert_(2010 == obj.a_dti.year)
    self.assert_(12 == obj.a_dti.month)
    self.assert_(10 == obj.a_dti.day)
    self.assert_(17 == obj.a_dti.hour)
    self.assert_(51 == obj.a_dti.minute)
    self.assert_(30 == obj.a_dti.second)
    for_ds = db.get_value(obj, 'a_dti')
    self.assert_(isinstance(for_ds, basestring))
    obj.put()
    
    obj2 = obj.get(obj.key())
    self.assert_(isinstance(obj2.a_dti, datetime.datetime))
    self.assert_(for_ds == db.get_value(obj2, 'a_dti'))

  def test_DictProperty(self):
    obj = Sample()
    obj.a_dict = {'hoge': 'fuga', 'foo': 'bar'}
    self.assert_(isinstance(obj.a_dict, dict))
    self.assert_(2 == len(obj.a_dict))
    obj.a_dict['aaa'] = 'bbb'
    self.assert_(3 == len(obj.a_dict))
    obj.put()
    
    obj2 = obj.get(obj.key())
    self.assert_(isinstance(obj2.a_dict, dict))
    self.assert_(3 == len(obj2.a_dict))

  def test_SetProperty(self):
    obj = Sample()
    obj.a_set = set([1, 2, 3])
    self.assert_(isinstance(obj.a_set, set))
    self.assert_(3 == len(obj.a_set))
    obj.a_set.add(4)
    self.assert_(4 == len(obj.a_set))
    obj.a_set.add(3) #duplicate
    self.assert_(4 == len(obj.a_set))
    obj.put()
    
    obj2 = obj.get(obj.key())
    self.assert_(isinstance(obj2.a_set, set))
    self.assert_(4 == len(obj2.a_set))

  def test_TransformProperty(self):
    obj = Sample()
    obj.data = 'hogehoge'
    self.assert_(hashlib.sha1(obj.data).hexdigest() == obj.data_hash)
    obj.put()
    
    obj2 = obj.get(obj.key())
    self.assert_(obj2)
    self.assert_(hashlib.sha1(obj.data).hexdigest() == obj2.data_hash)

  def test_LengthProperty(self):
    obj = Sample()
    obj.data = 'hogehoge'
    self.assert_(len(obj.data) == obj.data_len2)
    obj.put()
    
    obj2 = obj.get(obj.key())
    self.assert_(obj2)
    self.assert_(len(obj2.data) == obj2.data_len2)

  def test_DerivedProperty(self):
    obj = Sample()
    obj.data = 'hogehoge'
    self.assert_(len(obj.data) == obj.data_len)
    obj.put()
    
    obj2 = obj.get(obj.key())
    self.assert_(obj2)
    self.assert_(len(obj2.data) == obj2.data_len)

  def test_KeyProperty(self):
    obj = Sample()
    obj.a_key = Sample.to_key('hoge')
    self.assert_(isinstance(obj.a_key, db.Key))
    obj.put()
    obj2 = Sample.get(obj)
    self.assert_(obj.key() == obj2.key())
    obj2 = Sample.all().filter('a_key =', obj.a_key).get()
    self.assert_(obj.key() == obj2.key())

  def test_default_config_put(self):
    def tmp(ex, config=None):
      if ex:
        if not config or 20 >= config.deadline:
          raise ex
      
    try:
      db.run_in_config_put(tmp)(db.Timeout())
      self.fail()
    except:
      pass
    
    db.set_default_config(put_deadline=5)
    db.set_default_config(put_retries=5)
    db.set_default_config(put_interval=0)
    db.run_in_config_put(tmp)(db.Timeout)

  def test_default_config_get(self):
    def tmp(ex, config=None):
      if ex:
        if not config or 20 >= config.deadline:
          raise ex
      
    try:
      db.run_in_config_get(tmp)(db.Timeout())
      self.fail()
    except:
      pass
    
    db.set_default_config(get_deadline=5)
    db.set_default_config(get_retries=5)
    db.set_default_config(get_interval=0)
    db.run_in_config_get(tmp)(db.Timeout)

  def test_run_in_transaction_retries(self):
    def tmp(flg):
      if 'raise' == flg.data:
        flg.data = ''
        raise db.Timeout()
    
    obj = Sample()
    obj.data = 'raise'
    db.run_in_transaction_retries(5)(tmp)(obj)

if __name__ == '__main__':
    unittest.main()

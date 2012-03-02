# -*- coding:utf-8 -*-

import sys
import logging
import unittest
try:
  import xmlrunner
except ImportError:
  xmlrunner = None
from optparse import OptionParser

def usage():
  print 'test.py  [-t testsuite] [-v verbosity] [-x xmlrunner]'
  print '    -t   run specific testsuite (app|template|all)'
  print '    -v   verbosity (0|1|2)'
  print '    -x   xmlrunner'

def main():
  parser = OptionParser()
  parser.add_option("-x", "--xmlrunner", action="store_true", dest="is_xmlrunner",
    default=False, help="use xmlrunner. default is False")
  parser.add_option("-v", "--verbosity", action="store",
    type="int", dest="verbosity", default=1,
    help="verbosity (0|1|2). default is 1")
  parser.add_option("-t", "--testsuite", action="store",
    type="string", dest="testsuite", default="all",
    help="run specific testsuite (app|template|all). default is all")
  opts, args = parser.parse_args()
  tests = suite(opts.testsuite)
  if opts.verbosity > 1:
    logging.basicConfig(level=logging.DEBUG)
  if opts.is_xmlrunner and xmlrunner:
    runner = xmlrunner.XMLTestRunner(verbose=opts.verbosity >= 1)
  else:
    runner = unittest.TextTestRunner(verbosity=opts.verbosity)
  runner.run(tests)

def suite(testsuite='all'):
  tests = unittest.TestSuite()
  
  import raginei_app
  import raginei_template
  
  if testsuite in ('all', 'app'):
    tests.addTest(unittest.makeSuite(raginei_app.MyTest))
  
  if testsuite in ('all', 'template'):
    tests.addTest(unittest.makeSuite(raginei_template.MyTest))
  
  return tests

if __name__ == '__main__':
  main()

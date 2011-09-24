#!/usr/local/bin/python2.6
##!/usr/bin/python
import sys, os
sys.path.insert(0, os.path.normpath(os.path.realpath(__file__) + '/../../'))
sys.path.insert(0, os.path.normpath(os.path.realpath(__file__) + '/../../packages'))

from logic import constants as constants_module

import ConfigParser
config = ConfigParser.ConfigParser()
config.read('../site.cfg')
constants = dict(constants_module.dictionary.items() + config.items('general'))
for constant in ('debug', 'port', 'page_size', 'single_user_site', 'ioloop'):
  constants[constant] = int(constants[constant])

from autumn.db.connection import Database, DBConn
from autumn.db.connection import autumn_db
from autumn.db.query import Query
autumn_db.conn.connect('mysql', host=constants['mysql_host'], user=constants['mysql_user'], passwd=constants['mysql_password'], db=constants['mysql_database'])
from models import base as models

import datetime

def fixstuff():
  options = { 'username':'mime', 'name like':'untitled' + '-%' }
  highest_existing_name = models.content.get(**options).order_by('name', 'DESC')[0]
  print highest_existing_name.name

#fixstuff()
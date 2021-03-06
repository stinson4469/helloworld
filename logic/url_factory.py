import cgi
import os.path
import re
import urllib
import urlparse

import tornado.escape

def load_basic_parameters(handler, prefix="", url=""):
  uri = url if url else handler.request.uri
  # Hmmm, some servers send UTF-8 percent encoded and some don't...
  uri = tornado.escape.url_unescape(uri)
  # XXX WTF?? it's double-escaped??? something's weird here.  FIX
  uri = tornado.escape.url_unescape(uri)

  if handler.prefix and uri.find(handler.prefix) == 0:
    uri = uri[len(handler.prefix):]

  if prefix and uri.find(prefix) == 0:
    uri = uri[len(prefix):]

  implied_profile = None
  hostname_user = None
  if handler.models:
    hostname_user = handler.get_user_by_hostname()

  if handler.constants['single_user_site'] and handler.models:
    implied_profile = handler.get_author_username()
  elif hostname_user:
    implied_profile = hostname_user.username
  elif handler.current_user is not None:
    implied_profile = handler.current_user.get('username', None)

  parsed_url = urlparse.urlparse(uri)
  uri_array = parsed_url.path.split("/")
  uri_array.pop(0)
  uri_array = [sanitize_form_value(x) for x in uri_array]

  uri_dict = {
    'uri': uri,
    'profile': None,
    'section': None,
    'album': None,
    'name': None,
    'modifier': None,
    'private': None,
  }

  if not hostname_user and (len(uri_array) == 0 or uri_array[0] == ""):
    uri_dict['profile'] = (implied_profile or
        (handler.models.users.get(1).username if handler.models else ''))
    uri_dict['section'] = 'main'
    uri_dict['name']    = 'main'
    return uri_dict

  if uri_array[0] == 'private':
    uri_dict['private'] = '/'.join(uri_array[1:])
    return uri_dict

  if uri_array[0] in handler.constants['reserved_names']:
    uri_array.insert(0, implied_profile)
  elif ((handler.constants['single_user_site'] or hostname_user) and
      uri_array[0] != implied_profile):
    uri_array.insert(0, implied_profile)

  uri_dict['profile'] = uri_array[0]

  if (len(uri_array) > 2 and uri_array[2] != "" and
      uri_array[-2] == "page" and uri_array[-1] != ""):
    uri_dict["modifier"] = uri_array[-1]
    uri_array.pop()
    uri_array.pop()

  if len(uri_array) == 1:
    uri_array.append('home')
  elif uri_array[1] == "":
    uri_array[1] = 'home'

  if len(uri_array) > 2 and uri_array[2] != "":
    uri_dict["section"] = uri_array[1]
    uri_dict["name"] = uri_array[-1]
  else:
    uri_dict["section"] = 'main'
    uri_dict["name"] = uri_array[1]

  uri_dict["name"] = reverse_href(urllib.unquote_plus(uri_dict["name"]))

  return uri_dict

def sanitize_form_value(value):
  main_regex = re.compile("<|>|&#|script\:", re.IGNORECASE)
  value = main_regex.sub("_", value)
  # prevent something that is already &amp; from becoming &amp;amp;
  value = re.sub("&amp;", "&", value)
  value = re.sub("&", "&amp;", value)

  if value.find('?') != -1:
    value = value[:value.find('?')]  # get rid of arguments

  return value;

def href(url):
  return url.replace(" ", "+")

def reverse_href(url):
  return url.replace("+", " ")

def add_base_uris(handler, view):
  return re.compile(r'(["\'])(static/resource)', re.M | re.U).sub(
      r'\1' + handler.base_uri + r'\2', view)

# xxx, this is now done in wysiwyg
def linkify_tags(handler, username, text):
  return re.compile(r'#(\w+)(?![^<&]*([>;]))', re.M | re.U).sub(
      r' <a href="' + handler.nav_url(username=username, section='search') +
      r'?q=%23\1" rel="tag">#\1</a>', text)

def clean_name(name):
  return re.compile(r'[\W]+', re.M | re.U).sub('', name.replace(
      " ", "_").replace("-", "_")).replace("_", "-")[:255]

def check_legit_filename(full_path):
  leafname = os.path.basename(full_path)
  # _current_theme is used internally for themes
  if leafname in ('crossdomain.xml', 'clientaccesspolicy.xml', '.htaccess',
      '.htpasswd', '_current_theme'):
    raise tornado.web.HTTPError(400, "i call shenanigans")

def clean_filename(name):
  if name == '..' or name == '.':
    return ''

  check_legit_filename(name)

  if name.startswith('/'):  # get rid of leading /
    name = name[1:]
  return re.compile(r'[\\\/]\.\.|\.\.[\\\/]', re.M | re.U).sub('', name)

def content_url(handler, item, host=False, **arguments):
  url = ""

  if host:
    url += handler.request.protocol + "://" + handler.request.host

  if not handler.constants['http_hide_prefix']:
    url += handler.prefix

  if (not handler.constants['single_user_site'] and not handler.hostname_user
      and item.name != 'main'):
    url += '/' + item.username

  if item.section != 'main':
    url += '/' + item.section

  if item.album and item.album != 'main':
    url += '/' + item.album

  if item.name != 'home' and item.name != 'main':
    url += '/' + item.name
  elif item.name == 'home' and handler.hostname_user:
    url += '/'

  if arguments:
    for arg in arguments:
      arguments[arg] = arguments[arg].encode('utf-8')
    url += '?' + urllib.urlencode(arguments)

  return href(url)

def nav_url(handler, host=False, username="", section="", album="", name="",
    page=None, **arguments):
  url = ""

  if host:
    url += handler.request.protocol + "://" + handler.request.host

  if not handler.constants['http_hide_prefix']:
    url += handler.prefix

  if (not handler.constants['single_user_site'] and not handler.hostname_user
      and username):
    url += '/' + username

  if section:
    url += '/' + section
    if album:
      url += '/' + album
      if name:
        url += '/' + name

  if page:
    url += '/page/' + str(page)

  args = ""
  if arguments:
    for arg in arguments:
      arguments[arg] = arguments[arg].encode('utf-8')
    args = '?' + urllib.urlencode(arguments)

  return (href(url) + args) or "/"

def resource_directory(handler, section="", album=""):
  path = handler.application.settings["resource_path"]

  path = os.path.join(path, handler.get_author_username())

  if section:
    path += '/' + section

  if album:
    path += '/' + album

  return path

def resource_url(handler, section="", album="", resource="", filename="",
    host=False):
  if filename:
    return handler.application.settings["resource_url"] \
         + filename.replace(handler.application.settings["resource_path"], '')

  path = ""
  if host:
    path += handler.request.protocol + "://" + handler.request.host
    if not handler.constants['http_hide_prefix']:
      path += handler.prefix
    path += '/'

  path += handler.application.settings["resource_url"] + '/'

  path += handler.get_author_username()

  if section:
    path += '/' + section + '/'

  if album:
    path += album + '/'

  if resource:
    path += resource + '/'

  return path

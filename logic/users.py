import base64
import datetime
import os
import os.path
import re
import urllib
import urllib2
import urlparse

from BeautifulSoup import BeautifulSoup
import Crypto.PublicKey.RSA as RSA
from Crypto.Util import number
import tornado.escape
import tornado.web

import magicsig
import pubsubhubbub_subscribe
import salmoning

def create_user(handler, username, email):
  user = handler.models.users()
  user.username = username
  user.name = username
  user.oauth = email
  user.superuser = False
  user.author = False

  key = RSA.generate(1024, os.urandom)
  n = base64.urlsafe_b64encode(number.long_to_bytes(key.n))
  e = base64.urlsafe_b64encode(number.long_to_bytes(key.e))
  d = base64.urlsafe_b64encode(number.long_to_bytes(key.d))
  user.magic_key = 'RSA.' + n + '.' + e
  user.private_key = d

  user.save()

  create_empty_content(handler, user.username, 'main', 'home', 'Hello, world.', template="feed", translate=True)
  create_empty_content(handler, user.username, 'main', 'photos', 'photos', template='album', translate=True)
  create_empty_content(handler, user.username, 'main', 'microblog', 'microblog', template='feed', translate=True)
  create_empty_content(handler, user.username, 'main', 'links', 'links', template='links', translate=True)
  create_empty_content(handler, user.username, 'main', 'about', 'about', view="I like turtles.", translate=True)
  create_empty_content(handler, user.username, 'main', 'comments', 'comments', translate=True, hidden=True)
  create_empty_content(handler, user.username, 'microblog', 'first', "first!", view="Hello, world.", translate=True)

  os.makedirs(os.path.join(handler.application.settings["private_path"], username))
  os.makedirs(os.path.join(os.path.join(handler.application.settings["resource_path"], username), 'themes'))

  return user

def create_empty_content(handler, username, section, name, title, template=None, view=None, translate=False, hidden=False):
  content = handler.models.content()
  content.username = username
  content.section  = section
  content.name     = name
  content.date_created = datetime.datetime.utcnow()
  content.date_updated = datetime.datetime.utcnow()
  content.title = handler.locale.translate(title) if translate else title
  content.template = template
  content.hidden = hidden
  content.view = handler.locale.translate(view) if translate else view
  content.save()

def get_lrdd_link(url):
  parsed_url = urlparse.urlparse(url)
  host_meta_url = parsed_url.scheme + '://' + parsed_url.hostname + '/.well-known/host-meta'
  #host_meta_url = 'http://localhost/statusnet2/.well-known/host-meta'
  host_meta_response = urllib2.urlopen(host_meta_url)
  host_meta_doc = BeautifulSoup(host_meta_response.read())
  lrdd_link = host_meta_doc.find('link', rel='lrdd')['template']

  return lrdd_link

def get_webfinger(lrdd, uri):
  webfinger_url = lrdd.replace('{uri}', urllib.quote_plus(uri))
  webfinger_response = urllib2.urlopen(webfinger_url)
  return BeautifulSoup(webfinger_response.read())

def sanitize(value):
  VALID_TAGS = ['video', 'audio', 'strong', 'em', 'i', 'b', 'u', 'a', 'h1', 'h2', 'h3', 'pre', 'img', 'p', 'ul', 'li', 'br']

  soup = BeautifulSoup(value)

  for tag in soup.findAll(True):
      if tag.name not in VALID_TAGS:
          tag.hidden = True

  return soup.renderContents()

def salmon_common(handler):
  user = handler.get_author_user()
  handler.display['feed'] = None
  handler.display["user"] = user
  handler.display["push_hub"] = handler.constants['push_hub']
  handler.display['utcnow'] = datetime.datetime.utcnow()
  handler.display["section"] = None
  handler.display['activity_object'] = ''
  handler.display['activity_extra'] = ''
  handler.display['id'] = str(datetime.datetime.utcnow()).replace(' ', ':')
  return user

def salmon_follow(handler, salmon_url, follow=True):
  user = salmon_common(handler)
  action = 'follow' if follow else 'unfollow'
  handler.display['title'] = action
  handler.display['atom_content'] = action
  handler.display['activity_object'] = ''
  handler.display['verb'] = 'http://activitystrea.ms/schema/1.0/' + action
  atom_html = handler.render_string("feed.html", **handler.display)
  salmon_send(handler, user, salmon_url, atom_html)

def salmon_favorite(handler, salmon_url, post_id, favorite=True):
  user = salmon_common(handler)
  action = 'favorite' if favorite else 'unfavorite'
  handler.display['title'] = action
  handler.display['atom_content'] = action
  handler.display['verb'] = 'http://activitystrea.ms/schema/1.0/' + action
  handler.display['activity_object'] = """
    <activity:object-type>http://activitystrea.ms/schema/1.0/note</activity:object-type>
    <id>%(post_id)s</id>
    <title></title>
    <content type="html"></content>
    <!--<link href="http://freelish.us/notice/19245388" rel="alternate" type="text/html" />-->
""" % { 'post_id': post_id }
  atom_html = handler.render_string("feed.html", **handler.display)
  salmon_send(handler, user, salmon_url, atom_html)

def salmon_reply(handler, user_remote, content, thread=None):
  user = salmon_common(handler)
  handler.display['id'] = handler.content_url(content)
  handler.display['title'] = content.title
  handler.display['atom_content'] = content.view
  action = 'comment' if content.section == 'comments' else 'post'
  handler.display['verb'] = 'http://activitystrea.ms/schema/1.0/' + action
  handler.display['activity_extra'] = """
  <activity:object-type>http://activitystrea.ms/schema/1.0/note</activity:object-type>
  <link href="%(content_url)s" rel="alternate" type="text/html" />
  <link href="%(profile_url)s" rel="ostatus:attention" />
  <link href="%(profile_url)s" rel="mentioned" />
""" % { 'content_url': handler.content_url(content, host=True), 'profile_url': user_remote.profile_url }
  thread = thread or content.thread
  if thread:
    handler.display['activity_extra'] += """<thr:in-reply-to href="%(content_url)s" ref="%(thread)s" xmlns:thr="http://purl.org/syndication/thread/1.0" />""" % { 'content_url': handler.content_url(content, host=True), 'thread': thread }
    handler.display['activity_extra'] += """<link rel="related" href="%(content_url)s"/>""" % { 'content_url': handler.content_url(content, host=True) }
  atom_html = handler.render_string("feed.html", **handler.display)
  salmon_send(handler, user, user_remote.salmon_url, atom_html)

class MockKeyRetriever(magicsig.KeyRetriever):
  def __init__(self, local_user):
    self.local_user = local_user
    self.signer_uri = None

  def LookupPublicKey(self, signer_uri=None):
    self.signer_uri = signer_uri
    return (str(self.local_user.magic_key + '.' + self.local_user.private_key))

def salmon_send(handler, user, salmon_url, text):
  salmonizer = salmoning.SalmonProtocol()
  salmonizer.key_retriever = MockKeyRetriever(local_user=user)
  env = salmonizer.SignSalmon(unicode(text, "utf8"), 'application/atom+xml', handler.nav_url(host=True, username=user.username))

  try:
    req = urllib2.Request(url=salmon_url,
                          data=env,
                          headers={ 'Content-Type': 'application/magic-envelope+xml' })
    
    urllib2.urlopen(req)
  except:
    pass

def get_remote_user_info(handler, user_url, profile):
  # get host-meta first
  lrdd_link = get_lrdd_link(user_url)
  salmon_url = ''
  magic_key = ''
  alias = ''

  if not lrdd_link:
    user_response = urllib2.urlopen(user_url)
    user_doc = BeautifulSoup(user_response.read())

    atom_url = user_doc.find('link', rel='alternate', type='application/atom+xml')
    rss_url = user_doc.find('link', rel='alternate', type='application/atom+xml')

    feed_url = atom_url or rss_url
  else:
    # get webfinger
    webfinger_doc = get_webfinger(lrdd_link, user_url)
    feed_url = webfinger_doc.find('link', rel='http://schemas.google.com/g/2010#updates-from')
    salmon_url = webfinger_doc.find('link', rel='salmon')
    if salmon_url:
      salmon_url = salmon_url['href']
    magic_key = webfinger_doc.find('link', rel='magic-public-key')
    if magic_key:
      magic_key = magic_key['href'].replace('data:application/magic-public-key,', '')
    alias = webfinger_doc.find('alias')
    if alias:
      alias = alias.string

  if not feed_url:
    raise tornado.web.HTTPError(400)

  feed_url = feed_url['href']

  if not feed_url.startswith('/') and not feed_url.startswith('http://'):
    base_url = user_doc.find('base')
    if base_url:
      base_url = base_url['href']
    else:
      base_url = ''
    feed_url = base_url + feed_url

  if not feed_url.startswith('http://'):
    parsed_url = urlparse.urlparse(user_url)
    feed_url = parsed_url.scheme + '://' + parsed_url.hostname + feed_url

  feed_response = urllib2.urlopen(feed_url)
  feed_doc = BeautifulSoup(feed_response.read())
  author = feed_doc.find('author')

  alias = author.find('uri').string  # alias or user_url
  user_remote = handler.models.users_remote.get(local_username=profile, profile_url=alias)[0]
  hub_url = feed_doc.find('link', rel='hub')

  if not user_remote:
    user_remote = handler.models.users_remote()

  user_remote.local_username = profile
  if author:
    user_remote.avatar = author.find('link', rel='avatar')['href']
    user_remote.username = author.find(re.compile('.+:preferredusername$')).string
    user_remote.name = author.find(re.compile('.+:displayname$')).string
  elif webfinger_doc:
    user_remote.avatar = feed_doc.find('logo').string
    user_remote.username = webfinger_doc.find('Property', type="http://apinamespace.org/atom/username").string
  user_remote.profile_url = alias
  user_remote.magic_key = magic_key
  user_remote.salmon_url = salmon_url
  user_remote.feed_url = feed_url
  if hub_url:
    user_remote.hub_url = hub_url['href']
  user_remote.save()

  try:
    if user_remote.hub_url:
      callback_url = handler.nav_url(host=True, username=profile, section='push')
      pubsubhubbub_subscribe.subscribe_topic(user_remote.hub_url, user_remote.feed_url, callback_url, verify="sync")
  except:
    import logging
    logging.error("couldn't subscribe on the hub!")

  return user_remote
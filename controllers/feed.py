import hashlib

import tornado.web

from base import BaseHandler
from logic import content_remote
from logic import url_factory

class FeedHandler(BaseHandler):
  def get(self):
    user = self.models.users.get(username=self.breadcrumbs["profile"])[0]

    if not user:
      raise tornado.web.HTTPError(404)

    self.display["user"] = user
    self.display["push_hub"] = self.constants['push_hub']

    section = self.get_argument('category', '')
    album_feed = self.get_argument('album_feed', '')
    comments_url = self.get_argument('comments', '')
    self.display["comments_url"] = comments_url
    self.display["thread_url"] = None

    if comments_url:
      content_url = url_factory.load_basic_parameters(self, url=comments_url)
      content = self.models.content.get(username=content_url["profile"],
          section=content_url["section"], name=content_url["name"])[0]

      comments = content_remote.get_comments(self, content)
      thread_url = ('tag:' + self.request.host + ',' +
          self.display["tag_date"] + ':' + self.content_url(content))
      self.display["thread_url"] = thread_url
      comments.sort(key=lambda x: x.date_created, reverse=True)
      self.display["feed"] = comments
    else:
      common_options = {}
      if not self.is_owner_viewing(self.breadcrumbs["profile"]):
        common_options['hidden'] = False

      content_options = { 'username': user.username,
                          'redirect': 0,
                          'forum': 0,
                          'section !=': 'comments', }
      if section:
        content_options['section'] = section
      if album_feed:
        content_options['album'] = album_feed

      content_options = dict(common_options.items() + content_options.items())
      feed = self.models.content.get(**content_options).order_by(
          'date_created', 'DESC')

      self.display["feed"] = [ self.ui["modules"].Content(content) \
          for content in feed[:100] if content.section != 'main' and \
          content.album != 'main' ]  # todo, this should move to query really

    self.display["section"] = section
    self.display["album_feed"] = album_feed

    self.display['sup_id'] = hashlib.md5(self.nav_url(host=True,
        username=user.username, section='feed')).hexdigest()[:10]

    self.set_header("Content-Type", "application/atom+xml")
    self.set_header("X-SUP-ID", "http://friendfeed.com/api/public-sup.json#" +
        self.display['sup_id'])
    self.fill_template("feed.html")

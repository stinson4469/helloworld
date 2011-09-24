import hashlib

from base import BaseHandler

import tornado.web

class FeedHandler(BaseHandler):
  def get(self):
    user = self.models.users.get(username=self.breadcrumbs["profile"])[0]

    if not user:
      raise tornado.web.HTTPError(404)

    self.display["user"] = user
    self.display["push_hub"] = self.constants['push_hub']

    section = self.get_argument('category', '')
    album = self.get_argument('album', '')

    common_options = {}
    if not self.is_owner_viewing(self.breadcrumbs["profile"]):
      common_options['hidden'] = False

    content_options = { 'username': user.username,
                        'redirect': 0, }
    if section:
      content_options['section'] = section
    if album:
      content_options['album'] = album

    content_options = dict(common_options.items() + content_options.items())
    feed = self.models.content.get(**content_options).order_by('date_created', 'DESC')

    self.display["feed"] = [ self.ui["modules"].Content(content) \
        for content in feed[:10] if content.section != 'main' and content.album != 'main' ]  # todo, this should move to query really
    self.display["section"] = section
    self.display["album"] = album

    self.display['sup_id'] = hashlib.md5(self.nav_url(host=True, username=user.username, section='feed')).hexdigest()[:10]

    self.set_header("Content-Type", "application/atom+xml")
    self.set_header("X-SUP-ID", "http://friendfeed.com/api/public-sup.json#" + self.display['sup_id'])
    self.fill_template("feed.html")
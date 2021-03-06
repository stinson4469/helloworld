import datetime
import hashlib
import re
import urllib

from BeautifulSoup import BeautifulSoup
import tornado.escape
import tornado.web

from base import BaseHandler
from logic import cache
from logic import content as content_logic
from logic import content_remote
from logic import loader
from logic import socialize
from logic import url_factory

class ViewHandler(BaseHandler):
  def head(self):
    # /profile/section/name
    content = self.models.content.get(username=self.breadcrumbs["profile"],
                                      section=self.breadcrumbs["section"],
                                      name=self.breadcrumbs["name"])[0]

    if not content:
      # not found: see if the url maybe exists, and wasn't properly redirected
      alternate = self.models.content.get(username=self.breadcrumbs["profile"],
                                          name=self.breadcrumbs["name"])[0]
      if alternate:
        self.redirect(self.content_url(alternate,
            referrer=self.breadcrumbs['uri']), permanent=True)
        return
      raise tornado.web.HTTPError(404)
    elif content.template:
      pass
    elif content.album == 'main':
      # /profile/section/album
      parent_content = self.models.content.get(
          username=self.breadcrumbs["profile"],
          section="main",
          name=self.breadcrumbs["section"])[0]

      if not parent_content or parent_content.template == "":
        raise tornado.web.HTTPError(404)

  def get(self):
    self.display["section_style"] = ""
    self.display["section_code"] = ""
    self.display["album_style"] = ""
    self.display["album_code"] = ""

    self.display["edit"] = self.get_argument('edit', False)

    is_special = False
    template = None
    # /profile/section/name
    content = self.models.content.get(username=self.breadcrumbs["profile"],
                                      section=self.breadcrumbs["section"],
                                      name=self.breadcrumbs["name"])[0]
    self.display["content"] = content
    # hmm, not sure this should go here, TODO fix ise now, clean up later

    if not content:
      # not found: see if the url maybe exists, and wasn't properly redirected
      alternate = self.models.content.get(username=self.breadcrumbs["profile"],
                                          name=self.breadcrumbs["name"])[0]
      if alternate:
        self.redirect(self.content_url(alternate,
            referrer=self.breadcrumbs['uri']), permanent=True)
        return
      raise tornado.web.HTTPError(404)
    elif content.template:
      template = content.template
      is_special = True
    elif content.album == 'main':
      # /profile/section/album
      parent_content = self.models.content.get(
          username=self.breadcrumbs["profile"],
          section="main",
          name=self.breadcrumbs["section"])[0]

      if not parent_content or parent_content.template == "":
        raise tornado.web.HTTPError(404)
      else:
        template = parent_content.template
        is_special = True

    content_owner = self.models.users.get(username=content.username)[0]
    is_owner_viewing = self.is_owner_viewing(content.username)
    self.display['content_owner'] = content_owner
    self.display['is_owner_viewing'] = is_owner_viewing

    if (content_owner.adult_content and self.get_cookie("adult_content") != "1"
        and not is_owner_viewing):
      self.fill_template("adult_content.html")
      return

    if content.redirect:
      if self.display["edit"]:
        self.display["refers_to"] = self.content_url(
            self.models.content.get(content.redirect))
      else:
        redirect = self.models.content.get(content.redirect)
        self.redirect(self.content_url(redirect,
            referrer=self.breadcrumbs['uri']), permanent=True)
        return

    if content.style and not re.search(r"<link|<style",
        content.style, re.I | re.M):
      content.style = '<style>\n' + content.style + '\n</style>'
    if content.code and not re.search(r"<script", content.code, re.I | re.M):
      content.code = '<script>\n' + content.code + '\n</script>'

    self.display["content_thumb"] = content_logic.get_thumbnail(self, content)
    self.display["is_store"] = template == 'store'
    self.display["is_events"] = template == 'events'

    # grab parent's styling, code
    self.display["section_template"] = None
    self.display["section_sort_type"] = None
    content_section = self.models.content.get(username=content.username,
                                              section='main',
                                              name=content.section)[0]
    if content.section != 'main':
      if content_section:
        if content_section.style and not re.search(r"<link|<style",
            content_section.style, re.I | re.M):
          content_section.style = ('<style>\n' +
              content_section.style + '\n</style>')
        if content_section.code and not re.search(r"<script",
            content_section.code, re.I | re.M):
          content_section.code = ('<script>\n' +
              content_section.code + '\n</script>')
        self.display["section_style"] = content_section.style
        self.display["section_code"] = content_section.code
        self.display["section_template"] = content_section.template
        self.display["section_sort_type"] = content_section.sort_type
        self.display["is_store"] = (self.display["is_store"] or
            content_section.template == 'store')
        self.display["is_events"] = (self.display["is_events"] or
            content_section.template == 'events')
    else:
      self.display["section_template"] = content.template
      self.display["section_sort_type"] = content.sort_type

    self.display["main_section_title"] = (content_section.title if
        content.section != 'main' else content.title)
    self.display["main_section_name"] = (content.section if
        content.section != 'main' else content.name)

    content_album = self.models.content.get(username=content.username,
                                            section=content.section,
                                            album='main',
                                            name=content.album)[0]
    if content.album:
      self.display["main_album_title"] = (content_album.title if
          content.album != 'main' else content.title)
      self.display["main_album_name"] = (content.album if
          content.album != 'main' else content.name)
    else:
      self.display["main_album_title"] = None

    if content.album and content.album != 'main':
      if content_album:
        if content_album.style and not re.search(r"<link|<style",
            content_album.style, re.I | re.M):
          content_album.style = ('<style>\n' +
              content_album.style + '\n</style>')
        if content_album.code and not re.search(r"<script",
            content_album.code, re.I | re.M):
          content_album.code = ('<script>\n' +
              content_album.code + '\n</script>')
        self.display["album_style"] = content_album.style
        self.display["album_code"] = content_album.code
        if content_album.template:
          self.display["section_template"] = content_album.template
        if content_album.sort_type:
          self.display["section_sort_type"] = content_album.sort_type
        self.display["is_store"] = (self.display["is_store"] or
            content_album.template == 'store')
        self.display["is_events"] = (self.display["is_events"] or
            content_album.template == 'events')

    # figure out breadcrumbs, grab neighbors
    if is_special:
      if self.breadcrumbs["section"] == 'main':
        content_options = { 'username': content.username,
                            'section': content.name,
                            'name': None, }
      else:
        content_options = { 'username': content.username,
                            'section': content.name,
                            'name': self.breadcrumbs["name"], }
    elif content.album:
      content_options = { 'username': content.username,
                          'section': content.section,
                          'name': content.album, }
    else:
      content_options = { 'username': content.username,
                          'section': content.section,
                          'name': None, }

    if not content.hidden:
      collection, common_options = content_logic.get_collection(
          self, profile=content_options['username'],
          section=content_options['section'],
          name=content_options['name'])

      index = -1
      for i, p in enumerate(collection):
        if p.id == content.id:
          index = i
          break

    if not content.hidden and len(collection):
      if self.display["section_sort_type"] == "":
        self.display["start"] = collection[len(collection) - 1]
        self.display["previous"] = (collection[index + 1] if
            index + 1 < len(collection) else None)
        self.display["next"] = (collection[index - 1] if
            index - 1 >= 0 else None)
        self.display["last"] = collection[0]
      else:
        self.display["start"] = collection[0]
        self.display["previous"] = (collection[index - 1] if
            index - 1 >= 0 else None)
        self.display["next"] = (collection[index + 1] if
            index + 1 < len(collection) else None)
        self.display["last"] = collection[len(collection) - 1]
    else:
      self.display["start"] = None

    if is_special:
      if self.breadcrumbs["section"] == 'main':
        self.display["top_url"] = self.nav_url(username=content.username,
            section=content.name)
      else:
        self.display["top_url"] = self.nav_url(username=content.username,
            section=content.name, name=self.breadcrumbs["name"])
    else:
      if self.display["section_template"] in ('first', 'latest'):
        self.display["top_url"] = self.nav_url(username=content.username,
            section=content.section, name=content.album, mode='archive')
      else:
        self.display["top_url"] = self.nav_url(username=content.username,
            section=content.section, name=content.album)


    self.display['has_code'] = (content.code != "" or re.search(r"<script",
        content.view, re.I | re.M) or self.display["section_code"] or
        self.display["album_code"])
    if self.display["edit"] and self.display['has_code']:
      content.original_code = content.code
      content.code = self.code_workaround(content.code)
      content.view = self.code_workaround(content.view)
      if content_section:
        content_section.code = self.code_workaround(content_section.code)
      if content_album:
        content_album.code = self.code_workaround(content_album.code)

    # increase view count (if it's not the owner looking at it)
    #if not is_owner_viewing:
    #  content.count = content.count + 1
    #  content.save()

    is_robot = content_logic.is_viewed_by_robot(self)
    if is_robot:  # human views are handled by the stats image
      content.count_robot = content.count_robot + 1
      content.save()

    if is_owner_viewing:
      # otherwise, when restarting browser, it shows old data and
      # freaks you out!
      self.prevent_caching()

    if is_special:
      self.display["individual_content"] = False
      self.display["content"] = content
      self.display["template"] = template
      rendered_content = self.ui["modules"][template.capitalize()]()
    else:
      try:
        content = self.ui["modules"].Content(content, simple=False,
            template_type=self.display["section_template"])
      except tornado.web.HTTPError as ex:
        if ex.status_code == 401:
          # we're logging in
          return
        else:
          # re-raise
          raise ex

      self.display['content'] = content

      if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
        self.prevent_caching()
        self.write(self.ui["modules"].ContentView(content))
        return
      else:
        rendered_content = self.fill_template("view.html")

    if not self.current_user:
      cache.add(self, content, rendered_content)
      
  def post(self):
    if not self.authenticate(author=True):
      return

    content_url = url_factory.load_basic_parameters(self)
    content = self.models.content()

    if (not self.constants['single_user_site'] and
        content_url["profile"] != self.current_user["username"]):
      raise tornado.web.HTTPError(400, "i call shenanigans")

    self.save_content(content, content_url, new=True)

    if content.album:
      cache.remove(self, self.nav_url(username=content.username,
          section=content.section, name=content.album))
    cache.remove(self, self.nav_url(username=content.username,
        section=content.section))

    if not content.hidden:
      socialize.socialize(self, content)
      self.sup_ping(content)

    self.set_header('Location', self.content_url(content))
    content.restricted = False

    content = self.ui["modules"].Content(content)

    self.write(self.ui["modules"].ContentView([content]))
    self.set_status(201)

  def sup_ping(self, content):
    try:
      feed_url = self.nav_url(host=True, username=content.username,
          section='feed')
      sup_id = hashlib.md5(feed_url).hexdigest()[:10]
      args = urllib.urlencode({
        "url": feed_url,
        "supid": sup_id,
      })
      response = urllib2.urlopen("http://friendfeed.com/api/public-sup-ping?" +
          args)
    except:
      pass

  def put(self):
    if not self.authenticate(author=True):
      return

    content_url = url_factory.load_basic_parameters(self)
    content = self.models.content.get(username=content_url["profile"],
        section=content_url["section"], name=content_url["name"])[0]

    if not content:
      raise tornado.web.HTTPError(404)

    if (not self.constants['single_user_site'] and
        content.username != self.current_user["username"]):
      raise tornado.web.HTTPError(400, "i call shenanigans")

    old_section = content.section
    old_album   = content.album
    old_name    = content.name
    old_hidden  = content.hidden

    # remove old cached content
    if content.album:
      cache.remove(self, self.nav_url(username=content.username,
          section=content.section, name=content.album))
    cache.remove(self, self.nav_url(username=content.username,
        section=content.section))
    cache.remove(self, self.content_url(content))

    section = (self.get_argument('section') if
        self.get_argument('section') else content_url["section"])
    name = (self.get_argument('name') if
        self.get_argument('name', "") else content_url["name"])
    hidden = int(self.get_argument('hidden', 0))

    if content.section == 'main' and old_hidden != hidden:
      collection = self.models.content.get(username=content.username,
                                           section=old_name)[:]
      for item in collection:
        item.hidden = hidden
        item.save()

    if content.album == 'main' and old_hidden != hidden:
      collection = self.models.content.get(username=content.username,
                                           section=old_section,
                                           album=old_name)[:]
      for item in collection:
        item.hidden = hidden
        item.save()

    did_redirect = False
    if content.section == 'main' and old_name != name:
      did_redirect = True
      new_section = content_logic.rename_section(self, old_name, name,
          content.title)

    if content.album == 'main' and old_name != name:
      did_redirect = True
      new_album = content_logic.rename_album(self, content.section, old_name,
          name, content.title)     

    try:
      self.save_content(content, content_url, new=False)
    except tornado.web.HTTPError as ex:
      if ex.status_code == 400:
        # dup
        return
      else:
        # re-raise
        raise ex

    # remove cached in possible new album and new sections
    if content.album:
      cache.remove(self, self.nav_url(username=content.username,
          section=content.section, name=content.album))
    cache.remove(self, self.nav_url(username=content.username,
        section=content.section))

    if content.album == 'main' and old_section != content.section:
      album_name = new_album if did_redirect else old_name
      album_items = self.models.content.get(username=content.username,
                                            album=album_name)[:]
      for item in album_items:
        item.section = (album_name if content.section == 'main'
            else content.section)
        if content.section == 'main':
          item.album = ""
        item.save()

    if content.name != old_name and not did_redirect:
      content_logic.create_redirect(self, content, old_section, old_name)

    if content.name != old_name or content.section != old_section:
      self.set_header('Location', self.content_url(content))

    if not content.hidden:
      socialize.socialize(self, content)

    self.set_status(204)

  def delete(self):
    if not self.authenticate(author=True):
      return

    content_url = url_factory.load_basic_parameters(self)
    content = self.models.content.get(username=content_url["profile"],
        section=content_url["section"], name=content_url["name"])[0]

    if not content:
      raise tornado.web.HTTPError(404)

    if content.name == 'about':  # not allowed to delete
      raise tornado.web.HTTPError(400)

    if (not self.constants['single_user_site'] and
        content.username != self.current_user["username"]):
      raise tornado.web.HTTPError(400, "i call shenanigans")

    if content.name == 'home' or content.name == 'main':
      raise tornado.web.HTTPError(400, "i call shenanigans")

    collection = []
    if content.section == 'main':
      collection = self.models.content.get(username=content.username,
                                              section=content.name)[:]
    elif content.album == 'main':
      collection = self.models.content.get(username=content.username,
                                           album=content.name)[:]

    for item in collection:
      item.delete()

    content.delete()

    self.set_status(204)

  def save_content(self, content, content_url, new):
    # things not to be changed by the user
    content.username = self.get_author_username()

    # must be filled in
    content.style   = self.get_argument('style', "")
    content.code    = self.get_argument('code', "")
    content.view    = self.get_argument('view', "")

    section_template = self.get_argument('section_template', "")

    # linkify
    soup = BeautifulSoup(content.view)
    for text in soup.findAll(text=True):
      if text.parent.name not in ('a', 'script', 'style'):
        text.replaceWith(url_factory.linkify_tags(self, content.username,
            tornado.escape.linkify(tornado.escape.xhtml_unescape(text))))
    content.view = soup.renderContents()

    template = self.get_argument('template', "")

    if template:
      parent_template = template
    elif new or content.section == 'main':
      parent_template = "feed"
    else:
      parent_template = self.models.content.get(username=content.username,
          section='main',
          name=content.section)[0].template

    section = (self.get_argument('section') if
        self.get_argument('section') else content_url["section"])
    content.section = (content_logic.create_section(self, content.username,
        section, parent_template))

    # secondary things to be changed by user, filled in by default
    current_datetime = datetime.datetime.utcnow()
    if self.request.method == "POST":
      content.date_created = current_datetime
    content.date_updated = current_datetime

    if content.section != 'main':
      album = self.get_argument('album', "")
      album_template = template
      if not new and content.album:
        original_album = self.models.content.get(username=content.username,
                                                 album='main',
                                                 name=content.album)[0]
        if original_album:
          album_template = original_album.template
      content.album    = content_logic.create_album(self, content.username,
          content.section, album, album_template)

    title = self.get_argument('title', "")
    thumb = self.get_argument('thumb', "")
    name = (self.get_argument('name') if
        self.get_argument('name', "") else content_url["name"])

    content.name = content_logic.get_unique_name(self, content, name, title)
    content.title        = title
    content.thumb        = thumb
    if (content.section == 'main' or content.album == 'main' or
        template not in ('album', 'events', 'feed', 'forum',
        'slideshow', 'store')):
      content.template   = template
    else:
      content.template   = ''
    content.sort_type    = self.get_argument('sort_type', "")
    content.price        = float(self.get_argument('price', 0))
    content.thread       = self.get_argument('thread', '')
    date_start           = self.get_argument('date_start', None)
    date_end             = self.get_argument('date_end', None)
    content.date_start   = (datetime.datetime.fromtimestamp(int(date_start)) if
        date_start is not None and date_start != 'NaN' and date_start != '' else None)
    content.date_end     = (datetime.datetime.fromtimestamp(int(date_end)) if
        date_end is not None and date_end != 'NaN' and date_end != '' else None)
    date_repeats = self.get_argument('date_repeats', 0)
    content.date_repeats = int(date_repeats) if date_repeats != '' else 0
    hidden = self.get_argument('hidden', 0)
    content.hidden       = int(hidden) if hidden != '' else 0

    content.save()

  def code_workaround(self, text):
    text = text.replace("<script", '<style name="HWSCRIPTWORKAROUND"')
    text = text.replace("</script>", "</style><!--HWSCRIPTWORKAROUND-->")

    return text

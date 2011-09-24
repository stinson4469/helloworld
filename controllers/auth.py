import json
import tornado.auth
import tornado.escape
import tornado.web
import urllib
import urllib2

from base import BaseHandler

# BrowserId: https://browserid.org/developers
# or OAUTH
class AuthHandler(BaseHandler, tornado.auth.GoogleMixin):
  def post(self):
    assertion = self.get_argument('assertion')
    audience = self.request.host
    try:
      browserid = urllib2.urlopen("https://browserid.org/verify",
                                  "assertion=%(assertion)s&audience=%(audience)s"
                                  % { 'assertion': assertion, 'audience': audience })
      response = json.loads(browserid.read())
    except:
      raise tornado.web.HTTPError(500, "BrowserId auth failed")

    if response['status'] == 'okay':
      self.set_secure_cookie("user", tornado.escape.json_encode(response))
    else:
      raise tornado.web.HTTPError(500, "BrowserId auth failed")

  def get_sync_authenticated_user(self, callback):
    """Fetches the authenticated user data upon redirect.

    This method should be called by the handler that receives the
    redirect from the authenticate_redirect() or authorize_redirect()
    methods."""
    
    # Verify the OpenID response via direct request to the OP
    args = dict((k, v[-1]) for k, v in self.request.arguments.iteritems())
    args["openid.mode"] = u"check_authentication"
    import httplib
    import urlparse
    url = urlparse.urlparse(self._OPENID_ENDPOINT)
    conn = httplib.HTTPSConnection(url.netloc)
    conn.request("GET", url.path + '?' + urllib.urlencode(args))
    class Response:
      def __init__(self, response):
        self.error = False
        self.body = response.read()
    response = Response(conn.getresponse())
    conn.close()
    self._on_authentication_verified(callback, response)

  #@tornado.web.asynchronous
  def get(self):
    if "User-Agent" in self.request.headers and self.request.headers["User-Agent"].find('MSIE') == -1:    # XXX UGH
      self.redirect(self.nav_url())
      return

    if self.get_argument("openid.mode", None):
      #self.get_authenticated_user(self.async_callback(self._on_auth))
      self.get_sync_authenticated_user(self.async_callback(self._on_auth))
      return
    self.authenticate_redirect()
  
  def _on_auth(self, user):
    if not user:
      raise tornado.web.HTTPError(500, "Google auth failed")
    self.set_secure_cookie("user", tornado.escape.json_encode(user))
    self.redirect(self.get_argument("next"))

class AuthLogoutHandler(tornado.web.RequestHandler):
  def get(self):
    self.clear_cookie("user")
    self.redirect(self.get_argument("next"))
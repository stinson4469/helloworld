import json
import os
import os.path
import shutil

import tornado.web

from base import BaseHandler
from logic import media
from logic import url_factory

class UploadHandler(BaseHandler):
  def get(self):
    if not self.authenticate(author=True):
      return

    self.get_common_parameters()

    self.prevent_caching()
    if not os.path.exists(self.tmp_path):
      self.set_status(404)

  def post(self):
    safe_user = False
    if self.authenticate(author=True):
      safe_user = True

    self.get_common_parameters()

    if safe_user:
      if media.detect_media_type(self.base_leafname) not in ('video',
          'image', 'audio', 'web', 'zip'):
        raise tornado.web.HTTPError(400, "i call shenanigans")
    else:
      if media.detect_media_type(self.base_leafname) != 'image':
        raise tornado.web.HTTPError(400, "i call shenanigans")

    if self.get_argument('canvasImage', None):
      uploaded_file = self.get_argument('canvasImage')
    else:
      uploaded_file = self.request.files['file'][0]
    overwrite = True if self.get_argument('overwrite', False) else False

    if safe_user:
      self.media_section = url_factory.clean_filename(
          self.get_argument('section'))
      if self.media_section.startswith(url_factory.resource_url(self)):
        self.media_section = self.media_section[len(
            url_factory.resource_url(self)) + 1:]
      self.parent_directory = url_factory.resource_directory(self,
          self.media_section)
      self.parent_url = url_factory.resource_url(self, self.media_section)

      if self.media_section == 'themes':
        test_zip_path_name = os.path.join(self.parent_directory,
            self.base_leafname)
        split_path = os.path.splitext(test_zip_path_name)
        if os.path.exists(test_zip_path_name):
          os.remove(test_zip_path_name)
        if os.path.exists(split_path[0]) and os.path.isdir(split_path[0]):
          shutil.rmtree(split_path[0])
    else:
      self.parent_directory = os.path.join(
          self.application.settings["resource_path"], 'remote')
      self.parent_url = os.path.join(
          self.application.settings["resource_url"], 'remote')
    self.full_path = os.path.join(self.parent_directory, self.base_leafname)
    if not overwrite:
      self.full_path = media.get_unique_name(self.full_path)

    if not os.path.isdir(self.parent_directory):
      os.makedirs(self.parent_directory)

    if self.chunked_upload and safe_user:
      f = open(self.tmp_path, 'w')
      f.write(uploaded_file['body'])
      f.close()

      total_chunks_uploaded = 0
      for f in os.listdir(self.tmp_dir):
        if f.startswith(self.base_leafname):
          total_chunks_uploaded += 1

      if total_chunks_uploaded == max(self.total_size / self.chunk_size, 1):
        final_file = open(self.full_path, 'w')
        for f in os.listdir(self.tmp_dir):
          if f.startswith(self.base_leafname):
            chunk_path = os.path.join(self.tmp_dir, f)
            chunk_file = open(chunk_path, 'r')
            final_file.write(chunk_file.read())
            chunk_file.close()
            os.unlink(chunk_path)
        final_file.close()

        original_size_url, url, thumb_url = media.save_locally(
            self.parent_url, self.full_path, None, skip_write=True,
            overwrite=overwrite)
      else:
        return
    else:
      original_size_url, url, thumb_url = media.save_locally(
          self.parent_url, self.full_path, uploaded_file['body'],
          disallow_zip=(not safe_user), overwrite=overwrite)

    media_html = media.generate_full_html(self, url, original_size_url)
    self.set_header("Content-Type", "text/plain; charset=UTF-8")
    self.write(json.dumps({ 'original_size_url': original_size_url, \
                            'url': url, \
                            'thumb_url': thumb_url, \
                            'html': media_html, }))

  def get_common_parameters(self):
    self.chunked_upload = True
    if not self.get_argument('resumableChunkSize', None):
      if self.get_argument('canvasName', None):
        self.base_leafname = self.get_argument('canvasName')
      else:
        self.base_leafname = self.request.files['file'][0]['filename']
      self.chunked_upload = False
      return

    if not self.authenticate(author=True):
      raise tornado.web.HTTPError(400, "i call shenanigans")

    self.chunk_number = url_factory.clean_filename(
        self.get_argument('resumableChunkNumber'))
    self.chunk_size = int(self.get_argument('resumableChunkSize'))
    self.total_size = int(self.get_argument('resumableTotalSize'))
    self.identifier = self.get_argument('resumableIdentifier')
    self.filename = url_factory.clean_filename(
        self.get_argument('resumableFilename'))

    self.base_leafname = os.path.basename(self.filename)
    self.leafname = self.base_leafname + '_' + self.chunk_number.zfill(4)
    self.private_path = os.path.join(
        self.application.settings["private_path"], self.get_author_username())
    self.tmp_dir = os.path.join(self.private_path, 'tmp')
    self.tmp_path = os.path.join(self.tmp_dir, self.leafname)

    if not os.path.isdir(self.tmp_dir):
      os.makedirs(self.tmp_dir)

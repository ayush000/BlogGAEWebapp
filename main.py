#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import webapp2
import jinja2
import time
from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(autoescape=True, extensions=['jinja2.ext.autoescape'],
                               loader=jinja2.FileSystemLoader(template_dir))


# css_dir=os.path.join(os.path.dirname(__file__), "stylesheets")


class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))


class MainHandler(Handler):
    def render_mainpg(self):
        posts = db.GqlQuery('SELECT * FROM Post ORDER BY created DESC LIMIT 10')
        self.render("main.html", posts=posts)

    def get(self):
        self.render_mainpg()


class Post(db.Model):
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    date = db.DateProperty(auto_now_add=True)

class User(db.Model):
    pass

class NewPostHandler(Handler):
    def get(self):
        self.render("newpost.html")

    def post(self, ):
        error = "subject and content, please!"
        subject = self.request.get("subject")
        content = self.request.get("content")
        if content and subject:
            # content=content.replace('\n','<br>')
            p = Post(content=content, subject=subject)
            p.put()
            post_path = p.key().id()
            time.sleep(0.1)
            self.redirect('/{}'.format(post_path))
            # self.response.write(url_append)
        else:
            self.render('newpost.html', subject=subject, content=content, error=error)


class PostHandler(Handler):
    def get(self):
        post_path = self.request.path[1:]
        # self.response.out.write(post_path)
        post = Post.get_by_id(int(post_path))
        if not post:
            self.abort(404)
            return
        posts = []
        posts.append(post)
        self.render('main.html', posts=posts)


class SignupHandler(Handler):
    def get(self):
        self.render('signup.html')


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/newpost', NewPostHandler),
    (r'/\d+', PostHandler),
    ('/signup',SignupHandler)
], debug=True)

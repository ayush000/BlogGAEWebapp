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
import logging
import os
import time
import re
import hmac
import json

import webapp2
import jinja2
from google.appengine.ext import db
from google.appengine.api import memcache

SECRET = "hunter2"


def hash_str(s):
    return hmac.new(SECRET, s).hexdigest()


def make_secure_val(s):
    return "{}|{}".format(s, hash_str(s))


def check_secure_val(h):
    val = h.split('|')[0]
    if make_secure_val(val) == h:
        return val


def getApi(post):
    out = {}
    out['subject'] = post.subject
    out['content'] = post.content
    out['created'] = post.created.strftime("%c")
    return out


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(autoescape=True, extensions=['jinja2.ext.autoescape'],
                               loader=jinja2.FileSystemLoader(template_dir))

q_time=0
def query_posts(update=False):

    global q_time
    key='top'
    posts=memcache.get(key)
    if posts is None or update:
        logging.error('DB QUERY')
        posts = db.GqlQuery('SELECT * FROM Post ORDER BY created DESC LIMIT 10')
        memcache.set(key,posts)
        posts = list(posts)
        q_time=time.time()

    return posts


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
        posts = query_posts()
        self.render("main.html", posts=posts)
        time_diff=time.time()-q_time
        self.write('Queried {} seconds ago'.format(time_diff))

    def get(self):
        self.render_mainpg()


class Post(db.Model):
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    date = db.DateProperty(auto_now_add=True)


class User(db.Model):
    user_name = db.StringProperty(required=True)
    user_password = db.StringProperty(required=True)
    user_email = db.StringProperty()


class NewPostHandler(Handler):
    def get(self):
        self.render("newpost.html")

    def post(self):
        error = "subject and content, please!"
        subject = self.request.get("subject")
        content = self.request.get("content")
        if content and subject:
            # content=content.replace('\n','<br>')
            p = Post(content=content, subject=subject)
            p.put()
            query_posts(update=True)
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
        time_diff=time.time()-q_time
        self.write('Queried {} seconds ago'.format(time_diff))
        self.render('main.html', posts=posts)


class SignupHandler(Handler):
    def get(self):
        self.render('signup.html')

    def post(self):
        user_error = ""
        password_error = ""
        verify_error = ""
        email_error = ""
        has_error = False

        def match_user(user):
            USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
            return USER_RE.match(user)

        def match_password(password):
            PASSWORD_RE = re.compile(r"^.{3,20}$")
            return PASSWORD_RE.match(password)

        def match_email(email):
            EMAIL_RE = re.compile(r"^[\S]+@[\S]+\.[\S]+$")
            return EMAIL_RE.match(email)

        user_name = self.request.get('username')
        user_password = self.request.get('password')
        user_verify = self.request.get('verify')
        user_email = self.request.get('email')
        user_list = db.GqlQuery('SELECT * FROM User')
        if not match_user(user_name):
            has_error = True
            user_error = "Enter a valid username"
        else:
            for user in user_list:
                if user_name == user.user_name:
                    has_error = True
                    user_error = "User already exists"

        if not match_password(user_password):
            has_error = True
            password_error = "Enter a valid pasword"
        elif not user_password == user_verify:
            has_error = True
            verify_error = "Passwords don't match"
        if user_email:
            if not match_email(user_email):
                has_error = True
                email_error = "Enter a valid email"
        if has_error:
            self.render("signup.html", user_name=user_name, user_email=user_email, user_error=user_error,
                        password_error=password_error, verify_error=verify_error, email_error=email_error)
        else:
            hashed_password = make_secure_val(user_password)
            u = User(user_name=user_name, user_password=hashed_password, user_email=user_email)
            u.put()
            secure_id = make_secure_val(user_name)
            self.response.headers.add_header('Set-Cookie', 'user_id={}; Path=/'.format(secure_id))
            self.redirect('/welcome')


class WelcomeHandler(Handler):
    def get(self):
        user = self.request.cookies.get('user_id')
        if user:
            user_name = check_secure_val(user)
            if user_name:
                self.write("welcome, {}".format(user_name))
            else:
                self.redirect('/signup')
        else:
            self.redirect('/signup')


class LoginHandler(Handler):
    def get(self):
        self.render('login.html')

    def post(self):
        user_name = self.request.get('username')
        user_password = self.request.get('password')
        hashed_password = make_secure_val(user_password)
        user_list = db.GqlQuery('SELECT * FROM User')
        for user in user_list:
            if user.user_name == user_name and user.user_password == hashed_password:
                secure_id = make_secure_val(user_name)
                self.response.headers.add_header('Set-Cookie', 'user_id={}; Path=/'.format(secure_id))
                self.redirect('/welcome')
            else:
                self.render('login.html', user_name=user_name, login_error="Invalid login details")


class LogoutHandler(Handler):
    def get(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')
        self.redirect('/signup')


class JsonHandler1(Handler):
    def get(self):
        posts = db.GqlQuery('SELECT * FROM Post')
        jsonOut = []
        self.response.headers['Content-Type'] = 'application/json'

        for post in posts:
            jsonOut.append(getApi(post))
        jsonOut = json.dumps(jsonOut)

        self.write(jsonOut)


class JsonPostHandler(Handler):
    def get(self):
        post_path = self.request.path[1:-5]
        # self.response.out.write(post_path)
        post = Post.get_by_id(int(post_path))
        if not post:
            self.abort(404)
            return
        self.response.headers['Content-Type'] = 'application/json'
        self.write(json.dumps(getApi(post)))
        # self.write(self.response.headers)


class FlushHandler(Handler):
    def get(self):
        memcache.flush_all()
        self.redirect('/')


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/newpost', NewPostHandler),
    (r'/\d+', PostHandler),
    ('/signup', SignupHandler),
    ('/welcome', WelcomeHandler),
    ('/login', LoginHandler),
    ('/logout', LogoutHandler),
    (r'/.json', JsonHandler1),
    (r'/\d+.json', JsonPostHandler),
    ('/flush',FlushHandler)
], debug=True)

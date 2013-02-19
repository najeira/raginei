# -*- coding: utf-8 -*-

from raginei.app import Application, render_text, route


@route('/')
def index():
  return render_text('Hello World!')


application = Application.instance()


if __name__ == '__main__':
  application.run()

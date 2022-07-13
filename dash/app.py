import os
from flask import Flask

import views

APP_ROOT = os.path.dirname(os.path.realpath(__file__))
class CustomFlask(Flask):
    jinja_options = Flask.jinja_options.copy()
    jinja_options.update(dict(
        block_start_string='(%',
        block_end_string='%)',
        variable_start_string='((',
        variable_end_string='))',
        comment_start_string='(#',
        comment_end_string='#)'))

app = CustomFlask(__name__)
app.config.from_object(__name__)
app.register_blueprint(views.blueprint)
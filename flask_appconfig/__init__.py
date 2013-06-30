#!/usr/bin/env python

import json
import os
from urlparse import urlparse


class AppConfig(object):
    def __init__(self, app=None, *args, **kwargs):
        if app:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app,
                 configfile=None, envvar=True, default_settings=True,
                 load_envvars='json', from_envvars_prefix=None):

        if from_envvars_prefix is None:
            from_envvars_prefix = app.name.upper() + '_'

        if default_settings is True:
            try:
                app.config.from_object(app.name + '.default_config')
            except ImportError:
                # ignore import errors if settings were autogenerated
                pass
        elif default_settings:
            app.config.from_object(default_settings)

        # load supplied configuration file
        if configfile:
            app.config.from_pyfile(configfile)

        # load configuration file from environment
        if envvar is True:
            envvar = app.name.upper() + '_CONFIG'

        if envvar and envvar in os.environ:
            app.config.from_envvar(envvar)

        # load environment variables
        if load_envvars:
            from_envvars(app.config, from_envvars_prefix,
                         as_json=('json' == load_envvars))

        # register extension
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['appconfig'] = self


class HerokuConfig(AppConfig):
    def init_app(self, app, *args, **kwargs):
        super(HerokuConfig, self).init_app(app, *args, **kwargs)

        var_map = {
            # SQL-Alchemy
            'DATABASE_URL': 'SQLALCHEMY_DATABASE_URI',

            # newer-style
            'HEROKU_POSTGRESQL_ORANGE_URL': 'SQLALCHEMY_DATABASE_URI',

            # Celery w/ RabbitMQ
            'BROKER_URL': 'RABBITMQ_URL',

            'REDISTOGO_URL': 'REDIS_URL',
            'MONGOLAB_URI': 'MONGO_URI',
            'MONGOHQ_URL': 'MONGO_URI',
            'CLOUDANT_URL': 'COUCHDB_URL',

            'MEMCACHIER_SERVERS': 'CACHE_MEMCACHED_SERVERS',
            'MEMCACHIER_USERNAME': 'CACHE_MEMCACHED_USERNAME',
            'MEMCACHIER_PASSWORD': 'CACHE_MEMCACHED_PASSWORD',
        }

        var_list = [
            # Sentry
            'SENTRY_DSN',

            # Exceptional
            'EXCEPTIONAL_API_KEY',

            # Flask-GoogleFed
            'GOOGLE_DOMAIN',

            # Mailgun
            'MAILGUN_API_KEY', 'MAILGUN_SMTP_LOGIN', 'MAILGUN_SMTP_PASSWORD',
            'MAILGUN_SMTP_PORT', 'MAILGUN_SMTP_SERVER',

            # SendGrid
            'SENDGRID_USERNAME', 'SENDGRID_PASSWORD'
        ]

        # import the relevant envvars
        self.from_envvars(app, var_list)
        self.from_envvars(app, var_map)

        # fix up configuration
        if 'MAILGUN_SMTP_SERVER' in app.config:
            app.config['SMTP_SERVER'] = app.config['MAILGUN_SMTP_SERVER']
            app.config['SMTP_PORT'] = app.config['MAILGUN_SMTP_PORT']
            app.config['SMTP_LOGIN'] = app.config['MAILGUN_SMTP_LOGIN']
            app.config['SMTP_PASSWORD'] = app.config['MAILGUN_SMTP_PASSWORD']
            app.config['SMTP_USE_TLS'] = True
        elif 'SENDGRID_USERNAME' in app.config:
            app.config['SMTP_SERVER'] = 'smtp.sendgrid.net'
            app.config['SMTP_PORT'] = 25
            app.config['SMTP_LOGIN'] = app.config['SENDGRID_USERNAME']
            app.config['SMTP_PASSWORD'] = app.config['SENDGRID_PASSWORD']
            app.config['SMTP_USE_TLS'] = True

        # convert to Flask-Mail specific configuration
        if 'MAILGUN_SMTP_SERVER' in app.config or\
           'SENDGRID_PASSWORD' in app.config:

            app.config['MAIL_SERVER'] = app.config['SMTP_SERVER']
            app.config['MAIL_PORT'] = app.config['SMTP_PORT']
            app.config['MAIL_USE_TLS'] = app.config['SMTP_USE_TLS']
            app.config['MAIL_USERNAME'] = app.config['SMTP_LOGIN']
            app.config['MAIL_PASSWORD'] = app.config['SMTP_PASSWORD']

        # for backwards compatiblity, redis:
        if 'REDIS_URL' in app.config:
            url = urlparse(app.config['REDIS_URL'])
            app.config['REDIS_HOST'] = url.hostname
            app.config['REDIS_PORT'] = url.port
            app.config['REDIS_PASSWORD'] = url.password
            # FIXME: missing db#?

        if 'MONGO_URI' in app.config:
            url = urlparse(app.config['MONGO_URI'])
            app.config['MONGODB_USER'] = url.username
            app.config['MONGODB_PASSWORD'] = url.password
            app.config['MONGODB_HOST'] = url.hostname
            app.config['MONGODB_PORT'] = url.port
            app.config['MONGODB_DB'] = url.path[1:]


def from_envvars(conf, prefix, envvars=None, as_json=True):
    """Load environment variables as Flask configuration settings.

    Values are parsed as JSON. If parsing fails with a ValueError,
    values are instead used as verbatim strings.

    :param app: App, whose configuration should be loaded from ENVVARs.
    :param envvars: A dictionary of mappings of environment-variable-names
                    to Flask configuration names. If a list is passed
                    instead, names are mapped 1:1. If ``None``, see prefix
                    argument.
    :param prefix: If ``None`` is passed as envvars, all variables from
                   ``environ`` starting with this prefix are imported. The
                   prefix is stripped upon import.
    :param as_json: If False, values will not be parsed as JSON first.
    """

    # if it's a list, convert to dict
    if isinstance(envvars, list):
        envvars = {k: None for k in envvars}

    if not envvars:
        envvars = {k: k[len(prefix):] for k in os.environ.iterkeys()
                   if k.startswith(prefix)}

    for env_name, name in envvars.iteritems():
        if name is None:
            name = env_name

        if not env_name in os.environ:
            continue

        if as_json:
            try:
                conf[name] = json.loads(os.environ[env_name])
            except ValueError:
                conf[name] = os.environ[env_name]
        else:
            conf[name] = os.environ[env_name]

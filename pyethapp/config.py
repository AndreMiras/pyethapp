"""
Support for simple yaml persisted config dicts.

Usual building of the configuration
 - with datadir (default or from option)
    - create dir if not available
        - create minimal config if not available
    - load config
 - App is initialized with an (possibly empty) config
    which is recursively updated (w/o overriding values) with its own default config
 - Services are initialized with app and
    recursively update (w/o overriding values) the config with their default config

todo:
    datadir


"""
import random
import os
import sys
import click
from devp2p.utils import update_config_with_defaults
import yaml
import ethereum.slogging as slogging
from importlib import import_module
import inspect
from devp2p.service import BaseService
from devp2p.app import BaseApp


slogging.configure(config_string=':debug')
log = slogging.get_logger('config')

default_data_dir = click.get_app_dir('pyethapp')


def get_config_path(data_dir=default_data_dir):
    return os.path.join(data_dir, 'config.yaml')

default_config_path = get_config_path(default_data_dir)


def setup_data_dir(data_dir):
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)


required_config = dict(p2p=dict(privkey_hex=''), eth=dict(privkey_hex=''))


def check_config(config, required_config=required_config):
    "check if values are set"
    for k, v in required_config.items():
        if not config.get(k):
            return False
        if isinstance(v, dict):
            if not check_config(config[k], v):
                return False
    return True


def setup_default_config(data_dir=default_data_dir):
    "writes minimal neccessary config to data_dir"
    def mk_privkey_hex():
        return hex(random.getrandbits(256))[2:]
    log.info('setup default config', path=data_dir)
    config_path = get_config_path(data_dir)
    assert not os.path.exists(config_path)
    setup_data_dir(data_dir)
    config = dict(p2p=dict(privkey_hex=mk_privkey_hex()),
                  eth=dict(privkey_hex=mk_privkey_hex()))
    write_config(config, config_path)


def get_default_config(services):
    "collect default_config from services"
    config = dict()
    for s in services:
        assert isinstance(s, (BaseService, BaseApp))
        update_config_with_defaults(config, s.default_config)
    return config


def load_config(path=default_config_path):
    """Load config from string or file like object `path`."""
    log.info('loading config', path=path)
    if os.path.exists(path):
        return yaml.load(open(path))
    return dict()


def write_config(config, path=default_config_path):
    """Load config from string or file like object `f`, discarding the one
    already in place.
    """
    assert path
    log.info('writing config', path=path)
    with open(path, 'wb') as f:
        yaml.dump(config, f)


def set_config_param(config, s, strict=True):
    """Set a specific config parameter.

    :param s: a string of the form ``a.b.c=d`` which will set the value of
              ``config['a']['b']['b']`` to ``yaml.load(d)``
    :param strict: if `True` will only override existing values.
    :raises: :exc:`ValueError` if `s` is malformed or the value to set is not
             valid YAML
    """
    # fixme add += support
    try:
        param, value = s.split('=', 1)
        keys = param.split('.')
    except ValueError:
        raise ValueError('Invalid config parameter')
    d = config
    for key in keys[:-1]:
        if strict and key not in d:
            raise KeyError('Unknown config option')
        d = d.setdefault(key, {})
    try:
        d[keys[-1]] = yaml.load(value)
    except yaml.parser.ParserError:
        raise ValueError('Invalid config value')
    return config


def load_contrib_services(config):  # FIXME
    # load contrib services
    contrib_directory = os.path.join(config_directory, 'contrib')  # change to pyethapp/contrib
    contrib_modules = []
    for directory in config['app']['contrib_dirs']:
        sys.path.append(directory)
        for filename in os.listdir(directory):
            path = os.path.join(directory, filename)
            if os.path.isfile(path) and filename.endswith('.py'):
                contrib_modules.append(import_module(filename[:-3]))
    contrib_services = []
    for module in contrib_modules:
        classes = inspect.getmembers(module, inspect.isclass)
        for _, cls in classes:
            if issubclass(cls, BaseService) and cls != BaseService:
                contrib_services.append(cls)
    log.info('Loaded contrib services', services=sorted(contrib_services.keys()))
    return contrib_services


"""
if os.path.exists(config_path):
    with open(config_path) as f:
        load_config(f)
else:
    load_config(default_config)
    pubkey = crypto.privtopub(config['p2p']['privkey_hex'].decode('hex'))
    config['app']['dir'] = config_directory
    config['p2p']['node_id'] = crypto.sha3(pubkey)
    config['app']['contrib_dirs'].append(contrib_directory)
    # problem with the following code: default config specified here is
    # ignored if config file already exists -> annoying for development with
    # frequently changing default config. Also: comments are discarded
#   try:
#       os.makedirs(config_directory)
#   except OSError as exc:
#       if exc.errno == errno.EEXIST:
#           pass
#       else:
#           raise
#   with open(config_path, 'wb') as f:
#       yaml.dump(config, f)
"""

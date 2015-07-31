#!/usr/bin/env python

"""
    mini.py: minifies and compresses static content.

    yuicompressor, htmlcompressor, uglifyjs, and lessc are run against the
    CSS, JS, HTML. Then CSS, JS, and images are GZipped.
    The result is a tar archive pumped to stdout.
"""

""" Version history
1.0.0 - Initial build (Based off of pywebbuild project)
"""

__author__ = 'Justin Wilson'
__copyright__ = 'Copyright 2015'
__credits__ = ['Justin Wilson']

__license__ = 'BSD'
__version__ = '1.0.0'
__maintainer__ = 'Justin Wilson'
__repository__ = 'https://github.com/juztin/mini'
__email__ = 'justin@mini.io'
__status__ = 'Beta'

import os
import re
import sys
from optparse import OptionParser

from subprocess import Popen, PIPE
from shutil import ignore_patterns
from time import time

CWD = os.getcwd()
UTIL_ROOT = os.path.dirname(sys.argv[0])
UTIL_JOIN = lambda *args: os.path.join(UTIL_ROOT, *args)
IGNORE_FILES = ['.DS_Store', '*.pyc', 'tmp*', '*.xcf']

MINIFY_CSS = ['java', '-jar', UTIL_JOIN('yuicompressor.jar'), '{FILENAME}']
MINIFY_HTML = ['java', '-jar', UTIL_JOIN('htmlcompressor.jar'), '{FILENAME}']
MINIFY_JS = ['uglifyjs', '{FILENAME}']
COMPRESS_FILE = ['gzip', '-c', '{FILENAME}']


class cprint:
    # http://snippets.dzone.com/posts/show/6944
    DISABLE = True
    OK = '\033[32m'
    WARNING = '\033[33m'
    ERROR = '\033[31m'
    INFO = '\033[34m'
    MSG = '\033[37m'
    DEFAULT = '\033[m'

    @staticmethod
    def _print(color, msg, reg_msg=''):
        if cprint.DISABLE:
            print(msg, reg_msg)
        else:
            print("{0}{1}{2}{3}".format(color, msg, cprint.DEFAULT, reg_msg))

    @staticmethod
    def warning(msg, reg_msg=''):
        cprint._print(cprint.WARNING, msg, reg_msg)

    @staticmethod
    def error(msg, reg_msg=''):
        cprint._print(cprint.ERROR, msg, reg_msg)

    @staticmethod
    def ok(msg, reg_msg=''):
        cprint._print(cprint.OK, msg, reg_msg)

    @staticmethod
    def info(msg, reg_msg=''):
        cprint._print(cprint.INFO, msg, reg_msg)

    @staticmethod
    def msg(msg, reg_msg=''):
        cprint._print(cprint.MSG, msg, reg_msg)


def timed(f):
    def _f(*args, **kwds):
        start = time()
        result = f(*args, **kwds)
        elapsed = time() - start

        if cprint.DISABLE:
            print('Build finished in {0} seconds'.format(elapsed))
        else:
            print("{2}{0}\r\n{1}Build finished in {2}{3}{1} seconds{4}".format(
                  '-----------------------------------------------------------',
                  cprint.INFO,
                  cprint.WARNING,
                  elapsed,
                  cprint.DEFAULT))

        return result
    return _f


def _perform_utilproc(src, cmd_args,
                      on_cmd=None, include=None, ignore=None, verbose=False):
    if include is None:
        return

    names = os.listdir(src)
    inc_p = ignore_patterns(*include)
    include_names = inc_p(src, names)

    if ignore is None:
        ignore_files = set()
    else:
        patterns = ignore_patterns(*ignore)
        ignore_files = patterns(src, names)

    for name in names:
        if name in ignore_files:
            if verbose:
                cprint.warning('ignored: ', os.path.join(src, name))
            continue

        srcname = os.path.join(src, name)
        if not os.path.isdir(srcname) and name not in include_names:
            if verbose:
                cprint.warning('excluded: ', os.path.join(src, name))
            continue

        try:
            if os.path.isdir(srcname):
                _perform_utilproc(srcname,
                                  cmd_args,
                                  on_cmd=on_cmd,
                                  include=include,
                                  ignore=ignore,
                                  verbose=verbose)
            else:
                args = [a if a != '{FILENAME}' else srcname for a in cmd_args]
                if verbose:
                    cprint.ok(str(' '.join(c for c in args)))

                p = Popen(args, stdout=PIPE, stderr=PIPE)
                stdout, stderr = p.communicate()

                if p.returncode != 0:
                    cprint.error('ERROR PROCESSING: ', '{0} -> {1}'.
                                 format(srcname, args))
                    print(stderr)
                    continue

                if on_cmd is not None:
                    on_cmd(srcname, stdout)
                elif verbose:
                    print(stdout)

        except (IOError, os.error) as err:
            print(err)
            msg = "Failed to perform util on {0}: ".format(srcname, str(err))
            return (False, msg)

    return (True, None)


def minify_css(src, util_dir, verbose):
    def write_file(filename, compressed_content):
        fnp = os.path.splitext(filename)
        min_filename = fnp[0]+'.min'+fnp[1]

        with open(min_filename, 'w') as f:
            f.write(str(compressed_content))

    (succeded, err) = _perform_utilproc(
        src,
        MINIFY_CSS,
        on_cmd=write_file,
        include=['*.css'],
        ignore=['*.min.*', 'lib', 'libs', 'vendor'],
        verbose=verbose)

    if not succeded:
        raise Exception(err)


def minify_js(src, util_dir, verbose):
    def write_file(filename, compressed_content):
        fnp = os.path.splitext(filename)
        min_filename = fnp[0]+'.min'+fnp[1]

        with open(min_filename, 'w') as f:
            f.write(str(compressed_content))

    (succeded, err) = _perform_utilproc(
        src,
        MINIFY_JS,
        on_cmd=write_file,
        include=['*.js'],
        ignore=['*.min.*', 'lib', 'libs', 'vendor'],
        verbose=verbose)

    if not succeded:
        raise Exception(err)


def minify_html(src, util_dir, verbose, fix_django=False):
    def write_file(filename, lines):
        with open(filename, 'w') as f:
            for line in lines:
                f.write(line)

    def fix_djangotemplate(template_name, lines):
        filename = os.path.basename(template_name)
        cprint.info('Fixing Django template: %s' % filename)
        exp = re.compile(r'(\{%\s[^%}]*[^\s=><])([=><]{2})([^}%]*%\})')
        for line in lines:
            yield exp.sub(r'\1 \2\3', line)

    def write_handler(filename, content):
        lines = content.splitlines()
        if fix_django:
            lines = fix_djangotemplate(filename, lines)
        write_file(filename, lines)

    (succeded, err) = _perform_utilproc(
        src,
        MINIFY_HTML,
        on_cmd=write_handler,
        include=['*.html'],
        verbose=verbose)

    if not succeded:
        raise Exception(err)


def gzip_content(src, util_dir, include_files=None, ignore=None, verbose=False):
    def write_file(filename, gzipped_content):
        with open(filename+'.gz', 'wb') as f:
            f.write(gzipped_content)

    if not ignore:
        ignore = []
    ignore.append('*.gz')

    (succeded, err) = _perform_utilproc(
        src,
        COMPRESS_FILE,
        on_cmd=write_file,
        include=include_files,
        ignore=ignore,
        verbose=verbose)

    if not succeded:
        raise Exception(err)


@timed
def build(static_path, util_dir, ignore, verbose):
    # Minify html
    cprint.info('Minifying html')
    minify_html(static_path,
                util_dir,
                verbose)

    # Minify css
    cprint.info('Minifying stylesheets')
    minify_css(static_path,
               util_dir,
               verbose)

    # Minify js
    cprint.info('Minifying scripts')
    minify_js(static_path,
              util_dir,
              verbose)

    # Gzip css
    cprint.info('GZipping css')
    gzip_content(static_path,
                 util_dir,
                 include_files=['*.css'],
                 verbose=verbose)

    # Gzip js
    cprint.info('GZipping js')
    gzip_content(static_path,
                 util_dir,
                 include_files=['*.js'],
                 verbose=verbose)

    # Gzip images
    cprint.info('GZipping images')
    gzip_content(static_path,
                 util_dir,
                 include_files=['*.jpg', '*.png', '*.gif', '*.bmp', '*.ico'],
                 verbose=verbose)


import traceback
parser = OptionParser()
parser.add_option('-c', '--color', action='store_true', default=False,
                  help='colorize output.')
parser.add_option('-v', '--verbose', action='store_true', default=False,
                  help='verbose output.')
parser.add_option('-p', '--path', default=CWD,
                  help='path to static content to minify/compress')

(options, args) = parser.parse_args()
cprint.DISABLE = not options.color

try:
    build(options.path, UTIL_ROOT, IGNORE_FILES, options.verbose)
except Exception as err:
    print(traceback.format_exc())
    cprint.error(err)
    cprint.error('Build Failed!')

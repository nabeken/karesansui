#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of Karesansui.
#
# Copyright (C) 2010 HDE, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#

import os
import sys
import re
import logging
from optparse import OptionParser

from ksscommand import KssCommand, KssCommandException, KssCommandOptException

import __cmd__

try:
    import karesansui
    from karesansui import __version__
    from karesansui.lib.virt.virt import KaresansuiVirtConnection
    from karesansui.lib.utils import load_locale
    from karesansui.lib.const import VIRT_STORAGE_CONFIG_DIR
except ImportError:
    print >>sys.stderr, "[Error] karesansui package was not found."
    sys.exit(1)

_ = load_locale()

usage = '%prog [options]'

def getopts():
    optp = OptionParser(usage=usage, version=__version__)
    optp.add_option('-n', '--name', dest='name', help=_('Storage pool name'), default=None)
    optp.add_option('-f', '--force', dest='force', action="store_true",
                    help=_('Force to remove the storage pool'), default=False)
    return optp.parse_args()

def chkopts(opts):
    reg = re.compile("[^a-zA-Z0-9\./_:-]")

    if opts.name:
        if reg.search(opts.name):
            raise KssCommandOptException('ERROR: Illigal option value. option=%s value=%s' % ('-n or --name', opts.name))
    else:
        raise KssCommandOptException('ERROR: %s option is required.' % '-n or --name')

class DeleteStoragePool(KssCommand):

    def process(self):
        (opts, args) = getopts()
        chkopts(opts)
        self.up_progress(10)

        conn = KaresansuiVirtConnection(readonly=False)
        try:
            inactive_storage_pools = conn.list_inactive_storage_pool()
            active_storage_pools = conn.list_active_storage_pool()
            self.up_progress(10)
            if not (opts.name in active_storage_pools or \
                   opts.name in inactive_storage_pools):
                raise KssCommandException('Storage pool does not exist. - pool=%s'
                                          % (opts.name))
            try:
                self.up_progress(30)
                if opts.force is True and opts.name in conn.list_active_storage_pool():
                    if conn.destroy_storage_pool(opts.name) is False:
                        raise KssCommandException("Failed to stop the storage pool. - pool=%s" \
                                                  % (opts.name))

                if opts.name in conn.list_active_storage_pool():
                    raise KssCommandException(
                        "Could not delete storage pool: internal error storage pool is still active' pool=%s" \
                        % opts.name)

                if conn.delete_storage_pool(opts.name, False) is False:
                    raise KssCommandException("Failed to remove the storage pool. - pool=%s" \
                                              % (opts.name))
                self.up_progress(30)

                # pool check
                inactive_storage_pools = conn.list_inactive_storage_pool()
                active_storage_pools = conn.list_active_storage_pool()
                if opts.name in active_storage_pools or \
                       opts.name in inactive_storage_pools:
                    raise KssCommandException('Could not remove a storage pool. - pool=%s' \
                                              % (opts.name))

                # .xml
                path = "%s/%s.xml" % (VIRT_STORAGE_CONFIG_DIR, opts.name)
                if os.path.isfile(path) is True:
                    raise KssCommandException(
                        "Could not delete the configuration file. - pool=%s, path=%s" \
                        % (opts.name, path))

                self.logger.info('Deleted storage pool. - pool=%s' % (opts.name))
                print >>sys.stdout, _('Deleted storage pool. - pool=%s') % (opts.name)
                return True
            except KssCommandException, e:
                raise e
        finally:
            conn.close()

if __name__ == "__main__":
    target = DeleteStoragePool()
    sys.exit(target.run())
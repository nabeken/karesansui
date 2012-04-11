# -*- coding: utf-8 -*-
#
# This file is part of Karesansui.
#
# Copyright (C) 2009-2010 HDE, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#

import web
import simplejson as json

import karesansui
from karesansui.lib.rest import Rest, auth
from karesansui.db.access.machine import \
     findbyhost1, findby1name, findby1hostname, \
     update as m_update, delete as m_delete, logical_delete

from karesansui.lib.merge import MergeHost
from karesansui.lib.virt.virt import KaresansuiVirtConnection
from karesansui.lib.utils import \
    comma_split, uniq_sort, is_param, json_dumps, \
    get_proc_cpuinfo, get_proc_meminfo, get_partition_info, \
    available_virt_uris

from karesansui.lib.checker import Checker, \
    CHECK_EMPTY, CHECK_LENGTH, CHECK_ONLYSPACE, CHECK_VALID,\
    CHECK_MIN, CHECK_MAX

from karesansui.lib.const import \
    NOTE_TITLE_MIN_LENGTH, NOTE_TITLE_MAX_LENGTH, \
    MACHINE_NAME_MIN_LENGTH, MACHINE_NAME_MAX_LENGTH, \
    TAG_MIN_LENGTH, TAG_MAX_LENGTH, \
    FQDN_MIN_LENGTH, FQDN_MAX_LENGTH, \
    PORT_MIN_NUMBER, PORT_MAX_NUMBER, \
    VENDOR_DATA_DIR

from karesansui.db.access.tag import \
    new as t_new, samecount as t_count, findby1name as t_name


def validates_host_edit(obj):
    checker = Checker()
    check = True

    _ = obj._
    checker.errors = []

    if not is_param(obj.input, 'm_name'):
        check = False
        checker.add_error(_('Parameter m_name does not exist.'))
    else:
        check = checker.check_string(
                    _('Machine Name'),
                    obj.input.m_name,
                    CHECK_EMPTY | CHECK_LENGTH | CHECK_ONLYSPACE,
                    None,
                    min = MACHINE_NAME_MIN_LENGTH,
                    max = MACHINE_NAME_MAX_LENGTH,
            ) and check

    if not is_param(obj.input, 'm_hostname'):
        check = False
        checker.add_error(_('"%s" is required.') % _('FQDN'))
    else:
        m_hostname_parts = obj.input.m_hostname.split(":")
        if len(m_hostname_parts) > 2:
            check = False
            checker.add_error(_('%s contains too many colon(:)s.') % _('FQDN'))
        else:
            check = checker.check_domainname(
                        _('FQDN'),
                        m_hostname_parts[0],
                        CHECK_EMPTY | CHECK_LENGTH | CHECK_VALID,
                        min = FQDN_MIN_LENGTH,
                        max = FQDN_MAX_LENGTH,
                        ) and check
            try:
                check = checker.check_number(
                            _('Port Number'),
                            m_hostname_parts[1],
                            CHECK_EMPTY | CHECK_VALID | CHECK_MIN | CHECK_MAX,
                            PORT_MIN_NUMBER,
                            PORT_MAX_NUMBER,
                            ) and check
            except IndexError:
                # when reach here, 'm_hostname' has only host name
                pass

    if is_param(obj.input, 'note_title'):
        check = checker.check_string(
                    _('Title'),
                    obj.input.note_title,
                    CHECK_LENGTH | CHECK_ONLYSPACE,
                    None,
                    min = NOTE_TITLE_MIN_LENGTH,
                    max = NOTE_TITLE_MAX_LENGTH,
                ) and check

    if is_param(obj.input, 'note_value'):
        check = checker.check_string(
                    _('Note'),
                    obj.input.note_value,
                    CHECK_ONLYSPACE,
                    None,
                    None,
                    None,
                ) and check

    if is_param(obj.input, 'tags'):
        for tag in comma_split(obj.input.tags):
            check = checker.check_string(
                        _('Tag'),
                        tag,
                        CHECK_LENGTH | CHECK_ONLYSPACE,
                        None,
                        min = TAG_MIN_LENGTH,
                        max = TAG_MAX_LENGTH,
                    ) and check

    obj.view.alert = checker.errors
    return check

class HostBy1(Rest):

    def _post(self, f):
        ret = Rest._post(self, f)
        if hasattr(self, "kvc") is True:
            self.kvc.close()
        return ret

    @auth
    def _GET(self, *param, **params):

        if self.input.has_key('job_id') is True:
            self.view.job_id = self.input.job_id
        else:
            self.view.job_id = None

        host_id = self.chk_hostby1(param)
        if host_id is None: return web.notfound()

        model = findbyhost1(self.orm, host_id)

        uris = available_virt_uris()
        if model.attribute == 0 and model.hypervisor == 1:
            uri = uris["XEN"]
        elif model.attribute == 0 and model.hypervisor == 2:
            uri = uris["KVM"]
        else:
            uri = None

        # other_url
        other_url = "%s://%s%s/" % (self.view.ctx.protocol, model.hostname, karesansui.config['application.url.prefix'])
        
        if self.is_mode_input() is False:
            if karesansui.config["application.uniqkey"] == model.uniq_key:
                # My host
                host_cpuinfo = get_proc_cpuinfo()
                cpuinfo = {}
                cpuinfo["number"] = len(host_cpuinfo)
                cpuinfo["vendor"] = host_cpuinfo[0]["vendor_id"]
                cpuinfo["model"] = host_cpuinfo[0]["model name"]
                cpuinfo["frequency"] = host_cpuinfo[0]["cpu MHz"]

                host_meminfo = get_proc_meminfo()
                meminfo = {}
                meminfo["total"] = host_meminfo["MemTotal"][0]
                meminfo["free"] = host_meminfo["MemFree"][0]
                meminfo["buffers"] = host_meminfo["Buffers"][0]
                meminfo["cached"] = host_meminfo["Cached"][0]

                host_diskinfo = get_partition_info(VENDOR_DATA_DIR)
                diskinfo = {}
                diskinfo["total"] = host_diskinfo[1]
                diskinfo["free"] = host_diskinfo[3]

                self.kvc = KaresansuiVirtConnection(uri)
                try:
                    host = MergeHost(self.kvc, model)
                    if self.is_json() is True:
                        json_host = host.get_json(self.me.languages)
                        self.view.data = json_dumps({"model": json_host["model"], 
                                                     "cpuinfo": cpuinfo,
                                                     "meminfo": meminfo,
                                                     "diskinfo": diskinfo,
                                                     })
                    else:
                        self.view.model = host.info["model"]
                        self.view.virt = host.info["virt"]
                finally:
                    self.kvc.close()

            else:
                # other host
                if self.is_json() is True:
                    self.view.data = json_dumps({
                        "model": model.get_json(self.me.languages),
                        "other_url" : other_url,
                        })
                else:
                    self.view.model = model
                    self.view.virt = None
                    self.view.other_url = other_url

            return True
        else:
            # mode=input
            self.kvc = KaresansuiVirtConnection(uri)
            try:
                host = MergeHost(self.kvc, model)
                self.view.model = host.info["model"]
                self.view.application_uniqkey = karesansui.config['application.uniqkey']
            finally:
                self.kvc.close()

            return True

    @auth
    def _PUT(self, *param, **params):
        host_id = self.chk_hostby1(param)
        if host_id is None: return web.notfound()
        
        if not validates_host_edit(self):
            self.logger.debug("Update Host OS is failed, Invalid input value.")
            return web.badrequest(self.view.alert)

        host = findbyhost1(self.orm, host_id)

        cmp_host = findby1name(self.orm, self.input.m_name)
        if cmp_host is not None and int(host_id) != cmp_host.id:
            self.logger.debug("Update Host OS is failed, "
                              "Already exists name"
                              "- %s, %s" % (host, cmp_host))
            return web.conflict(web.ctx.path)

        hostname_check = findby1hostname(self.orm, self.input.m_hostname)
        if hostname_check is not None and int(host_id) != hostname_check.id:
            return web.conflict(web.ctx.path)

        if is_param(self.input, "m_hostname"):
            host.hostname = self.input.m_hostname
        if is_param(self.input, "note_title"):
            host.notebook.title = self.input.note_title
        if is_param(self.input, "note_value"):
            host.notebook.value = self.input.note_value
        if is_param(self.input, "m_name"):
            host.name = self.input.m_name
    
        # Icon
        icon_filename = None
        if is_param(self.input, "icon_filename", empty=True):
            host.icon = self.input.icon_filename

        # tag UPDATE
        if is_param(self.input, "tags"):
            _tags = []
            tag_array = comma_split(self.input.tags)
            tag_array = uniq_sort(tag_array)
            for x in tag_array:
                if t_count(self.orm, x) == 0:
                    _tags.append(t_new(x))
                else:
                    _tags.append(t_name(self.orm, x))
            host.tags = _tags

        host.modified_user = self.me

        m_update(self.orm, host)

        return web.seeother(web.ctx.path)

    @auth
    def _DELETE(self, *param, **params):

        host_id = self.chk_hostby1(param)
        if host_id is None: return web.notfound()

        host = findbyhost1(self.orm, host_id)

        logical_delete(self.orm, host)

        return web.seeother(url = "/")

urls = (
    '/host/(\d+)/?(\.html|\.part|\.json)?$', HostBy1,
    )
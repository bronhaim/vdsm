#
# Copyright 2015 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

vdsmpyrpcdir = $(pythondir)/api
vdsmrpcdir = $(vdsmpylibdir)/rpc

CLEANFILES = \
	vdsm-api.html \
	$(NULL)

EXTRA_DIST = \
	schema_to_html.py \
	$(NULL)

dist_vdsmpyrpc_PYTHON = \
	__init__.py \
	vdsmapi.py \
	$(NULL)

dist_vdsmrpc_DATA = \
	vdsm-api.yml \
	vdsm-api-gluster.yml \
	vdsm-events.yml \
	$(NULL)

nodist_noinst_DATA = \
	vdsm-api.html \
	$(NULL)

vdsm-api.html: schema_to_html.py vdsm-api.yml
	@echo "  Generate $@"
	chmod u+w $(srcdir)
	PYTHONPATH=$(srcdir)/../:$(srcdir)/../vdsm \
	    $(PYTHON) schema_to_html.py vdsm-api.yml $@

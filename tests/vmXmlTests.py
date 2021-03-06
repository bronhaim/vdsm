# -*- coding: utf-8 -*-
#
# Copyright 2014, 2016 Red Hat, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import

from vdsm import cpuarch
from vdsm.virt import vmchannels

from virt import domain_descriptor
from virt import vmxml

from testlib import VdsmTestCase as TestCaseBase
from testlib import XMLTestCase, permutations, expandPermutations

import vmfakelib as fake

from vmTestsData import CONF_TO_DOMXML_X86_64
from vmTestsData import CONF_TO_DOMXML_PPC64
from vmTestsData import CONF_TO_DOMXML_NO_VDSM


class VmXmlTestCase(TestCaseBase):

    _CONFS = {
        cpuarch.X86_64: CONF_TO_DOMXML_X86_64,
        cpuarch.PPC64: CONF_TO_DOMXML_PPC64,
        'novdsm': CONF_TO_DOMXML_NO_VDSM}

    def _build_domain_xml(self, arch):
        for conf, rawXml in self._CONFS[arch]:
            domXml = rawXml % conf
            yield fake.Domain(domXml, vmId=conf['vmId']), domXml


@expandPermutations
class TestVmXmlFunctions(VmXmlTestCase):

    @permutations([[cpuarch.X86_64], [cpuarch.PPC64]])
    def test_has_channel(self, arch):
        for _, dom_xml in self._build_domain_xml(arch):
            self.assertEqual(True, vmxml.has_channel(
                dom_xml, vmchannels.DEVICE_NAME))

    @permutations([
        # custom, mapping
        [{}, {}],
        [{'volumeMap': 'data:vda'}, {'data': 'vda'}],
        [{'volumeMap': 'data:vda,extra:vdb'},
         {'data': 'vda', 'extra': 'vdb'}],
        [{'volumeMap': 'data1:vda, data2:vdb'},
         {'data1': 'vda', 'data2': 'vdb'}],
    ])
    def test_parse_drive_mapping(self, custom, mapping):
        result = vmxml.parse_drive_mapping(custom)
        self.assertEqual(result, mapping)

    @permutations([
        # custom, exc
        [{'volumeMap': ''}, ValueError],
        [{'volumeMap': 'foobar'}, ValueError],
    ])
    def test_explode_parsing_drive_mapping(self, custom, exc):
        self.assertRaises(exc,
                          vmxml.parse_drive_mapping,
                          custom)


@expandPermutations
class TestVmXmlHelpers(XMLTestCase):

    _XML = u'''<?xml version="1.0" ?>
    <topelement>
      <hello lang="english">hello</hello>
      <hello cyrillic="yes" lang="русский">здра́вствуйте</hello>
      <bye>good bye<hello lang="čeština">dobrý den</hello></bye>
      <empty/>
    </topelement>
    '''

    def setUp(self):
        self._dom = vmxml.parse_xml(self._XML)

    def test_import_export(self):
        xml = vmxml.format_xml(self._dom)
        self.assertXMLEqual(xml, self._XML)

    @permutations([[None, 'topelement', 1],
                   ['topelement', 'topelement', 1],
                   [None, 'hello', 3],
                   ['topelement', 'bye', 1],
                   [None, 'none', 0]])
    def test_find_all(self, start_tag, tag, number):
        dom = self._dom
        if start_tag is not None:
            dom = vmxml.find_first(self._dom, 'topelement')
        elements = vmxml.find_all(dom, tag)
        matches = [vmxml.tag(e) == tag for e in elements]
        self.assertTrue(all(matches))
        self.assertEqual(len(matches), number)

    def test_find_first_not_found(self):
        self.assertRaises(vmxml.NotFound, vmxml.find_first, self._dom, 'none')

    @permutations([['hello', 'lang', 'english'],
                   ['hello', 'none', ''],
                   ['none', 'lang', ''],
                   ])
    def test_find_attr(self, tag, attribute, result):
        value = vmxml.find_attr(self._dom, tag, attribute)
        self.assertEqual(value, result)

    @permutations([['hello', 1, {'cyrillic': 'yes', 'lang': 'русский'}],
                   ['topelement', 0, {}],
                   ['empty', 0, {}],
                   ])
    def test_attributes(self, tag, index, result):
        element = list(vmxml.find_all(self._dom, tag))[index]
        self.assertEqual(vmxml.attributes(element), result)

    @permutations([['hello', 'hello'],
                   ['empty', '']])
    def test_text(self, tag, result):
        element = vmxml.find_first(self._dom, tag)
        text = vmxml.text(element)
        self.assertEqual(text, result)

    @permutations([['topelement', 'hello', 2],
                   ['bye', 'hello', 1],
                   ['empty', 'hello', 0],
                   ['topelement', 'none', 0],
                   ['topelement', None, 4],
                   ])
    def test_children(self, start_tag, tag, number):
        element = vmxml.find_first(self._dom, start_tag)
        self.assertEqual(len(list(vmxml.children(element, tag))), number)

    def test_append_child(self):
        empty = vmxml.find_first(self._dom, 'empty')
        vmxml.append_child(empty, vmxml.Element('new'))
        self.assertIsNotNone(vmxml.find_first(self._dom, 'new', None))
        empty = vmxml.find_first(self._dom, 'empty')
        self.assertIsNotNone(vmxml.find_first(empty, 'new', None))

    def test_remove_child(self):
        top = vmxml.find_first(self._dom, 'topelement')
        hello = list(vmxml.find_all(top, 'hello'))
        old = hello[1]
        vmxml.remove_child(top, old)
        updated_hello = list(vmxml.find_all(top, 'hello'))
        hello = hello[:1] + hello[2:]
        self.assertEqual(updated_hello, hello)

    def test_namespaces(self):
        expected_xml = '''
        <domain xmlns:ovirt="http://ovirt.org/vm/tune/1.0">
          <metadata>
            <ovirt:qos/>
          </metadata>
        </domain>
        '''
        domain = vmxml.Element('domain')
        metadata = vmxml.Element('metadata')
        domain.appendChild(metadata)
        qos = vmxml.Element('qos', namespace='ovirt',
                            namespace_uri='http://ovirt.org/vm/tune/1.0')
        metadata.appendChild(qos)
        self.assertXMLEqual(vmxml.format_xml(domain), expected_xml)


@expandPermutations
class TestDomainDescriptor(VmXmlTestCase):

    @permutations([[cpuarch.X86_64], [cpuarch.PPC64]])
    def test_all_channels_vdsm_domain(self, arch):
        for _, dom_xml in self._build_domain_xml(arch):
            dom = domain_descriptor.DomainDescriptor(dom_xml)
            channels = list(dom.all_channels())
            self.assertTrue(len(channels) >=
                            len(vmchannels.AGENT_DEVICE_NAMES))
            for name, path in channels:
                self.assertIn(name, vmchannels.AGENT_DEVICE_NAMES)

    def test_all_channels_extra_domain(self):
        for conf, raw_xml in CONF_TO_DOMXML_NO_VDSM:
            dom = domain_descriptor.DomainDescriptor(raw_xml % conf)
            self.assertNotEquals(sorted(dom.all_channels()),
                                 sorted(vmchannels.AGENT_DEVICE_NAMES))


@expandPermutations
class TestVmXmlMetadata(XMLTestCase):

    def __init__(self, *args, **kwargs):
        XMLTestCase.__init__(self, *args, **kwargs)
        self.channelListener = None
        self.conf = {
            'vmName': 'testVm',
            'vmId': '9ffe28b6-6134-4b1e-8804-1185f49c436f',
            'smp': '8',
            'maxVCpus': '160',
            'memSize': '1024',
            'memGuaranteedSize': '512',
        }

    def test_no_custom(self):
        expected = """
          <domain type="kvm" xmlns:ovirt="http://ovirt.org/vm/tune/1.0">
            <metadata>
              <ovirt:qos/>
            </metadata>
          </domain>
        """
        conf = {}
        conf.update(self.conf)
        domxml = StrippedDomain(conf, self.log, cpuarch.X86_64)
        domxml.appendMetadata()
        result = domxml.toxml()
        self.assertXMLEqual(result, expected)

    @permutations([
        # conf
        [{}],
        [{'custom': {}}],
        [{'custom': {'containerImage': 'foobar'}}],
        [{'custom': {'containerType': 'foobar'}}],
    ])
    def test_no_container_data(self, conf):
        expected = """
          <domain type="kvm" xmlns:ovirt="http://ovirt.org/vm/tune/1.0">
            <metadata>
              <ovirt:qos/>
            </metadata>
          </domain>
        """
        conf.update(self.conf)
        domxml = StrippedDomain(conf, self.log, cpuarch.X86_64)
        domxml.appendMetadata()
        result = domxml.toxml()
        self.assertXMLEqual(result, expected)

    def test_container_data(self):
        expected = """
          <domain xmlns:ns0="http://ovirt.org/vm/tune/1.0"
                  xmlns:ns1="http://ovirt.org/vm/containers/1.0"
                  type="kvm">
            <metadata>
              <ns0:qos />
              <ns1:container image="foobar">foobar</ns1:container>
            </metadata>
          </domain>
        """
        conf = {
            'custom': {
                'containerImage': 'foobar',
                'containerType': 'foobar',
            }
        }
        conf.update(self.conf)
        domxml = StrippedDomain(conf, self.log, cpuarch.X86_64)
        domxml.appendMetadata()
        result = domxml.toxml()
        self.assertXMLEqual(result, expected)

    def test_container_data_drive_map(self):
        expected = """
          <domain xmlns:ns0="http://ovirt.org/vm/tune/1.0"
                  xmlns:ns1="http://ovirt.org/vm/containers/1.0"
                  xmlns:ns2="http://ovirt.org/vm/containers/drivemap/1.0"
                  type="kvm">
            <metadata>
              <ns0:qos />
              <ns1:container image="foobar">foobar</ns1:container>
              <ns2:drivemap>
                <ns2:volume drive="vda" name="data1" />
                <ns2:volume drive="vdb" name="data2" />
              </ns2:drivemap>
            </metadata>
          </domain>
        """
        conf = {
            'custom': {
                'containerImage': 'foobar',
                'containerType': 'foobar',
                'volumeMap': 'data1:vda,data2:vdb',
            }
        }
        conf.update(self.conf)
        domxml = StrippedDomain(conf, self.log, cpuarch.X86_64)
        domxml.appendMetadata()
        result = domxml.toxml()
        self.assertXMLEqual(result, expected)


class StrippedDomain(vmxml.Domain):
    """
    Bare-bones vmxml.Domain, which doesn't add elements on its __init__
    to sinmplify the testing. Will be dropped if vmxml.Domain is refactored.
    """
    def __init__(self, conf, log, arch):
        self.conf = conf
        self.log = log
        self.arch = arch
        self.dom = vmxml.Element('domain', type='kvm')

    def toxml(self):
        return vmxml.format_xml(self.dom)

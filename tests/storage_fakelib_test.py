# Copyright 2015-2016 Red Hat, Inc.
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

from contextlib import contextmanager
import os

from vdsm.storage import exception as se
from vdsm.storage import constants as sc

from testlib import VdsmTestCase, namedTemporaryDir
from testlib import permutations, expandPermutations

from storagefakelib import FakeLVM
from storagefakelib import FakeResourceManager
from storagefakelib import FakeStorageDomainCache
from storagetestlib import FakeSD

from storage import blockSD
from storage import lvm as real_lvm


MB = 1024 ** 2


class FakeLVMSimpleVGTests(VdsmTestCase):
    VG_NAME = '1ffead52-7363-4968-a8c7-3bc34504d452'
    DEVICES = ['360014054d75cb132d474c0eae9825766']
    LV_NAME = '54e3378a-b2f6-46ff-b2da-a9c82522a55e'
    LV_SIZE_MB = 1024

    def validate_properties(self, props, obj):
        for var, val in props.items():
            self.assertEqual(val, getattr(obj, var))

    @contextmanager
    def base_config(self):
        """
        Create a simple volume group from a single 10G LUN.

        lvm.createVG('1ffead52-7363-4968-a8c7-3bc34504d452',
                     ['360014054d75cb132d474c0eae9825766'],
                     blockSD.STORAGE_UNREADY_DOMAIN_TAG,
                     blockSD.VG_METADATASIZE)

        print lvm.getVG('1ffead52-7363-4968-a8c7-3bc34504d452')
        VG(uuid='15hlPF-V3eG-F9Cp-SGtu-4Mq0-28Do-HC806y',
           name='1ffead52-7363-4968-a8c7-3bc34504d452',
           attr=VG_ATTR(permission='w', resizeable='z', exported='-',
                        partial='-', allocation='n', clustered='-'),
           size='10334765056', free='10334765056', extent_size='134217728',
           extent_count='77', free_count='77',
           tags=('RHAT_storage_domain_UNREADY',), vg_mda_size='134217728',
           vg_mda_free='67107328', lv_count='0', pv_count='1',
           pv_name=('/dev/mapper/360014054d75cb132d474c0eae9825766',),
           writeable=True, partial='OK')

        print lvm.getPV('360014054d75cb132d474c0eae9825766')
        PV(uuid='fIRjbD-usOA-tYgW-b2Uz-oUly-AJ49-bMMjYe',
           name='/dev/mapper/360014054d75cb132d474c0eae9825766',
           size='10334765056', vg_name='1ffead52-7363-4968-a8c7-3bc34504d452',
           vg_uuid='15hlPF-V3eG-F9Cp-SGtu-4Mq0-28Do-HC806y',
           pe_start='138412032', pe_count='77', pe_alloc_count='0',
           mda_count='2', dev_size='10737418240',
           guid='360014054d75cb132d474c0eae9825766')
        """
        with namedTemporaryDir() as tmpdir:
            lvm = FakeLVM(tmpdir)
            lvm.createVG(self.VG_NAME, self.DEVICES,
                         blockSD.STORAGE_UNREADY_DOMAIN_TAG,
                         blockSD.VG_METADATASIZE)
            yield lvm

    def test_vg_properties(self):
        expected = dict(
            name=self.VG_NAME,
            size='10334765056',
            free='10334765056',
            extent_size='134217728',
            extent_count='77',
            free_count='77',
            tags=(blockSD.STORAGE_UNREADY_DOMAIN_TAG,),
            vg_mda_size='134217728',
            lv_count='0',
            pv_count='1',
            writeable=True,
            partial='OK',
            pv_name=tuple(('/dev/mapper/%s' % d for d in self.DEVICES)))
        with self.base_config() as lvm:
            vg = lvm.getVG(self.VG_NAME)
            self.validate_properties(expected, vg)

    def test_vg_attributes(self):
        expected = real_lvm.VG_ATTR(permission='w', resizeable='z',
                                    exported='-', partial='-',
                                    allocation='n', clustered='-')
        with self.base_config() as lvm:
            vg = lvm.getVG(self.VG_NAME)
            self.assertEqual(expected, vg.attr)

    def test_vg_mda_free(self):
        # It is too complex to emulate vg_mda_free and at this point we do not
        # rely on this value.  For this reason, FakeLVM sets it to None.
        with self.base_config() as lvm:
            vg = lvm.getVG(self.VG_NAME)
            self.assertEqual(None, vg.vg_mda_free)

    def test_pv_properties(self):
        expected = dict(
            name='/dev/mapper/%s' % self.DEVICES[0],
            size='10334765056',
            vg_name=self.VG_NAME,
            pe_count='77',
            pe_alloc_count='0',
            mda_count='2',
            dev_size='10737418240',
            guid=self.DEVICES[0],
        )
        with self.base_config() as lvm:
            pv = lvm.getPV(self.DEVICES[0])
            self.validate_properties(expected, pv)

    def test_pv_vg_uuid(self):
        with self.base_config() as lvm:
            vg = lvm.getVG(self.VG_NAME)
            pv = lvm.getPV(self.DEVICES[0])
            self.assertEqual(pv.vg_uuid, vg.uuid)

    def test_pv_pe_start(self):
        # As documented in FakeLVM, pe_start is not emulated and should be None
        with self.base_config() as lvm:
            pv = lvm.getPV(self.DEVICES[0])
            self.assertIsNone(pv.pe_start)

    def test_lv_properties(self):
        """
        Create a single logical volume on the base configuration.

        lvm.createLV('1ffead52-7363-4968-a8c7-3bc34504d452',
                     '54e3378a-b2f6-46ff-b2da-a9c82522a55e', 1024)

        print lvm.getLV('1ffead52-7363-4968-a8c7-3bc34504d452',
                        '54e3378a-b2f6-46ff-b2da-a9c82522a55e')
        LV(uuid='89tSvh-HJl5-SO2K-O36t-3qkj-Zo2J-yugkjk',
           name='54e3378a-b2f6-46ff-b2da-a9c82522a55e',
           vg_name='1ffead52-7363-4968-a8c7-3bc34504d452',
           attr=LV_ATTR(voltype='-', permission='w', allocations='i',
                        fixedminor='-', state='a', devopen='-', target='-',
                        zero='-'),
           size='1073741824', seg_start_pe='0',
           devices='/dev/mapper/360014054d75cb132d474c0eae9825766(0)',
           tags=(), writeable=True, opened=False, active=True)
        """
        props = dict(
            name=self.LV_NAME,
            vg_name=self.VG_NAME,
            size='1073741824',
            seg_start_pe='0',
            tags=(),
            writeable=True,
            opened=False,
            active=True,
        )
        attrs = real_lvm.LV_ATTR(voltype='-', permission='w', allocations='i',
                                 fixedminor='-', state='a', devopen='-',
                                 target='-', zero='-')
        with self.base_config() as lvm:
            lvm.createLV(self.VG_NAME, self.LV_NAME, str(self.LV_SIZE_MB))
            lv = lvm.getLV(self.VG_NAME, self.LV_NAME)
            self.validate_properties(props, lv)
            self.assertEqual(attrs, lv.attr)

            # As documented in FakeLVM, devices is not emulated and is None
            self.assertIsNone(lv.devices)

    def test_lv_no_activate(self):
        """
        Create a logical volume with activate=False.

        lvm.createLV('1ffead52-7363-4968-a8c7-3bc34504d452',
                     '54e3378a-b2f6-46ff-b2da-a9c82522a55e',
                     '1024', activate=False)

        print lvm.getLV('1ffead52-7363-4968-a8c7-3bc34504d452',
                        '54e3378a-b2f6-46ff-b2da-a9c82522a55e')
        LV(uuid='dDbzkJ-RSAQ-0CdJ-1pTD-OdqZ-3my2-v3hSUT',
           name='54e3378a-b2f6-46ff-b2da-a9c82522a55e',
           vg_name='1ffead52-7363-4968-a8c7-3bc34504d452',
           attr=LV_ATTR(voltype='-', permission='w', allocations='i',
                        fixedminor='-', state='-', devopen='-', target='-',
                        zero='-'),
           size='1073741824', seg_start_pe='0',
           devices='/dev/mapper/360014054d75cb132d474c0eae9825766(0)', tags=(),
           writeable=True, opened=False, active=False)
        """
        with self.base_config() as lvm:
            lvm.createLV(self.VG_NAME, self.LV_NAME, str(self.LV_SIZE_MB),
                         activate=False)
            lv = lvm.getLV(self.VG_NAME, self.LV_NAME)
            self.assertFalse(lv.active)
            self.assertEqual('-', lv.attr.state)
            self.assertFalse(os.path.exists(lvm.lvPath(self.VG_NAME,
                                                       self.LV_NAME)))

    def test_lv_initialtags(self):
        """
        Create a logical volume with multiple tags.

        lvm.createLV('1ffead52-7363-4968-a8c7-3bc34504d452',
                     '54e3378a-b2f6-46ff-b2da-a9c82522a55e',
                     '1024', initialTags=(sc.TAG_VOL_UNINIT, "FOO"))

        print lvm.getLV('1ffead52-7363-4968-a8c7-3bc34504d452',
                        '54e3378a-b2f6-46ff-b2da-a9c82522a55e')
        LV(uuid='yJngqd-2kRy-9ogk-D7Gk-v3b1-RDQm-cb1bJv',
           name='54e3378a-b2f6-46ff-b2da-a9c82522a55e',
           vg_name='1ffead52-7363-4968-a8c7-3bc34504d452',
           attr=LV_ATTR(voltype='-', permission='w', allocations='i',
                        fixedminor='-', state='a', devopen='-', target='-',
                        zero='-'), size='1073741824', seg_start_pe='0',
           devices='/dev/mapper/360014054d75cb132d474c0eae9825766(0)',
           tags=('OVIRT_VOL_INITIALIZING', 'FOO'), writeable=True,
           opened=False, active=True)
        """
        with self.base_config() as lvm:
            lvm.createLV(self.VG_NAME, self.LV_NAME, str(self.LV_SIZE_MB),
                         initialTags=(sc.TAG_VOL_UNINIT, "FOO"))
            lv = lvm.getLV(self.VG_NAME, self.LV_NAME)
            self.assertEqual((sc.TAG_VOL_UNINIT, "FOO"), lv.tags)

    def test_changelvtags(self):
        """
        Create a logical volume with an initial tag and replace it.
        """
        with self.base_config() as lvm:
            lvm.createLV(self.VG_NAME, self.LV_NAME, str(self.LV_SIZE_MB),
                         initialTags=(sc.TAG_VOL_UNINIT,))
            deltags = (sc.TAG_VOL_UNINIT,)
            addtags = ("FOO",)
            lvm.changeLVTags(self.VG_NAME, self.LV_NAME,
                             delTags=deltags, addTags=addtags)
            lv = lvm.getLV(self.VG_NAME, self.LV_NAME)
            self.assertEqual(addtags, lv.tags)

    def test_activatelv(self):
        """
        Create an inactive LV and then activate it.

        lvm.createLV('1ffead52-7363-4968-a8c7-3bc34504d452',
                     '54e3378a-b2f6-46ff-b2da-a9c82522a55e',
                     '1024', activate=False)
        lvm.activateLVs('1ffead52-7363-4968-a8c7-3bc34504d452',
                        ['54e3378a-b2f6-46ff-b2da-a9c82522a55e'])

        print lvm.getLV('1ffead52-7363-4968-a8c7-3bc34504d452',
                        '54e3378a-b2f6-46ff-b2da-a9c82522a55e')
        LV(uuid='P8Y7p8-V13j-rWDp-FvGk-5AX1-zXhp-ZU4K2G',
           name='54e3378a-b2f6-46ff-b2da-a9c82522a55e',
           vg_name='1ffead52-7363-4968-a8c7-3bc34504d452',
           attr=LV_ATTR(voltype='-', permission='w', allocations='i',
                        fixedminor='-', state='a', devopen='-', target='-',
                        zero='-'),
           size='1073741824', seg_start_pe='0',
           devices='/dev/mapper/360014054d75cb132d474c0eae9825766(0)', tags=(),
           writeable=True, opened=False, active=True)
        """
        with self.base_config() as lvm:
            lvm.createLV(self.VG_NAME, self.LV_NAME, str(self.LV_SIZE_MB),
                         activate=False)
            lv_path = lvm.lvPath(self.VG_NAME, self.LV_NAME)
            self.assertFalse(os.path.exists(lv_path))
            lvm.activateLVs(self.VG_NAME, [self.LV_NAME])
            lv = lvm.getLV(self.VG_NAME, self.LV_NAME)
            self.assertTrue(lv.active)
            self.assertEqual('a', lv.attr.state)
            self.assertTrue(os.path.exists(lv_path))

    def test_lv_io(self):
        with self.base_config() as lvm:
            msg = "Hello World!"
            lvm.createLV(self.VG_NAME, self.LV_NAME, str(self.LV_SIZE_MB),
                         activate=True)
            lv_path = lvm.lvPath(self.VG_NAME, self.LV_NAME)
            self.assertEqual(MB * self.LV_SIZE_MB,
                             os.stat(lv_path).st_size)
            with open(lv_path, 'w') as f:
                f.write(msg)
            with open(lv_path) as f:
                self.assertEqual(msg, f.read())

    def test_changevgtags(self):
        with self.base_config() as lvm:
            deltags = (blockSD.STORAGE_UNREADY_DOMAIN_TAG,)
            addtags = ("FOO",)
            lvm.changeVGTags(self.VG_NAME, delTags=deltags, addTags=addtags)
            vg = lvm.getVG(self.VG_NAME)
            self.assertEqual(addtags, vg.tags)

    def test_lvsbytag(self):
        with self.base_config() as lvm:
            lvm.createLV(self.VG_NAME, self.LV_NAME, str(self.LV_SIZE_MB))
            lvm.changeLVTags(self.VG_NAME, self.LV_NAME, addTags=('foo',))
            lvs = lvm.lvsByTag(self.VG_NAME, 'foo')
            self.assertEqual(1, len(lvs))
            self.assertEqual(self.LV_NAME, lvs[0].name)
            self.assertEqual([], lvm.lvsByTag(self.VG_NAME, 'bar'))


@expandPermutations
class FakeLVMGeneralTests(VdsmTestCase):

    def test_lvpath(self):
        with namedTemporaryDir() as tmpdir:
            lvm = FakeLVM(tmpdir)
            vg_name = 'foo'
            lv_name = 'bar'
            expected = os.path.join(tmpdir, 'dev', vg_name, lv_name)
            self.assertEqual(expected, lvm.lvPath(vg_name, lv_name))

    @permutations([
        [se.VolumeGroupDoesNotExist, 'getVG', ['vg']],
        [se.CannotActivateLogicalVolume, 'activateLVs', ['vg', ['lv']]],
        [se.MissingTagOnLogicalVolume, 'addtag', ['vg', 'lv', 'tag']],
        [se.CannotCreateLogicalVolume, 'createLV', ['vg', 'lv', '1024']],
        [se.LogicalVolumeDoesNotExistError, 'getLV', ['vg', 'lv']],
        [se.InaccessiblePhysDev, 'getPV', ['pv']],
        [se.LogicalVolumeReplaceTagError, 'changeLVTags', ['vg', 'lv']],
    ])
    def test_bad_args(self, exception, fn, args):
        with namedTemporaryDir() as tmpdir:
            lvm = FakeLVM(tmpdir)
            lvm_fn = getattr(lvm, fn)
            self.assertRaises(exception, lvm_fn, *args)

    def test_lv_size_rounding(self):
        vg_name = 'foo'
        lv_name = 'bar'
        devices = ['360014054d75cb132d474c0eae9825766']
        with namedTemporaryDir() as tmpdir:
            lvm = FakeLVM(tmpdir)
            lvm.createVG(vg_name, devices, blockSD.STORAGE_UNREADY_DOMAIN_TAG,
                         blockSD.VG_METADATASIZE)
            lvm.createLV(vg_name, lv_name, sc.VG_EXTENT_SIZE_MB - 1)
            lv = lvm.getLV(vg_name, lv_name)
            self.assertEqual(sc.VG_EXTENT_SIZE_MB * MB, int(lv.size))


class FakeResourceManagerTests(VdsmTestCase):

    def test_acquire_contextmanager(self):
        expected_calls = []
        rm = FakeResourceManager()
        acquire_args = ('ns', 'name', 'locktype')
        with rm.acquireResource(*acquire_args):
            expected_calls.append(('acquireResource', acquire_args, {}))
            self.assertEqual(expected_calls, rm.__calls__)
        expected_calls.append(('releaseResource', acquire_args, {}))
        self.assertEqual(expected_calls, rm.__calls__)


class TestFakeStorageDomainCache(VdsmTestCase):

    def test_domain_does_not_exist(self):
        sdc = FakeStorageDomainCache()
        self.assertRaises(se.StorageDomainDoesNotExist, sdc.produce, "uuid")

    def test_produce(self):
        sdc = FakeStorageDomainCache()
        sdc.domains["uuid"] = "fake domain"
        self.assertEqual("fake domain", sdc.produce("uuid"))

    def test_produce_manifest(self):
        sdc = FakeStorageDomainCache()
        sdc.domains["uuid"] = FakeSD("fake manifest")
        self.assertEqual("fake manifest", sdc.produce_manifest("uuid"))

    def test_manually_remove_domain(self):
        sdc = FakeStorageDomainCache()
        sdc.domains["uuid"] = "fake domain"
        sdc.manuallyRemoveDomain("uuid")
        self.assertRaises(se.StorageDomainDoesNotExist, sdc.produce, "uuid")

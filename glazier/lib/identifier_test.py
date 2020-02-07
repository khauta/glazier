# Lint as: python3
# Copyright 2019 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for glazier.lib.winpe."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from absl.testing import absltest
from pyfakefs import fake_filesystem
from glazier.lib import identifier
import mock

TEST_UUID = identifier.uuid.UUID('12345678123456781234567812345678')
TEST_SERIAL = '1A19SEL90000R90DZN7A'
TEST_ID = TEST_SERIAL+'-'+str(TEST_UUID)[:7]


class IdentifierTest(absltest.TestCase):

  def setUp(self):
    super(IdentifierTest, self).setUp()
    mock_wmi = mock.patch.object(
        identifier.hw_info.wmi_query, 'WMIQuery', autospec=True)
    self.addCleanup(mock_wmi.stop)
    mock_wmi.start()
    self.identifier = identifier.ImageID()

  @mock.patch.object(
      identifier.hw_info.HWInfo, 'BiosSerial', autospec=True)
  @mock.patch.object(identifier.uuid, 'uuid4', autospec=True)
  def test_generate_id(self, mock_uuid, mock_serial):
    mock_uuid.return_value = str(TEST_UUID)[:7]
    mock_serial.return_value = TEST_SERIAL
    self.assertEqual(self.identifier._generate_id(), TEST_ID)

  @mock.patch.object(identifier.registry, 'Registry', autospec=True)
  def test_write_reg(self, reg):
    self.identifier._write_reg('some_name', 'some_value')
    reg.assert_called_with('HKLM')
    reg.return_value.SetKeyValue.assert_has_calls([
        mock.call(
            key_path=identifier.constants.REG_ROOT,
            key_name='some_name',
            key_value='some_value',
            key_type='REG_SZ',
            use_64bit=identifier.constants.USE_REG_64),
    ])

  @mock.patch.object(identifier.registry, 'Registry', autospec=True)
  def test_write_reg_error(self, reg):
    reg.return_value.SetKeyValue.side_effect = identifier.registry.RegistryError
    self.assertRaises(identifier.Error, self.identifier._write_reg, '', '')

  @mock.patch.object(identifier.ImageID, '_write_reg', autospec=True)
  @mock.patch.object(identifier.ImageID, '_generate_id', autospec=True)
  @mock.patch.object(identifier.registry, 'Registry', autospec=True)
  def test_set_id(self, unused_reg, genid, write):
    genid.return_value = TEST_ID
    self.identifier._set_id()
    write.assert_called_with(self.identifier, 'image_id', TEST_ID)
    self.assertEqual(self.identifier._set_id(), TEST_ID)

  @mock.patch.object(identifier.registry, 'Registry', autospec=True)
  def test_get_id(self, reg):
    reg.return_value.GetKeyValue.return_value = TEST_ID
    self.assertEqual(self.identifier._get_id(), TEST_ID)
    reg.assert_called_with('HKLM')
    reg.return_value.GetKeyValue.assert_called_with(
        key_path=identifier.constants.REG_ROOT,
        key_name='image_id',
        use_64bit=identifier.constants.USE_REG_64)

  @mock.patch.object(identifier.registry, 'Registry', autospec=True)
  def test_get_id_none(self, reg):
    reg.return_value.GetKeyValue.side_effect = identifier.registry.RegistryError
    self.assertEqual(self.identifier._get_id(), None)

  @mock.patch.object(identifier.ImageID, '_write_reg', autospec=True)
  @mock.patch.object(identifier.registry, 'Registry', autospec=True)
  def test_check_file(self, unused_reg, write):
    fs = fake_filesystem.FakeFilesystem()
    identifier.open = fake_filesystem.FakeFileOpen(fs)
    identifier.os = fake_filesystem.FakeOsModule(fs)
    fs.CreateFile(
        '/%s/build_info.yaml' % identifier.constants.SYS_CACHE,
        contents=
        '{BUILD: {opt 1: true, TIMER_opt 2: some value, image_id: 12345}}\n')
    self.identifier._check_file()
    write.assert_called_with(self.identifier, 'image_id', 12345)
    self.assertEqual(self.identifier._check_file(), 12345)

  @mock.patch.object(identifier.registry, 'Registry', autospec=True)
  def test_check_file_no_id(self, unused_reg):
    fs = fake_filesystem.FakeFilesystem()
    identifier.open = fake_filesystem.FakeFileOpen(fs)
    identifier.os = fake_filesystem.FakeOsModule(fs)
    fs.CreateFile(
        '/%s/build_info.yaml' % identifier.constants.SYS_CACHE,
        contents=
        '{BUILD: {opt 1: true, TIMER_opt 2: some value, image_num: 12345}}\n')
    self.assertRaises(identifier.Error, self.identifier._check_file)

  @mock.patch.object(identifier.registry, 'Registry', autospec=True)
  def test_check_file_error(self, unused_reg):
    fs = fake_filesystem.FakeFilesystem()
    identifier.open = fake_filesystem.FakeFileOpen(fs)
    identifier.os = fake_filesystem.FakeOsModule(fs)
    self.assertRaises(identifier.Error, self.identifier._check_file)

  @mock.patch.object(identifier.ImageID, '_get_id', autospec=True)
  def test_check_id_get(self, getid):
    getid.return_value = TEST_ID
    self.assertEqual(self.identifier.check_id(), TEST_ID)

  @mock.patch.object(identifier.ImageID, '_set_id', autospec=True)
  @mock.patch.object(identifier.ImageID, '_get_id', autospec=True)
  @mock.patch.object(identifier.winpe, 'check_winpe', autospec=True)
  def test_check_id_set(self, wpe, getid, setid):
    getid.return_value = None
    wpe.return_value = True
    self.identifier.check_id()
    self.assertTrue(setid.called)

  @mock.patch.object(identifier.ImageID, '_check_file', autospec=True)
  @mock.patch.object(identifier.ImageID, '_get_id', autospec=True)
  @mock.patch.object(identifier.winpe, 'check_winpe', autospec=True)
  def test_check_id_file(self, wpe, getid, checkfile):
    getid.return_value = None
    wpe.return_value = False
    checkfile.return_value = TEST_ID
    self.assertEqual(self.identifier.check_id(), TEST_ID)

if __name__ == '__main__':
  absltest.main()

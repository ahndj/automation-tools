#!/usr/bin/env python

from collections import namedtuple
from datetime import datetime
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import vcr

from transfers import transfer
from transfers import models

AM_URL = 'http://127.0.0.1'
SS_URL = 'http://127.0.0.1:8000'
USER = 'demo'
API_KEY = '1c34274c0df0bca7edf9831dd838b4a6345ac2ef'

TS_LOCATION_UUID = '2a3d8d39-9cee-495e-b7ee-5e629254934d'
PATH_PREFIX = b'SampleTransfers'
DEPTH = 1
COMPLETED = set()
FILES = False
TimestampsMock = namedtuple('TimestampsMock', ['path', 'started_timestamp'])

engine = create_engine('sqlite:///:memory:')
models.Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()


class TestAutomateTransfers(unittest.TestCase):
    @vcr.use_cassette('fixtures/vcr_cassettes/get_status_transfer.yaml')
    def test_get_status_transfer(self):
        transfer_uuid = 'dfc8cf5f-b5b1-408c-88b1-34215964e9d6'
        transfer_name = 'test1'
        info = transfer.get_status(AM_URL, USER, API_KEY, transfer_uuid, 'transfer', session)
        assert isinstance(info, dict)
        assert info['status'] == 'USER_INPUT'
        assert info['type'] == 'transfer'
        assert info['name'] == transfer_name
        assert info['uuid'] == transfer_uuid
        assert info['directory'] == transfer_name
        assert info['path'] == '/var/archivematica/sharedDirectory/watchedDirectories/activeTransfers/standardTransfer/test1/'

    @vcr.use_cassette('fixtures/vcr_cassettes/get_status_transfer_to_ingest.yaml')
    def test_get_status_transfer_to_ingest(self):
        # Reference values
        transfer_uuid = 'dfc8cf5f-b5b1-408c-88b1-34215964e9d6'
        unit_name = 'test1'
        sip_uuid = 'f2248e2a-b593-43db-b60c-fa8513021785'
        # Setup transfer in DB
        new_transfer = models.Unit(uuid=transfer_uuid, path=b'/foo', unit_type='transfer', status='PROCESSING', current=True)
        session.add(new_transfer)
        session.commit()

        # Run test
        info = transfer.get_status(AM_URL, USER, API_KEY, transfer_uuid, 'transfer', session)
        # Verify
        assert isinstance(info, dict)
        assert info['status'] == 'USER_INPUT'
        assert info['type'] == 'SIP'
        assert info['name'] == unit_name
        assert info['uuid'] == sip_uuid
        assert info['directory'] == unit_name + '-' + sip_uuid
        assert info['path'] == '/var/archivematica/sharedDirectory/watchedDirectories/workFlowDecisions/selectFormatIDToolIngest/test1-f2248e2a-b593-43db-b60c-fa8513021785/'

    @vcr.use_cassette('fixtures/vcr_cassettes/get_status_ingest.yaml')
    def test_get_status_ingest(self):
        sip_uuid = 'f2248e2a-b593-43db-b60c-fa8513021785'
        sip_name = 'test1'
        info = transfer.get_status(AM_URL, USER, API_KEY, sip_uuid, 'ingest', session)
        assert isinstance(info, dict)
        assert info['status'] == 'USER_INPUT'
        assert info['type'] == 'SIP'
        assert info['name'] == sip_name
        assert info['uuid'] == sip_uuid
        assert info['directory'] == sip_name + '-' + sip_uuid
        assert info['path'] == '/var/archivematica/sharedDirectory/watchedDirectories/workFlowDecisions/selectFormatIDToolIngest/test1-f2248e2a-b593-43db-b60c-fa8513021785/'

    @vcr.use_cassette('fixtures/vcr_cassettes/get_status_no_unit.yaml')
    def test_get_status_no_unit(self):
        transfer_uuid = 'deadc0de-c0de-c0de-c0de-deadc0dec0de'
        info = transfer.get_status(AM_URL, USER, API_KEY, transfer_uuid, 'transfer', session)
        assert info is None

    @vcr.use_cassette('fixtures/vcr_cassettes/get_status_not_json.yaml')
    def test_get_status_not_json(self):
        transfer_uuid = 'dfc8cf5f-b5b1-408c-88b1-34215964e9d6'
        info = transfer.get_status(AM_URL, USER, API_KEY, transfer_uuid, 'transfer', session)
        assert info is None

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_first_run.yaml')
    def test_get_next_transfer_first_run(self):
        # All default values
        # Test
        path = transfer.get_next_transfer(SS_URL, TS_LOCATION_UUID, PATH_PREFIX, DEPTH, COMPLETED, FILES)
        # Verify
        assert path == b'SampleTransfers/BagTransfer'

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_existing_set.yaml')
    def test_get_next_transfer_existing_set(self):
        # Set completed set
        completed = {b'SampleTransfers/BagTransfer'}
        # Test
        path = transfer.get_next_transfer(SS_URL, TS_LOCATION_UUID, PATH_PREFIX, DEPTH, completed, FILES)
        # Verify
        assert path == b'SampleTransfers/CSVmetadata'

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_depth.yaml')
    def test_get_next_transfer_depth(self):
        # Set depth
        depth = 2
        # Test
        path = transfer.get_next_transfer(SS_URL, TS_LOCATION_UUID, PATH_PREFIX, depth, COMPLETED, FILES)
        # Verify
        assert path == b'SampleTransfers/BagTransfer/data'

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_no_prefix.yaml')
    def test_get_next_transfer_no_prefix(self):
        # Set no prefix
        path_prefix = b''
        # Test
        path = transfer.get_next_transfer(SS_URL, TS_LOCATION_UUID, path_prefix, DEPTH, COMPLETED, FILES)
        # Verify
        assert path == b'OPF format-corpus'

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_all_complete.yaml')
    def test_get_next_transfer_all_complete(self):
        # Set completed set to be all elements
        completed = {b'SampleTransfers/BagTransfer', b'SampleTransfers/CSVmetadata', b'SampleTransfers/DigitizationOutput', b'SampleTransfers/DSpaceExport', b'SampleTransfers/Images', b'SampleTransfers/ISODiskImage', b'SampleTransfers/Multimedia', b'SampleTransfers/OCRImage', b'SampleTransfers/OfficeDocs', b'SampleTransfers/RawCameraImages', b'SampleTransfers/structMapSample'}
        # Test
        path = transfer.get_next_transfer(SS_URL, TS_LOCATION_UUID, PATH_PREFIX, DEPTH, completed, FILES)
        # Verify
        assert path is None

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_bad_source.yaml')
    def test_get_next_transfer_bad_source(self):
        # Set bad TS Location UUID
        ts_location_uuid = 'badd8d39-9cee-495e-b7ee-5e6292549bad'
        # Test
        path = transfer.get_next_transfer(SS_URL, ts_location_uuid, PATH_PREFIX, DEPTH, COMPLETED, FILES)
        # Verify
        assert path is None

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_files.yaml')
    def test_get_next_transfer_files(self):
        # See files
        files = True
        completed = {b'SampleTransfers/BagTransfer'}
        # Test
        path = transfer.get_next_transfer(SS_URL, TS_LOCATION_UUID, PATH_PREFIX, DEPTH, completed, files)
        # Verify
        assert path == b'SampleTransfers/BagTransfer.zip'

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_updated_timestamp.yaml')
    def test_get_next_transfer_updated_timestamp(self):
        # Set timestamps
        completed = {b'SampleTransfers/BagTransfer', b'SampleTransfers/CSVmetadata', b'SampleTransfers/DigitizationOutput', b'SampleTransfers/DSpaceExport', b'SampleTransfers/Images', b'SampleTransfers/ISODiskImage', b'SampleTransfers/Multimedia', b'SampleTransfers/OCRImage', b'SampleTransfers/OfficeDocs', b'SampleTransfers/RawCameraImages', b'SampleTransfers/structMapSample'}
        started_timestamps = [
            TimestampsMock(b'SampleTransfers/BagTransfer', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/Images', datetime(2010, 1, 1)),
        ]
        # Test
        path = transfer.get_next_transfer(SS_URL, TS_LOCATION_UUID, PATH_PREFIX, DEPTH, completed, FILES, started_timestamps)
        # Verify
        assert path == b'SampleTransfers/Images'

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_no_new_timestamp.yaml')
    def test_get_next_transfer_no_new_timestamp(self):
        # Set timestamps
        completed = {b'SampleTransfers/BagTransfer', b'SampleTransfers/CSVmetadata', b'SampleTransfers/DigitizationOutput', b'SampleTransfers/DSpaceExport', b'SampleTransfers/Images', b'SampleTransfers/ISODiskImage', b'SampleTransfers/Multimedia', b'SampleTransfers/OCRImage', b'SampleTransfers/OfficeDocs', b'SampleTransfers/RawCameraImages', b'SampleTransfers/structMapSample'}
        started_timestamps = [
            TimestampsMock(b'SampleTransfers/BagTransfer', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/CSVmetadata', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/DigitizationOutput', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/DSpaceExport', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/Images', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/ISODiskImage', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/Multimedia', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/OCRImage', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/OfficeDocs', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/RawCameraImages', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/structMapSample', datetime(2020, 1, 1)),
        ]
        # Test
        path = transfer.get_next_transfer(SS_URL, TS_LOCATION_UUID, PATH_PREFIX, DEPTH, completed, FILES, started_timestamps)
        # Verify
        assert path is None

    @vcr.use_cassette('fixtures/vcr_cassettes/get_next_transfer_missing_timestamps.yaml')
    def test_get_next_transfer_missing_timestamps(self):
        # Set timestamps
        completed = {b'SampleTransfers/BagTransfer', b'SampleTransfers/CSVmetadata', b'SampleTransfers/DigitizationOutput', b'SampleTransfers/DSpaceExport', b'SampleTransfers/Images', b'SampleTransfers/ISODiskImage', b'SampleTransfers/Multimedia', b'SampleTransfers/OCRImage', b'SampleTransfers/OfficeDocs', b'SampleTransfers/RawCameraImages', b'SampleTransfers/structMapSample'}
        started_timestamps = [
            TimestampsMock(b'SampleTransfers/BagTransfer', None),
            TimestampsMock(b'SampleTransfers/CSVmetadata', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/DigitizationOutput', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/DSpaceExport', None),
            TimestampsMock(b'SampleTransfers/Images', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/ISODiskImage', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/Multimedia', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/OCRImage', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/OfficeDocs', datetime(2020, 1, 1)),
            TimestampsMock(b'SampleTransfers/RawCameraImages', None),
            TimestampsMock(b'SampleTransfers/structMapSample', datetime(2020, 1, 1)),
        ]
        # Test
        path = transfer.get_next_transfer(SS_URL, TS_LOCATION_UUID, PATH_PREFIX, DEPTH, completed, FILES, started_timestamps)
        # Verify
        assert path is None

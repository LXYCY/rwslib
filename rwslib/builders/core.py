# -*- coding: utf-8 -*-
__author__ = 'glow'

from rwslib.builders.clinicaldata import ClinicalData
from rwslib.builders.admindata import AdminData
from rwslib.builders.metadata import Study
from rwslib.builders.common import ODMElement, now_to_iso8601, indent
from rwslib.builders.constants import GranularityType
from xml.etree import cElementTree as ET

import uuid
import datetime

class ODM(ODMElement):
    """Models the ODM object"""
    FILETYPE_TRANSACTIONAL = 'Transactional'
    FILETYPE_SNAPSHOT = 'Snapshot'
    VALID_ODM_VERSIONS = ("1.2", "1.2.1", "1.3", "1.3.1", "1.3.2")

    def __init__(self,
                 originator, description="",
                 creationdatetime=None,
                 fileoid=None,
                 filetype=None,
                 granularity=GranularityType.AllClinicalData,
                 source_system=None,
                 source_system_version=None,
                 odm_version=None,
                 as_of_datetime=None):
        """
        :param GranularityType granularity: Specify the GranularityType attribute for this ODM File
        :param str odm_version: Specify the ODMVersion attribute for this ODM File (default is "1.3",
            should be one of "1.2", "1.2.1", "1.3", "1.3.1", "1.3.2"
        :param Union[datetime.datetime, datetime.date] as_of_datetime: Specify the AsOfDateTime attribute for this ODM File
        :param GranularityType granularity: Specify the GranularityType attribute for this ODM File
        :param str source_system: Name of the SourceSystem that generated this file
        :param str source_system_version: Version of the SourceSystem that generated this file
        :param str originator: The organization that generated the ODM file.
        :param str description: The sender should use the Description attribute to record any information that will 
            help the receiver interpret the document correctly.
        :param str creationdatetime: Time of creation of the file containing the document.
        :param str fileoid: A unique identifier for this file.
        :param str filetype: Snapshot means that the document contains only the current state of the data and metadata 
            it describes, and no transactional history. A Snapshot document may include only one instruction per 
            data point. For clinical data, TransactionType in a Snapshot file must either not be present or be Insert. 
            Transactional means that the document may contain more than one instruction per data point. 
            Use a Transactional document to send both what the current state of the data is, and how it came to be there.
        """
        self.originator = originator  # Required
        self.description = description
        self.creationdatetime = creationdatetime or now_to_iso8601()
        self.source_system = source_system
        self.source_system_version = source_system_version
        # filetype will always be "Transactional"
        # ODM version will always be 1.3
        # Granularity="SingleSubject"
        # AsOfDateTime always OMITTED (it's optional)
        self.clinical_data = []
        self.study = None
        self.filetype = ODM.FILETYPE_TRANSACTIONAL if filetype is None else ODM.FILETYPE_SNAPSHOT
        self.admindata = None
        # Create unique fileoid if none given
        self.fileoid = str(uuid.uuid4()) if fileoid is None else fileoid
        self._granularity_type = None
        self._odm_version = "1.3"
        self._as_of_datetime = None
        if granularity:
            self.granularity_type = granularity
        if odm_version:
            self.odm_version = odm_version
        if as_of_datetime:
            self.as_of_datetime = as_of_datetime

    @property
    def odm_version(self):
        return self._odm_version

    @odm_version.setter
    def odm_version(self, value):
        # TODO: should we warn for values not supported by RWS?
        if not value in self.VALID_ODM_VERSIONS:
            raise ValueError("No such supported ODMVersion '%s'" % value)
        self._odm_version = value

    @property
    def as_of_datetime(self):
        return self._as_of_datetime

    @as_of_datetime.setter
    def as_of_datetime(self, value):
        if not isinstance(value, (datetime.datetime, datetime.date,)):
            raise ValueError("Unexpected format for AsOfDateTime")
        # TODO: should we warn for values that are greater than CreationDateTime
        if isinstance(value, (datetime.date, datetime.datetime,)):
            self._as_of_datetime = value.isoformat()

    @property
    def granularity_type(self):
        return self._granularity_type

    @granularity_type.setter
    def granularity_type(self, value):
        if not isinstance(value, (GranularityType)):
            raise ValueError("Should be an instance of GranularityType not {}".format(type(value)))
        self._granularity_type = value

    def __lshift__(self, other):
        """Override << operator"""
        if not isinstance(other, (ClinicalData, Study, AdminData)):
            raise ValueError("ODM object can only receive ClinicalData, Study or AdminData object")
        # per the ODM, we can have multiple ClinicalData elements
        self.set_list_attribute(other, ClinicalData, 'clinical_data')
        # per the ODM, we can have multiple Study elements, but owing to the context we restrict it here
        self.set_single_attribute(other, Study, 'study')
        self.set_single_attribute(other, AdminData, 'admindata')

        return other

    def getroot(self):
        """Build XML object, return the root"""
        builder = ET.TreeBuilder()
        self.build(builder)
        return builder.close()

    def build(self, builder):
        """Build XML object, return the root, this is a copy for consistency and testing"""
        params = dict(ODMVersion=self.odm_version,
                      FileType=self.filetype,
                      CreationDateTime=self.creationdatetime,
                      Originator=self.originator,
                      FileOID=self.fileoid,
                      xmlns="http://www.cdisc.org/ns/odm/v1.3",
                      )
        if self.granularity_type:
            params['Granularity'] = self.granularity_type.value
        if self.source_system:
            params['SourceSystem'] = self.source_system

        if self.source_system_version:
            params['SourceSystemVersion'] = self.source_system_version
        params['xmlns:mdsol'] = "http://www.mdsol.com/ns/odm/metadata"

        if self.description:
            params['Description'] = self.description

        if self.as_of_datetime:
            params['AsOfDateTime'] = self.as_of_datetime

        builder.start("ODM", params)

        # Ask the children
        if self.study is not None:
            self.study.build(builder)

        if self.clinical_data:
            for clinical_data in self.clinical_data:
                clinical_data.build(builder)

        if self.admindata is not None:
            self.admindata.build(builder)

        builder.end("ODM")
        return builder.close()

    def __str__(self):
        doc = self.getroot()
        indent(doc)
        header = '<?xml version="1.0" encoding="utf-8" ?>\n'
        return header + ET.tostring(doc, encoding='utf-8').decode('utf-8')

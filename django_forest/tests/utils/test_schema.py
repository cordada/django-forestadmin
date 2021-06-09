import copy
import json
import os
import sys

import django
import pytest
from unittest import mock
from django.test import TestCase, override_settings

from django_forest.tests.fixtures.schema import test_schema, test_question_choice_schema, test_exclude_django_contrib_schema
from django_forest.utils.collection import Collection
from django_forest.utils.json_api_serializer import JsonApiSchema
from django_forest.utils.models import Models
from django_forest.utils.schema import Schema


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
class UtilsSchemaTests(TestCase):

    def setUp(self):
        Schema.schema = copy.deepcopy(test_schema)

    def tearDown(self):
        # reset _registry after each test
        Collection._registry = {}
        JsonApiSchema._registry = {}

    @mock.patch.object(django, 'get_version', return_value='9.9.9')
    @mock.patch('importlib.metadata.version', return_value='0.0.0')
    def test_build_schema(self, mock_version, mock_orm_version):
        # reset schema
        Schema.schema = {
            'collections': [],
            'meta': {
                'database_type': 'sqlite',
                'liana': 'django-forest',
                'liana_version': '0.0.0',
                'orm_version': '9.9.9'
            }
        }
        Schema.models = Models.list()
        schema = Schema.build_schema()
        self.assertEqual(schema, test_schema)

    @override_settings(FOREST={'INCLUDED_MODELS': ['Choice']})
    @mock.patch.object(django, 'get_version', return_value='9.9.9')
    @mock.patch('importlib.metadata.version', return_value='0.0.0')
    def test_build_schema_included_models(self, mock_version, mock_orm_version):
        # reset schema
        Schema.schema = {
            'collections': [],
            'meta': {
                'database_type': 'sqlite',
                'liana': 'django-forest',
                'liana_version': '0.0.0',
                'orm_version': '9.9.9'
            }
        }
        Schema.models = Models.list(force=True)
        schema = Schema.build_schema()
        self.assertEqual(schema, test_question_choice_schema)

    @override_settings(FOREST={'EXCLUDED_MODELS': ['Permission', 'Group', 'User', 'ContentType']})
    @mock.patch.object(django, 'get_version', return_value='9.9.9')
    @mock.patch('importlib.metadata.version', return_value='0.0.0')
    def test_build_schema_excluded_models(self, mock_version, mock_orm_version):
        # reset schema
        Schema.schema = {
            'collections': [],
            'meta': {
                'database_type': 'sqlite',
                'liana': 'django-forest',
                'liana_version': '0.0.0',
                'orm_version': '9.9.9'
            }
        }
        Schema.models = Models.list(force=True)
        schema = Schema.build_schema()
        self.assertEqual(schema, test_exclude_django_contrib_schema)

    @pytest.mark.usefixtures('reset_config_dir_import')
    @mock.patch('django_forest.utils.collection.Collection')
    def test_add_smart_features(self, collection_mock):
        Schema.add_smart_features()
        from django_forest.tests.forest import QuestionForest
        from django_forest.tests.models import Question
        collection_mock.register.assert_called_once_with(QuestionForest, Question)

    def test_get_collection(self):
        collection = Schema.get_collection('Question')
        self.assertEqual(collection, [x for x in test_schema['collections'] if x['name'] == 'Question'][0])

    def test_get_collection_inexist(self):
        collection = Schema.get_collection('Foo')
        self.assertEqual(collection, None)

    def test_handle_json_api_serializer(self):
        Schema.handle_json_api_serializer()
        self.assertEqual(len(JsonApiSchema._registry), 16)


# reset forest config dir auto import
@pytest.fixture()
def reset_config_dir_import():
    for key in list(sys.modules.keys()):
        if key.startswith('django_forest.tests.forest'):
            del sys.modules[key]


file_path = os.path.join(os.getcwd(), '.forestadmin-schema.json')


@pytest.fixture()
def dumb_forestadmin_schema():
    schema_data = json.dumps(test_schema, indent=2)
    with open(file_path, 'w') as f:
        f.write(schema_data)


@pytest.fixture()
def invalid_forestadmin_schema():
    schema_data = 'invalid'
    with open(file_path, 'w') as f:
        f.write(schema_data)


class UtilsSchemaFileTests(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def setUp(self):
        Schema.build_schema()
        Schema.add_smart_features()

    def tearDown(self):
        # reset _registry after each test
        Collection._registry = {}
        JsonApiSchema._registry = {}
        Schema.schema_data = None
        if os.path.exists(file_path):
            os.remove(file_path)

    @pytest.mark.usefixtures('reset_config_dir_import')
    def test_handle_schema_file_no_file(self):
        self.assertRaises(Exception, Schema.handle_schema_file())
        self.assertIsNone(Schema.schema_data)
        self.assertEqual(self._caplog.messages, [
            'The .forestadmin-schema.json file does not exist.',
            'The schema cannot be synchronized with Forest Admin servers.'
        ])

    @pytest.mark.usefixtures('reset_config_dir_import')
    @pytest.mark.usefixtures('dumb_forestadmin_schema')
    def test_handle_schema_file_production(self):
        Schema.handle_schema_file()
        self.assertIsNotNone(Schema.schema_data)

    @pytest.mark.usefixtures('reset_config_dir_import')
    @pytest.mark.usefixtures('invalid_forestadmin_schema')
    def test_handle_schema_file_invalid_json_production(self):
        self.assertRaises(Exception, Schema.handle_schema_file())
        self.assertIsNone(Schema.schema_data)
        self.assertEqual(self._caplog.messages, [
            'The content of .forestadmin-schema.json file is not a correct JSON.',
            'The schema cannot be synchronized with Forest Admin servers.'
        ])

    @pytest.mark.usefixtures('reset_config_dir_import')
    @override_settings(DEBUG=True)
    def test_handle_schema_file_debug(self):
        self.maxDiff = None
        Schema.handle_schema_file()
        with open(file_path, 'r') as f:
            data = f.read()
            data = json.loads(data)
            question = [c for c in data['collections'] if c['name'] == 'Question'][0]
            self.assertEqual(len(question['fields']), 6)
            foo_field = [f for f in question['fields'] if f['field'] == 'foo'][0]
            self.assertFalse('get' in foo_field)
            self.assertIsNotNone(Schema.schema_data)


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
class UtilsGetAppTests(TestCase):

    @mock.patch('importlib.metadata.version', return_value='0.0.1')
    def test_get_app_version(self, mock_version):
        from django_forest.utils.schema import get_app_version
        version = get_app_version()
        self.assertEqual(version, '0.0.1')

    @mock.patch('importlib.metadata.version', side_effect=Exception('error'))
    def test_get_app_version_error(self, mock_version):
        from django_forest.utils.schema import get_app_version
        version = get_app_version()
        self.assertEqual(version, '0.0.0')


@pytest.mark.skipif(sys.version_info >= (3, 8), reason="requires python3.7 or lower")
class UtilsGetAppOldPythonTests(TestCase):

    @mock.patch('importlib_metadata.version', return_value='0.0.1')
    def test_get_app_version(self, mock_version):
        from django_forest.utils.schema import get_app_version
        version = get_app_version()
        self.assertEqual(version, '0.0.1')

    @mock.patch('importlib_metadata.version', side_effect=Exception('error'))
    def test_get_app_version_error(self, mock_version):
        from django_forest.utils.schema import get_app_version
        version = get_app_version()
        self.assertEqual(version, '0.0.0')
"""
Unit tests for new MCP tools: search_devices, get_device_commands,
get_context_summary, and batch_execute_commands.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import UUID
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from api import Location
from st.device import DeviceItem, Component, CapabilityModel, CategoryModel, DeviceProfile
from st.command import Command
from datetime import datetime


@pytest.fixture
def mock_location():
    """Create a mock Location instance for testing."""
    with patch('api.CustomSession'):
        # Create mock location
        location = Location(auth="test_token")

        # Mock rooms
        location.rooms = {
            UUID('11111111-1111-1111-1111-111111111111'): '客厅',
            UUID('22222222-2222-2222-2222-222222222222'): '卧室',
            UUID('33333333-3333-3333-3333-333333333333'): '厨房',
        }

        # Mock timezone
        import pytz
        location.timezone = pytz.timezone('Asia/Shanghai')

        return location


@pytest.fixture
def mock_devices():
    """Create mock device data for testing."""
    device1 = Mock(spec=DeviceItem)
    device1.device_id = UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    device1.label = '客厅吸顶灯'
    device1.room_id = UUID('11111111-1111-1111-1111-111111111111')
    device1.manufacturer_name = 'TestBrand'

    # Mock components
    component1 = Mock(spec=Component)
    component1.id = 'main'
    component1.label = 'Main'

    # Mock capabilities
    cap1 = Mock(spec=CapabilityModel)
    cap1.id = 'switch'
    cap1.version = 1
    cap1.status = {
        'switch': Mock(value='on', unit=None, timestamp=None)
    }

    component1.capabilities = [cap1]
    device1.components = [component1]

    # Device 2
    device2 = Mock(spec=DeviceItem)
    device2.device_id = UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
    device2.label = '客厅台灯'
    device2.room_id = UUID('11111111-1111-1111-1111-111111111111')
    device2.manufacturer_name = 'TestBrand'

    component2 = Mock(spec=Component)
    component2.id = 'main'
    component2.label = 'Main'

    cap2 = Mock(spec=CapabilityModel)
    cap2.id = 'switch'
    cap2.version = 1
    cap2.status = {
        'switch': Mock(value='off', unit=None, timestamp=None)
    }

    component2.capabilities = [cap2]
    device2.components = [component2]

    # Device 3 - Temperature sensor
    device3 = Mock(spec=DeviceItem)
    device3.device_id = UUID('cccccccc-cccc-cccc-cccc-cccccccccccc')
    device3.label = '卧室温度传感器'
    device3.room_id = UUID('22222222-2222-2222-2222-222222222222')
    device3.manufacturer_name = 'TestBrand'

    component3 = Mock(spec=Component)
    component3.id = 'main'
    component3.label = 'Main'

    cap3 = Mock(spec=CapabilityModel)
    cap3.id = 'temperatureMeasurement'
    cap3.version = 1
    cap3.status = None

    component3.capabilities = [cap3]
    device3.components = [component3]

    return [device1, device2, device3]


class TestSearchDevices:
    """Test search_devices functionality."""

    def test_search_by_room_and_type(self, mock_location, mock_devices):
        """Test searching devices by room and device type."""
        with patch.object(mock_location, 'get_devices', return_value=mock_devices):
            results = mock_location.search_devices("客厅 灯", limit=5)

            assert len(results) == 2
            assert results[0]['name'] == '客厅吸顶灯'
            assert results[0]['room'] == '客厅'
            assert results[0]['type'] == 'switch'
            assert 'fullId' in results[0]
            assert 'id' in results[0]

    def test_search_by_room_only(self, mock_location, mock_devices):
        """Test searching devices by room only."""
        with patch.object(mock_location, 'get_devices', return_value=mock_devices):
            results = mock_location.search_devices("客厅", limit=5)

            assert len(results) == 2
            assert all(r['room'] == '客厅' for r in results)

    def test_search_by_type_only(self, mock_location, mock_devices):
        """Test searching devices by type only."""
        with patch.object(mock_location, 'get_devices', return_value=mock_devices):
            results = mock_location.search_devices("温度", limit=5)

            assert len(results) == 1
            assert results[0]['name'] == '卧室温度传感器'

    def test_search_empty_query(self, mock_location):
        """Test searching with empty query."""
        results = mock_location.search_devices("", limit=5)
        assert results == []

    def test_search_limit(self, mock_location, mock_devices):
        """Test search result limiting."""
        with patch.object(mock_location, 'get_devices', return_value=mock_devices):
            results = mock_location.search_devices("客厅", limit=1)

            assert len(results) == 1


class TestGetDeviceCommands:
    """Test get_device_commands functionality."""

    def test_get_switch_commands(self, mock_location, mock_devices):
        """Test getting commands for switch capability."""
        device_id = UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

        with patch.object(mock_location, 'validate_device_id', return_value=device_id):
            with patch.object(mock_location, 'get_devices', return_value=mock_devices):
                result = mock_location.get_device_commands(device_id, 'switch')

                assert result['capability'] == 'switch'
                assert 'on' in result['commands']
                assert 'off' in result['commands']
                assert result['component'] == 'main'

    def test_get_commands_unsupported_capability(self, mock_location, mock_devices):
        """Test getting commands for unsupported capability."""
        device_id = UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

        with patch.object(mock_location, 'validate_device_id', return_value=device_id):
            with patch.object(mock_location, 'get_devices', return_value=mock_devices):
                result = mock_location.get_device_commands(device_id, 'thermostat')

                assert 'error' in result
                assert 'available_capabilities' in result


class TestGetContextSummary:
    """Test get_context_summary functionality."""

    def test_context_summary_structure(self, mock_location, mock_devices):
        """Test context summary returns correct structure."""
        with patch.object(mock_location, 'get_devices', return_value=mock_devices):
            summary = mock_location.get_context_summary()

            assert 'rooms' in summary
            assert 'statistics' in summary
            assert 'hub_time' in summary

            assert 'total_devices' in summary['statistics']
            assert 'by_type' in summary['statistics']

    def test_context_summary_room_counts(self, mock_location, mock_devices):
        """Test room device counts are correct."""
        with patch.object(mock_location, 'get_devices', return_value=mock_devices):
            summary = mock_location.get_context_summary()

            rooms = summary['rooms']
            assert '客厅' in rooms
            assert rooms['客厅']['device_count'] == 2
            assert '卧室' in rooms
            assert rooms['卧室']['device_count'] == 1

    def test_context_summary_device_types(self, mock_location, mock_devices):
        """Test device type statistics are correct."""
        with patch.object(mock_location, 'get_devices', return_value=mock_devices):
            summary = mock_location.get_context_summary()

            stats = summary['statistics']
            assert stats['total_devices'] == 3
            assert 'switch' in stats['by_type']
            assert stats['by_type']['switch'] == 2


class TestBatchExecuteCommands:
    """Test batch_execute_commands functionality."""

    def test_batch_execute_success(self, mock_location):
        """Test successful batch execution."""
        operations = [
            {
                'device_id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                'commands': [
                    {'component': 'main', 'capability': 'switch', 'command': 'off'}
                ]
            },
            {
                'device_id': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
                'commands': [
                    {'component': 'main', 'capability': 'switch', 'command': 'off'}
                ]
            }
        ]

        # Mock device_commands to return success
        mock_result = {'results': [{'status': 'ACCEPTED'}]}
        with patch.object(mock_location, 'device_commands', return_value=mock_result):
            result = mock_location.batch_execute_commands(operations)

            assert result['total'] == 2
            assert result['success'] == 2
            assert result['failed'] == 0
            assert len(result['results']) == 2

    def test_batch_execute_partial_failure(self, mock_location):
        """Test batch execution with partial failures."""
        operations = [
            {
                'device_id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                'commands': [
                    {'component': 'main', 'capability': 'switch', 'command': 'off'}
                ]
            },
            {
                'device_id': 'invalid-id',
                'commands': [
                    {'component': 'main', 'capability': 'switch', 'command': 'off'}
                ]
            }
        ]

        # Mock device_commands: first succeeds, second fails
        def mock_device_commands(device_id, commands):
            if 'invalid' in str(device_id):
                raise ValueError("Device not found")
            return {'results': [{'status': 'ACCEPTED'}]}

        with patch.object(mock_location, 'device_commands', side_effect=mock_device_commands):
            result = mock_location.batch_execute_commands(operations)

            assert result['total'] == 2
            assert result['success'] == 1
            assert result['failed'] == 1

    def test_batch_execute_empty_operations(self, mock_location):
        """Test batch execution with empty operations list."""
        result = mock_location.batch_execute_commands([])

        assert result['total'] == 0
        assert result['success'] == 0
        assert result['failed'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

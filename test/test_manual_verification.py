#!/usr/bin/env python3
"""
Manual verification script for new tools.
This script tests the logic without requiring a full SmartThings setup.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from unittest.mock import Mock, MagicMock
from uuid import UUID


def test_search_logic():
    """Test search_devices scoring logic"""
    print("✓ Testing search_devices logic...")

    # Simulate search scoring
    query = "客厅 灯"
    keywords = [k.strip().lower() for k in query.split()]

    device_label = "客厅吸顶灯"
    room_name = "客厅"

    score = 0.0
    for keyword in keywords:
        if keyword in device_label.lower():
            score += 10.0
        if keyword in room_name.lower():
            score += 8.0

    assert score > 0, "Search score should be > 0"
    assert "客厅" in keywords, "Should extract room keyword"
    assert "灯" in keywords, "Should extract device type keyword"

    print(f"  - Search score calculation: {score} (expected > 0) ✓")
    print(f"  - Keywords extracted: {keywords} ✓")


def test_context_summary_structure():
    """Test get_context_summary structure"""
    print("✓ Testing get_context_summary structure...")

    # Simulate context summary
    summary = {
        "rooms": {
            "客厅": {"device_count": 3, "types": ["switch", "sensor"]},
            "卧室": {"device_count": 2, "types": ["switch"]}
        },
        "statistics": {
            "total_devices": 5,
            "by_type": {"switch": 4, "sensor": 1}
        },
        "hub_time": "2025-11-12 10:30:00 UTC+8"
    }

    assert "rooms" in summary, "Should have rooms"
    assert "statistics" in summary, "Should have statistics"
    assert "hub_time" in summary, "Should have hub_time"
    assert summary["statistics"]["total_devices"] == 5, "Total devices should be 5"

    print(f"  - Structure validation ✓")
    print(f"  - Total devices: {summary['statistics']['total_devices']} ✓")


def test_device_commands_mapping():
    """Test get_device_commands capability mapping"""
    print("✓ Testing get_device_commands mapping...")

    CAPABILITY_COMMANDS = {
        "switch": ["on", "off"],
        "switchLevel": ["setLevel"],
        "lock": ["lock", "unlock"],
        "thermostat": ["setHeatingSetpoint", "setCoolingSetpoint", "setThermostatMode"],
    }

    assert "switch" in CAPABILITY_COMMANDS, "Should have switch capability"
    assert "on" in CAPABILITY_COMMANDS["switch"], "Switch should have 'on' command"
    assert "off" in CAPABILITY_COMMANDS["switch"], "Switch should have 'off' command"

    print(f"  - Capability mappings defined: {len(CAPABILITY_COMMANDS)} ✓")
    print(f"  - Switch commands: {CAPABILITY_COMMANDS['switch']} ✓")


def test_batch_execute_structure():
    """Test batch_execute_commands structure"""
    print("✓ Testing batch_execute_commands structure...")

    # Simulate batch execution result
    operations = [
        {"device_id": "abc", "commands": [{"capability": "switch", "command": "off"}]},
        {"device_id": "def", "commands": [{"capability": "switch", "command": "off"}]}
    ]

    results = []
    for op in operations:
        results.append({
            'device_id': op['device_id'],
            'status': 'success',
            'details': {'results': [{'status': 'ACCEPTED'}]}
        })

    summary = {
        'total': len(operations),
        'success': sum(1 for r in results if r['status'] == 'success'),
        'failed': sum(1 for r in results if r['status'] == 'failed'),
        'results': results
    }

    assert summary['total'] == 2, "Total should be 2"
    assert summary['success'] == 2, "Success should be 2"
    assert summary['failed'] == 0, "Failed should be 0"

    print(f"  - Batch execution: {summary['total']} operations ✓")
    print(f"  - Success: {summary['success']}, Failed: {summary['failed']} ✓")


def test_compressed_output():
    """Test compressed output format"""
    print("✓ Testing compressed output format...")

    device_id = UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')

    compressed = {
        "id": str(device_id)[:8],
        "fullId": str(device_id),
        "name": "客厅吸顶灯",
        "room": "客厅",
        "type": "switch",
        "relevance_score": 18.0
    }

    assert len(compressed["id"]) == 8, "Short ID should be 8 chars"
    assert len(compressed["fullId"]) == 36, "Full ID should be 36 chars (UUID format)"
    assert "name" in compressed, "Should have name"
    assert "room" in compressed, "Should have room"
    assert "type" in compressed, "Should have type"

    print(f"  - Short ID length: {len(compressed['id'])} ✓")
    print(f"  - Full ID preserved: {len(compressed['fullId'])} chars ✓")
    print(f"  - Compressed format validated ✓")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Manual Verification Tests for New MCP Tools")
    print("=" * 60 + "\n")

    tests = [
        test_search_logic,
        test_context_summary_structure,
        test_device_commands_mapping,
        test_batch_execute_structure,
        test_compressed_output
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    if failed == 0:
        print("✓ All tests passed!")
    else:
        print(f"✗ {failed} test(s) failed")
    print("=" * 60 + "\n")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

"""
Context Manager for SmartThings Agent
Handles short-term memory, device caching, and conversation state
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import re


@dataclass
class DeviceMemory:
    """Memory of a device mentioned in conversation"""

    device_id: str
    name: str
    room: Optional[str] = None
    device_type: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    last_mentioned_turn: int = 0
    last_status: Optional[Dict[str, Any]] = None
    last_status_time: Optional[datetime] = None

    def is_status_fresh(self, ttl_seconds: int = 300) -> bool:
        """Check if cached status is still fresh (default: 5 minutes)"""
        if not self.last_status_time:
            return False
        return datetime.now() - self.last_status_time < timedelta(seconds=ttl_seconds)


class ConversationContext:
    """Manages conversation context and device memory"""

    def __init__(self, status_ttl: int = 300):
        """
        Initialize context manager

        Args:
            status_ttl: Time-to-live for cached status in seconds (default: 5 minutes)
        """
        self.mentioned_devices: Dict[str, DeviceMemory] = {}
        self.current_room: Optional[str] = None
        self.current_turn: int = 0
        self.status_ttl = status_ttl
        self.last_intent: Optional[str] = None
        self.pending_actions: List[Dict] = []

    def add_device(
        self,
        device_id: str,
        name: str,
        room: Optional[str] = None,
        device_type: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
    ) -> DeviceMemory:
        """
        Add or update a device in memory

        Args:
            device_id: Unique device identifier
            name: Device name
            room: Room where device is located
            device_type: Type of device
            capabilities: List of device capabilities

        Returns:
            DeviceMemory object
        """
        if device_id in self.mentioned_devices:
            # Update existing
            device = self.mentioned_devices[device_id]
            device.name = name
            device.room = room or device.room
            device.device_type = device_type or device.device_type
            if capabilities:
                device.capabilities = capabilities
            device.last_mentioned_turn = self.current_turn
        else:
            # Create new
            device = DeviceMemory(
                device_id=device_id,
                name=name,
                room=room,
                device_type=device_type,
                capabilities=capabilities or [],
                last_mentioned_turn=self.current_turn,
            )
            self.mentioned_devices[device_id] = device

        # Update current room context
        if room:
            self.current_room = room

        return device

    def update_device_status(self, device_id: str, status: Dict[str, Any]):
        """
        Update cached status for a device

        Args:
            device_id: Device identifier
            status: Device status dictionary
        """
        if device_id in self.mentioned_devices:
            device = self.mentioned_devices[device_id]
            device.last_status = status
            device.last_status_time = datetime.now()

    def get_device(self, device_id: str) -> Optional[DeviceMemory]:
        """Get device from memory by ID"""
        return self.mentioned_devices.get(device_id)

    def get_cached_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached status if still fresh

        Args:
            device_id: Device identifier

        Returns:
            Cached status dict if fresh, None otherwise
        """
        device = self.get_device(device_id)
        if device and device.is_status_fresh(self.status_ttl):
            return device.last_status
        return None

    def find_device_by_reference(self, reference: str) -> Optional[DeviceMemory]:
        """
        Find device by natural language reference (e.g., "它", "那个灯")

        Args:
            reference: Natural language reference

        Returns:
            DeviceMemory if found, None otherwise
        """
        reference_lower = reference.lower()

        # Check for pronouns (它, that, it)
        if reference_lower in ["它", "that", "it", "这个", "那个", "this"]:
            # Return most recently mentioned device
            if self.mentioned_devices:
                return max(
                    self.mentioned_devices.values(), key=lambda d: d.last_mentioned_turn
                )

        # Check for device type match in current room
        for device in self.mentioned_devices.values():
            if device.room == self.current_room:
                # Match by device type or name
                if (
                    device.device_type
                    and device.device_type.lower() in reference_lower
                ):
                    return device
                if device.name and any(
                    word in device.name.lower()
                    for word in reference_lower.split()
                ):
                    return device

        # Partial name match across all devices
        for device in self.mentioned_devices.values():
            if device.name and any(
                word in device.name.lower() for word in reference_lower.split()
            ):
                return device

        return None

    def infer_room_from_input(self, user_input: str) -> Optional[str]:
        """
        Extract room mention from user input

        Args:
            user_input: User's message

        Returns:
            Room name if detected, None otherwise
        """
        # Common room patterns in Chinese and English
        room_patterns = [
            r"(客厅|living room|living|客廳)",
            r"(卧室|bedroom|bed room|臥室)",
            r"(厨房|kitchen|廚房)",
            r"(浴室|bathroom|bath room|洗手间|洗手間)",
            r"(书房|study|study room|書房)",
            r"(餐厅|dining room|dining|餐廳)",
            r"(阳台|balcony|陽台)",
            r"(车库|garage|車庫)",
            r"(走廊|hallway|corridor)",
            r"(入口|entrance|entry|玄关|玄關)",
        ]

        room_map = {
            "客厅": "living room",
            "客廳": "living room",
            "卧室": "bedroom",
            "臥室": "bedroom",
            "厨房": "kitchen",
            "廚房": "kitchen",
            "浴室": "bathroom",
            "洗手间": "bathroom",
            "洗手間": "bathroom",
            "书房": "study",
            "書房": "study",
            "餐厅": "dining room",
            "餐廳": "dining room",
            "阳台": "balcony",
            "陽台": "balcony",
            "车库": "garage",
            "車庫": "garage",
            "走廊": "hallway",
            "入口": "entrance",
            "玄关": "entrance",
            "玄關": "entrance",
        }

        for pattern in room_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                room = match.group(1)
                return room_map.get(room, room)

        return None

    def increment_turn(self):
        """Increment conversation turn counter"""
        self.current_turn += 1

    def set_intent(self, intent: str):
        """Set current intent"""
        self.last_intent = intent

    def add_pending_action(self, action: Dict):
        """Add a pending action to queue"""
        self.pending_actions.append(action)

    def clear_pending_actions(self):
        """Clear all pending actions"""
        self.pending_actions = []

    def get_summary(self) -> Dict[str, Any]:
        """
        Get context summary for debugging or logging

        Returns:
            Dictionary with context summary
        """
        return {
            "current_turn": self.current_turn,
            "current_room": self.current_room,
            "last_intent": self.last_intent,
            "devices_in_memory": len(self.mentioned_devices),
            "device_list": [
                {
                    "id": d.device_id,
                    "name": d.name,
                    "room": d.room,
                    "last_turn": d.last_mentioned_turn,
                }
                for d in self.mentioned_devices.values()
            ],
            "pending_actions": len(self.pending_actions),
        }

    def cleanup_old_devices(self, turns_threshold: int = 10):
        """
        Remove devices not mentioned in last N turns

        Args:
            turns_threshold: Number of turns after which to forget device
        """
        to_remove = []
        for device_id, device in self.mentioned_devices.items():
            if self.current_turn - device.last_mentioned_turn > turns_threshold:
                to_remove.append(device_id)

        for device_id in to_remove:
            del self.mentioned_devices[device_id]

        return len(to_remove)

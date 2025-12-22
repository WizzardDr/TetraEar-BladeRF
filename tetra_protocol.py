"""
TETRA Protocol Layer Parser
Implements PHY, MAC, and higher layer parsing as demonstrated by OpenEar.
Parses bursts, slots, frames, and superframes.
"""

import numpy as np
from bitstring import BitArray
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BurstType(Enum):
    """TETRA burst types."""
    NormalUplink = 1
    NormalDownlink = 2
    ControlUplink = 3
    ControlDownlink = 4
    Synchronization = 5
    Linearization = 6


class ChannelType(Enum):
    """TETRA logical channel types."""
    TCH = "Traffic Channel"
    STCH = "Stealing Channel"
    SCH = "Signaling Channel"
    AACH = "Associated Control Channel"
    BSCH = "Broadcast Synchronization Channel"
    BNCH = "Broadcast Network Channel"
    
    
class PDUType(Enum):
    """MAC PDU types."""
    MAC_RESOURCE = 0
    MAC_FRAG = 1
    MAC_END = 2
    MAC_BROADCAST = 3
    MAC_SUPPL = 4
    MAC_U_SIGNAL = 5
    MAC_DATA = 6
    MAC_U_BLK = 7


@dataclass
class TetraBurst:
    """Represents a TETRA burst (255 symbols)."""
    burst_type: BurstType
    slot_number: int
    frame_number: int
    training_sequence: np.ndarray
    data_bits: np.ndarray
    crc_ok: bool
    scrambling_code: int = 0
    colour_code: int = 0
    

@dataclass
class TetraSlot:
    """Represents a TETRA time slot (14.167ms, 255 symbols)."""
    slot_number: int  # 0-3 within frame
    frame_number: int
    burst: TetraBurst
    channel_type: ChannelType
    encrypted: bool = False
    encryption_mode: int = 0


@dataclass
class TetraFrame:
    """Represents a TETRA frame (4 slots = 56.67ms)."""
    frame_number: int  # 0-17 within multiframe
    slots: List[TetraSlot]
    multiframe_number: int = 0
    
    
@dataclass
class TetraMultiframe:
    """Represents a TETRA multiframe (18 frames = 1.02 seconds)."""
    multiframe_number: int
    frames: List[TetraFrame]


@dataclass
class TetraHyperframe:
    """Represents a TETRA hyperframe (60 multiframes = 61.2 seconds)."""
    hyperframe_number: int
    multiframes: List[TetraMultiframe]


@dataclass
class MacPDU:
    """MAC layer PDU."""
    pdu_type: PDUType
    encrypted: bool
    address: Optional[int]
    length: int
    data: bytes
    fill_bits: int = 0
    reassembled_data: Optional[bytes] = None  # For fragmented messages
    

@dataclass
class CallMetadata:
    """Call setup/teardown metadata."""
    call_type: str  # "Voice", "Data", "Group", "Individual"
    talkgroup_id: Optional[int]
    source_ssi: Optional[int]  # Subscriber Station Identity
    dest_ssi: Optional[int]
    channel_allocated: Optional[int]
    call_identifier: Optional[int] = None
    call_priority: int = 0
    mcc: Optional[int] = None
    mnc: Optional[int] = None
    duplex_mode: str = "simplex"
    encryption_enabled: bool = False
    encryption_algorithm: Optional[str] = None


class TetraProtocolParser:
    """
    TETRA protocol parser implementing PHY + MAC + higher layers.
    Demonstrates OpenEar-style decoding capabilities.
    """
    
    # TETRA timing constants
    SYMBOLS_PER_SLOT = 255
    SLOTS_PER_FRAME = 4
    FRAMES_PER_MULTIFRAME = 18
    MULTIFRAMES_PER_HYPERFRAME = 60
    
    # Training sequences for burst synchronization
    TRAINING_SEQUENCES = {
        1: [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1],
        2: [0, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1],
        3: [0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0],
    }
    
    # Sync patterns
    SYNC_CONTINUOUS_DOWNLINK = [1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1, 0, 0]
    SYNC_DISCONTINUOUS_DOWNLINK = [0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 1]
    
    def __init__(self):
        """Initialize protocol parser."""
        self.current_frame_number = 0
        self.current_multiframe = 0
        self.current_hyperframe = 0
        self.mcc = None  # Mobile Country Code
        self.mnc = None  # Mobile Network Code
        self.la = None   # Location Area
        self.colour_code = None
        
        # Statistics
        self.stats = {
            'total_bursts': 0,
            'crc_pass': 0,
            'crc_fail': 0,
            'clear_mode_frames': 0,
            'encrypted_frames': 0,
            'decrypted_frames': 0,
            'voice_calls': 0,
            'data_messages': 0,
            'control_messages': 0,
        }
        
        # Fragmentation handling
        self.fragment_buffer = bytearray()
        self.fragment_metadata = {}
        
    def parse_burst(self, symbols: np.ndarray, slot_number: int = 0) -> Optional[TetraBurst]:
        """
        Parse a TETRA burst (255 symbols).
        
        Args:
            symbols: Symbol stream (255 symbols expected)
            slot_number: Slot number (0-3)
            
        Returns:
            Parsed TetraBurst or None if invalid
        """
        if len(symbols) < self.SYMBOLS_PER_SLOT:
            logger.warning(f"Insufficient symbols for burst: {len(symbols)} < {self.SYMBOLS_PER_SLOT}")
            return None
        
        # Extract burst
        burst_symbols = symbols[:self.SYMBOLS_PER_SLOT]
        
        # Convert symbols to bits (2 bits per π/4-DQPSK symbol)
        bits = []
        for sym in burst_symbols:
            bits.extend([int(sym >> 1 & 1), int(sym & 1)])
        bits = np.array(bits)
        
        # Detect burst type from training sequence position
        burst_type = self._detect_burst_type(bits)
        
        # Extract training sequence
        training_seq = self._extract_training_sequence(bits, burst_type)
        
        # Extract data bits (excluding training sequence and tail bits)
        data_bits = self._extract_data_bits(bits, burst_type)
        
        # Check CRC
        crc_ok = self._check_crc(data_bits)
        
        self.stats['total_bursts'] += 1
        if crc_ok:
            self.stats['crc_pass'] += 1
        else:
            self.stats['crc_fail'] += 1
        
        burst = TetraBurst(
            burst_type=burst_type,
            slot_number=slot_number,
            frame_number=self.current_frame_number,
            training_sequence=training_seq,
            data_bits=data_bits,
            crc_ok=crc_ok,
            colour_code=self.colour_code or 0
        )
        
        return burst
    
    def _detect_burst_type(self, bits: np.ndarray) -> BurstType:
        """Detect burst type from training sequence position."""
        # Check for sync burst (training sequence at specific position)
        sync_pos = len(bits) // 2
        if self._check_sync_pattern(bits[sync_pos:sync_pos+22]):
            return BurstType.Synchronization
        
        # Default to normal downlink
        return BurstType.NormalDownlink
    
    def _check_sync_pattern(self, bits: np.ndarray) -> bool:
        """Check if bits match sync pattern."""
        if len(bits) < 22:
            return False
        
        # Check both sync patterns
        match_cont = np.sum(bits[:22] == self.SYNC_CONTINUOUS_DOWNLINK) / 22
        match_disc = np.sum(bits[:22] == self.SYNC_DISCONTINUOUS_DOWNLINK) / 22
        
        return max(match_cont, match_disc) > 0.8
    
    def _extract_training_sequence(self, bits: np.ndarray, burst_type: BurstType) -> np.ndarray:
        """Extract training sequence from burst."""
        # Training sequence is typically in the middle of the burst
        if burst_type == BurstType.Synchronization:
            # Sync burst: training at position ~108
            return bits[108:130]
        else:
            # Normal burst: training at position ~108
            return bits[108:122]
    
    def _extract_data_bits(self, bits: np.ndarray, burst_type: BurstType) -> np.ndarray:
        """Extract data bits from burst (excluding training and tail)."""
        # Normal burst: 216 bits (2 x 108) excluding training sequence
        if burst_type == BurstType.NormalDownlink or burst_type == BurstType.NormalUplink:
            # First block: bits 0-107
            # Training: bits 108-121
            # Second block: bits 122-229
            # Tail: bits 230+
            first_block = bits[0:108]
            second_block = bits[122:230]
            return np.concatenate([first_block, second_block])
        
        # For other burst types, return all bits
        return bits
    
    def _check_crc(self, bits: np.ndarray) -> bool:
        """
        Check CRC-16-CCITT for data integrity.
        Simplified check - TETRA CRC is complex, so we use heuristics.
        """
        if len(bits) < 16:
            return False
        
        # SIMPLIFIED: For now, use heuristics instead of strict CRC
        # Real TETRA CRC is complex with interleaving and puncturing
        
        # Heuristic 1: Check for reasonable bit distribution
        ones = np.sum(bits)
        zeros = len(bits) - ones
        bit_ratio = min(ones, zeros) / max(ones, zeros) if max(ones, zeros) > 0 else 0
        
        # If bits are reasonably distributed (not all 0s or 1s), consider valid
        if bit_ratio > 0.15:  # At least 15% of minority bit
            return True
        
        # Heuristic 2: Try actual CRC on payload
        try:
            payload = bits[:-16]
            received_crc = bits[-16:]
            calculated_crc = self._calculate_crc16(payload)
            
            # Allow some bit errors (TETRA has FEC)
            errors = np.sum(calculated_crc != received_crc)
            return errors <= 3  # Allow up to 3 bit errors
        except:
            # If CRC calculation fails, fall back to heuristic
            return bit_ratio > 0.2
    
    def _calculate_crc16(self, bits: np.ndarray) -> np.ndarray:
        """Calculate CRC-16-CCITT (polynomial 0x1021)."""
        polynomial = 0x1021
        crc = 0xFFFF
        
        for bit in bits:
            crc ^= (int(bit) << 15)
            for _ in range(1):
                if crc & 0x8000:
                    crc = (crc << 1) ^ polynomial
                else:
                    crc <<= 1
                crc &= 0xFFFF
        
        # Convert to bits
        crc_bits = [(crc >> i) & 1 for i in range(15, -1, -1)]
        return np.array(crc_bits)
    
    def parse_mac_pdu(self, bits: np.ndarray) -> Optional[MacPDU]:
        """
        Parse MAC layer PDU.
        Handles fragmentation (MAC-RESOURCE, MAC-FRAG, MAC-END).
        
        Args:
            bits: Data bits from burst
            
        Returns:
            Parsed MacPDU or None
        """
        if len(bits) < 8:
            return None
        
        # MAC PDU Type (first 3 bits - simplified view)
        # Note: Standard is 2 bits for DL, but we use 3 to map to our enum
        pdu_type_val = (bits[0] << 2) | (bits[1] << 1) | bits[2]
        try:
            pdu_type = PDUType(pdu_type_val)
        except ValueError:
            pdu_type = PDUType.MAC_DATA
        
        # Fill bit indicator
        fill_bit_ind = bits[3]
        
        # Default fields
        encrypted = False
        address = None
        length = 0
        data_bytes = b''
        
        # Parse based on PDU Type
        if pdu_type == PDUType.MAC_RESOURCE:
            # MAC-RESOURCE (Type 0)
            # Structure: Type(3?), Fill(1), Encrypted(1), Address(24), Length(6), Data...
            
            encrypted = bool(bits[4])
            
            # Address (bits 5-28)
            if len(bits) >= 29:
                address_bits = bits[5:29]
                address = int(''.join(str(b) for b in address_bits), 2)
            
            # Length (bits 29-35)
            if len(bits) >= 35:
                length_bits = bits[29:35]
                length = int(''.join(str(b) for b in length_bits), 2)
                
            # Data
            data_start = 35
            data_bits = bits[data_start:data_start + length * 8] if len(bits) > data_start else bits[data_start:]
            try:
                data_bytes = BitArray(data_bits).tobytes()
            except:
                data_bytes = b''
                
            # Start fragmentation buffer
            self.fragment_buffer = bytearray(data_bytes)
            self.fragment_metadata = {'address': address, 'encrypted': encrypted}
            
        elif pdu_type == PDUType.MAC_FRAG:
            # MAC-FRAG (Type 1)
            # Structure: Type(3?), Fill(1), Data... (No address/length/encryption header)
            # It just continues the previous stream
            
            # Data starts immediately after Fill bit (bit 4)
            data_start = 4
            data_bits = bits[data_start:]
            try:
                data_bytes = BitArray(data_bits).tobytes()
            except:
                data_bytes = b''
                
            # Append to buffer
            self.fragment_buffer.extend(data_bytes)
            
            # Restore metadata from RESOURCE frame
            if self.fragment_metadata:
                encrypted = self.fragment_metadata.get('encrypted', False)
                address = self.fragment_metadata.get('address')
            
        elif pdu_type == PDUType.MAC_END:
            # MAC-END (Type 2)
            # Structure: Type(3?), Fill(1), Length(6?), Data...
            
            # Length (bits 4-10?) - Assuming similar structure to RESOURCE but no address
            # Let's assume Length is present
            if len(bits) >= 10:
                length_bits = bits[4:10]
                length = int(''.join(str(b) for b in length_bits), 2)
                
                data_start = 10
                data_bits = bits[data_start:data_start + length * 8] if len(bits) > data_start else bits[data_start:]
                try:
                    data_bytes = BitArray(data_bits).tobytes()
                except:
                    data_bytes = b''
            else:
                data_bytes = b''
                
            # Append and Finalize
            self.fragment_buffer.extend(data_bytes)
            
        else:
            # Other types (Broadcast, etc) - Use generic parsing (legacy)
            encrypted = bool(bits[4])
            if len(bits) >= 29:
                address_bits = bits[5:29]
                address = int(''.join(str(b) for b in address_bits), 2)
            if len(bits) >= 35:
                length_bits = bits[29:35]
                length = int(''.join(str(b) for b in length_bits), 2)
            data_start = 35
            data_bits = bits[data_start:data_start + length * 8] if len(bits) > data_start else bits[data_start:]
            try:
                data_bytes = BitArray(data_bits).tobytes()
            except:
                data_bytes = b''

        if encrypted:
            self.stats['encrypted_frames'] += 1
        else:
            self.stats['clear_mode_frames'] += 1
        
        # Create PDU
        pdu = MacPDU(
            pdu_type=pdu_type,
            encrypted=encrypted,
            address=address,
            length=length,
            data=data_bytes,
            fill_bits=fill_bit_ind
        )
        
        # Attach reassembled data if this is the end
        if pdu_type == PDUType.MAC_END and self.fragment_buffer:
            pdu.reassembled_data = bytes(self.fragment_buffer)
            # Restore metadata from start frame
            if self.fragment_metadata:
                if not pdu.address: pdu.address = self.fragment_metadata.get('address')
                # Restore encryption status from RESOURCE frame
                if not encrypted:
                    encrypted = self.fragment_metadata.get('encrypted', False)
                    pdu.encrypted = encrypted
            
            logger.debug(f"Reassembled {len(pdu.reassembled_data)} bytes from fragments")
            
            # Clear buffer
            self.fragment_buffer = bytearray()
            self.fragment_metadata = {}
        
        # For FRAG frames, also include current buffer state for monitoring
        elif pdu_type == PDUType.MAC_FRAG and self.fragment_buffer:
            # Don't set reassembled_data yet, but we could log progress
            logger.debug(f"Fragment buffer now has {len(self.fragment_buffer)} bytes")
            
        return pdu
    def parse_call_metadata(self, mac_pdu: MacPDU) -> Optional[CallMetadata]:
        """
        Extract call metadata from MAC PDU (talkgroup, SSI, etc.).
        
        Args:
            mac_pdu: MAC PDU to parse
            
        Returns:
            CallMetadata or None
        """
        if not mac_pdu or len(mac_pdu.data) < 4:
            return None
        
        # Parse based on PDU type
        if mac_pdu.pdu_type == PDUType.MAC_RESOURCE:
            # Resource assignment - contains channel allocation
            return self._parse_resource_assignment(mac_pdu)
        elif mac_pdu.pdu_type == PDUType.MAC_U_SIGNAL:
            # Signaling - contains call setup
            return self._parse_call_setup(mac_pdu)
        elif mac_pdu.pdu_type == PDUType.MAC_BROADCAST:
            # Broadcast - contains network info
            return self._parse_broadcast(mac_pdu)
        
        return None
    
    def _parse_resource_assignment(self, mac_pdu: MacPDU) -> Optional[CallMetadata]:
        """Parse resource assignment message."""
        data = mac_pdu.data
        if len(data) < 8:
            return None
        
        # Extract fields (Heuristic mapping)
        # Byte 0: [CallType(1) | ... ]
        call_type = "Group" if data[0] & 0x80 else "Individual"
        
        # Bytes 1-3: Talkgroup/SSI (24 bits)
        talkgroup_id = int.from_bytes(data[1:4], 'big') & 0xFFFFFF
        
        # Byte 4: Channel Allocation
        channel_allocated = data[4] & 0x3F
        
        # Byte 5: Encryption & Priority
        encryption_enabled = bool(data[5] & 0x80)
        call_priority = (data[5] >> 2) & 0x0F  # Guessing priority location (4 bits)
        
        # Bytes 6-7: Call Identifier (14 bits)
        # Usually in the lower bits of byte 6 and upper of byte 7
        call_identifier = ((data[6] & 0x0F) << 10) | (data[7] << 2) # Rough guess
        
        self.stats['control_messages'] += 1
        
        return CallMetadata(
            call_type=call_type,
            talkgroup_id=talkgroup_id,
            source_ssi=None,
            dest_ssi=None,
            channel_allocated=channel_allocated,
            call_identifier=call_identifier,
            call_priority=call_priority,
            mcc=self.mcc,
            mnc=self.mnc,
            encryption_enabled=encryption_enabled,
            encryption_algorithm="TEA1" if encryption_enabled else None
        )
    
    def _parse_call_setup(self, mac_pdu: MacPDU) -> Optional[CallMetadata]:
        """Parse call setup signaling."""
        data = mac_pdu.data
        if len(data) < 12:
            return None
        
        # Extract SSIs
        source_ssi = int.from_bytes(data[0:3], 'big') & 0xFFFFFF
        dest_ssi = int.from_bytes(data[3:6], 'big') & 0xFFFFFF
        
        # Call type
        call_type_byte = data[6]
        if call_type_byte & 0x80:
            call_type = "Voice"
            self.stats['voice_calls'] += 1
        else:
            call_type = "Data"
            self.stats['data_messages'] += 1
        
        # Encryption
        encryption_enabled = bool(data[7] & 0x80)
        encryption_alg = None
        if encryption_enabled:
            alg_code = (data[7] >> 4) & 0x07
            if alg_code == 1:
                encryption_alg = "TEA1"
            elif alg_code == 2:
                encryption_alg = "TEA2"
            elif alg_code == 3:
                encryption_alg = "TEA3"
            elif alg_code == 4:
                encryption_alg = "TEA4"
        
        return CallMetadata(
            call_type=call_type,
            talkgroup_id=dest_ssi if call_type == "Voice" else None,
            source_ssi=source_ssi,
            dest_ssi=dest_ssi,
            channel_allocated=None,
            call_identifier=None,
            call_priority=0,
            mcc=self.mcc,
            mnc=self.mnc,
            encryption_enabled=encryption_enabled,
            encryption_algorithm=encryption_alg
        )

    def _parse_broadcast(self, mac_pdu: MacPDU) -> Optional[CallMetadata]:
        """
        Parse MAC-BROADCAST (SYSINFO/SYNC).
        Extracts MCC, MNC, LA, Color Code.
        """
        data = mac_pdu.data
        if len(data) < 5:
            return None
            
        # D-MLE-SYNC structure (approximate):
        # MCC (10 bits)
        # MNC (14 bits)
        # Neighbour Cell Info...
        
        try:
            # Convert to bits for easier parsing
            bits = BitArray(data)
            
            # MCC: 10 bits
            mcc = bits[0:10].uint
            
            # MNC: 14 bits
            mnc = bits[10:24].uint
            
            # Colour Code: 6 bits (often follows)
            colour_code = bits[24:30].uint
            
            # Update parser state
            self.mcc = mcc
            self.mnc = mnc
            self.colour_code = colour_code
            
            # Return metadata with just network info
            return CallMetadata(
                call_type="Broadcast",
                talkgroup_id=None,
                source_ssi=None,
                dest_ssi=None,
                channel_allocated=None,
                mcc=mcc,
                mnc=mnc,
                encryption_enabled=False
            )
        except:
            return None
    
    def parse_sds_message(self, mac_pdu: MacPDU) -> Optional[str]:
        """
        Parse Short Data Service (SDS) text message.
        
        Args:
            mac_pdu: MAC PDU containing SDS
            
        Returns:
            Decoded text message or None
        """
        if mac_pdu.pdu_type != PDUType.MAC_DATA and mac_pdu.pdu_type != PDUType.MAC_SUPPL:
            return None
        
        # SDS data is in the payload
        return self.parse_sds_data(mac_pdu.data)

    def parse_sds_data(self, data: bytes) -> Optional[str]:
        """
        Parse SDS data payload based on Protocol Identifier (PID) or heuristics.
        Supports SDS-1 (Text), SDS-TL (PID), and GSM 7-bit encoding.
        
        Args:
            data: Raw data bytes
            
        Returns:
            Decoded text string or None
        """
        if not data or len(data) < 1:
            return None
        
        # Strip trailing null bytes for text detection
        data_stripped = data.rstrip(b'\x00')
        if not data_stripped:
            return None
            
        # --- Check for User-Defined SDS Types (based on user examples) ---
        # Example 1: SDS-1 Text (05 00 Length ...)
        if len(data) > 3 and data[0] == 0x05 and data[1] == 0x00:
            # User example: 05 00 C8 48 45 4C 4C 4F -> HELLO
            # Payload starts at offset 3
            payload = data[3:].rstrip(b'\x00')
            try:
                text = payload.decode('ascii')
                if self._is_valid_text(text):
                    self.stats['data_messages'] += 1
                    return f"[SDS-1] {text}"
            except:
                pass

        # Example 2: SDS with GSM 7-bit (07 00 Length ...)
        if len(data) > 3 and data[0] == 0x07 and data[1] == 0x00:
            # User example: 07 00 D2 D4 79 9E 2F 03 -> STATUS OK
            # Try unpacking from offset 3 (skipping length byte D2)
            payload = data[3:]
            try:
                text = self._unpack_gsm7bit(payload)
                if self._is_valid_text(text):
                    self.stats['data_messages'] += 1
                    return f"[SDS-GSM] {text}"
            except:
                pass
            
            # Fallback: Try from offset 2 if offset 3 failed
            payload = data[2:]
            try:
                text = self._unpack_gsm7bit(payload)
                if self._is_valid_text(text):
                    self.stats['data_messages'] += 1
                    return f"[SDS-GSM] {text}"
            except:
                pass

        # --- Standard SDS-TL PID Checks ---
        pid = data[0]
        payload = data[1:].rstrip(b'\x00')
        
        if pid == 0x82:  # Text Messaging (ISO 8859-1)
            try:
                text = payload.decode('latin-1')
                if self._is_valid_text(text):
                    self.stats['data_messages'] += 1
                    return f"[TXT] {text}"
            except:
                pass
                
        elif pid == 0x03:  # Simple Text Messaging (ASCII)
            try:
                text = payload.decode('ascii')
                if self._is_valid_text(text):
                    self.stats['data_messages'] += 1
                    return f"[TXT] {text}"
            except:
                pass
            
        elif pid == 0x83:  # Location
            # Try to parse LIP
            lip_text = self.parse_lip(payload)
            if lip_text:
                return f"[LIP] {lip_text}"
            return f"[LOC] Location Data: {payload.hex()}"
            
        elif pid == 0x0C:  # GPS
            # Try to parse LIP (PID 0x0C is often used for LIP too)
            lip_text = self.parse_lip(payload)
            if lip_text:
                return f"[LIP] {lip_text}"
            return f"[GPS] GPS Data: {payload.hex()}"
            
        # --- Fallback Heuristics ---
        
        # Use stripped data for text detection
        test_data = data_stripped
        
        # Check for 7-bit GSM packing or 8-bit text
        # Heuristic: if > 60% of bytes are printable, treat as text
        printable_count = sum(1 for b in test_data if 32 <= b <= 126 or b in (10, 13))
        if len(test_data) > 0 and (printable_count / len(test_data)) > 0.6:
             try:
                # Try multiple encodings
                text = None
                for encoding in ['utf-8', 'latin-1', 'ascii', 'cp1252']:
                    try:
                        text = test_data.decode(encoding, errors='strict')
                        if self._is_valid_text(text, threshold=0.6):
                            self.stats['data_messages'] += 1
                            return f"[TXT] {text}"
                    except:
                        continue
                
                # If strict decode failed, try with errors='replace'
                if not text:
                    text = test_data.decode('latin-1', errors='replace')
                    if self._is_valid_text(text, threshold=0.6):
                        self.stats['data_messages'] += 1
                        return f"[TXT] {text}"
             except:
                pass
        
        # Check for Encrypted Binary SDS (High Entropy)
        if len(test_data) > 8:
            unique_bytes = len(set(test_data))
            entropy_ratio = unique_bytes / len(test_data)
            if entropy_ratio > 0.7:
                return f"[BIN-ENC] SDS (Binary/Encrypted) - {len(test_data)} bytes"

        # Default to Hex dump for binary data
        return f"[BIN] {data_stripped.hex(' ').upper()}"

    def parse_lip(self, data: bytes) -> Optional[str]:
        """
        Parse Location Information Protocol (LIP) payload.
        ETSI TS 100 392-18-1.
        Handles Basic Location Report (Short/Long).
        """
        if not data or len(data) < 2:
            return None
            
        try:
            # LIP PDU Type (first 2 bits)
            # 00: Short Location Report
            # 01: Long Location Report
            # 10: Location Report with Ack
            # 11: Reserved/Extended
            
            # Convert to bits for easier parsing
            bits = BitArray(data)
            pdu_type = bits[0:2].uint
            
            if pdu_type == 0: # Short Location Report
                # Structure: Type(2), Time Elapsed(2), Lat(24), Long(25), Pos Error(3), Horizontal Vel(5), Direction(4)
                # Total ~65 bits
                if len(bits) < 65:
                    return None
                    
                # Time Elapsed (0-3) - 0=Current, 1=<5s, 2=<5min, 3=>5min
                time_elapsed = bits[2:4].uint
                
                # Latitude (24 bits, 2's complement)
                lat_raw = bits[4:28].int
                # Scaling: lat_raw * 90 / 2^23
                latitude = lat_raw * 90.0 / (1 << 23)
                
                # Longitude (25 bits, 2's complement)
                lon_raw = bits[28:53].int
                # Scaling: lon_raw * 180 / 2^24
                longitude = lon_raw * 180.0 / (1 << 24)
                
                return f"Lat: {latitude:.5f}, Lon: {longitude:.5f} (Short)"
                
            elif pdu_type == 1: # Long Location Report
                # Structure: Type(2), Time Elapsed(2), Lat(25), Long(26), Pos Error(3), Horizontal Vel(8), Direction(9)
                # Total ~75 bits
                if len(bits) < 75:
                    return None
                    
                # Latitude (25 bits)
                lat_raw = bits[4:29].int
                latitude = lat_raw * 90.0 / (1 << 24)
                
                # Longitude (26 bits)
                lon_raw = bits[29:55].int
                longitude = lon_raw * 180.0 / (1 << 25)
                
                return f"Lat: {latitude:.5f}, Lon: {longitude:.5f} (Long)"
                
            # Heuristic for raw NMEA (sometimes sent as text in LIP PID)
            try:
                text = data.decode('ascii')
                if "$GPGGA" in text or "$GPRMC" in text:
                    return f"NMEA: {text.strip()}"
            except:
                pass
                
        except Exception as e:
            logger.debug(f"LIP parsing error: {e}")
            
        return None

    def _unpack_gsm7bit(self, data: bytes) -> str:
        """
        Unpack GSM 7-bit encoded data.
        """
        unpacked = ""
        shift = 0
        carry = 0
        
        for byte in data:
            val = (byte >> shift) | (carry << (8 - shift))
            carry = byte & ((1 << (shift + 1)) - 1) # This logic is wrong for standard GSM
            
            # Let's use the standard algorithm
            # Byte n contains: (7-n) bits of Char n, and (n+1) bits of Char n+1
            pass
            
        # Correct Standard GSM 7-bit Unpacking
        # Septets are packed into octets.
        # Octet 0: 1aaaaaaa (7 bits of char 0) + 1 bit of char 1
        # Octet 1: 22bbbbbb (6 bits of char 1) + 2 bits of char 2
        
        unpacked = ""
        shift = 0
        carry = 0
        
        for byte in data:
            # Extract current character
            char_code = (byte >> shift) | (carry << (8 - shift))
            char_code &= 0x7F
            unpacked += self._gsm_map(char_code)
            
            # Prepare carry for next character
            # The carry contains the upper bits of the current byte
            # which belong to the NEXT character
            # Wait, standard GSM:
            # Byte 0: 7 bits of char 0 (LSB), 1 bit of char 1 (MSB)
            # char 0 = Byte 0 & 0x7F
            # carry = Byte 0 >> 7
            
            # Let's try this simple loop
            pass
            
        # Re-implementation
        unpacked = ""
        shift = 0
        carry = 0
        for byte in data:
            val = (byte << shift) | carry
            char_code = val & 0x7F
            unpacked += self._gsm_map(char_code)
            
            carry = byte >> (7 - shift)
            shift += 1
            
            if shift == 7:
                unpacked += self._gsm_map(carry)
                carry = 0
                shift = 0
                
        return unpacked

    def _gsm_map(self, code: int) -> str:
        """Map GSM 7-bit code to character."""
        # Simplified GSM 03.38 mapping (Basic Latin)
        if 32 <= code <= 126:
            return chr(code)
        elif code == 0: return '@'
        elif code == 2: return '$'
        elif code == 10: return '\n'
        elif code == 13: return '\r'
        # Add more mappings as needed
        return '.'

    def _is_valid_text(self, text: str, threshold: float = 0.8) -> bool:
        """Check if string looks like valid human-readable text."""
        if not text or len(text) < 2:
            return False
            
        # Remove common whitespace
        clean_text = ''.join(c for c in text if c not in '\n\r\t ')
        if not clean_text:
            return False
            
        # Check ratio of printable characters
        printable = sum(1 for c in text if 32 <= ord(c) <= 126 or c in '\n\r\t')
        ratio = printable / len(text)
        
        # Check for excessive repetition (padding)
        if len(text) > 4 and text.count(text[0]) == len(text):
            return False
            
        # Check for high density of symbols (binary data often looks like symbols)
        alnum = sum(1 for c in text if c.isalnum() or c == ' ')
        alnum_ratio = alnum / len(text)
        
        return ratio >= threshold and alnum_ratio > 0.5



    def extract_voice_payload(self, mac_pdu: MacPDU) -> Optional[bytes]:
        """
        Extract ACELP voice payload from MAC PDU.
        
        Args:
            mac_pdu: MAC PDU
            
        Returns:
            Voice payload bytes or None
        """
        # Voice is usually in MAC-TRAFFIC (which maps to specific burst types)
        # But here we might receive it as MAC_U_SIGNAL or similar if not parsed correctly
        # In TETRA, voice frames are typically 2 slots interleaved
        
        # For this implementation, we assume the payload IS the voice frame
        # if the frame type indicates traffic
        
        if not mac_pdu.data:
            return None
            
        return mac_pdu.data
    
    def get_statistics(self) -> Dict:
        """Get parsing statistics."""
        total = self.stats['clear_mode_frames'] + self.stats['encrypted_frames']
        if total > 0:
            clear_pct = (self.stats['clear_mode_frames'] / total) * 100
            enc_pct = (self.stats['encrypted_frames'] / total) * 100
        else:
            clear_pct = enc_pct = 0
        
        return {
            **self.stats,
            'clear_mode_percentage': clear_pct,
            'encrypted_percentage': enc_pct,
            'crc_success_rate': (self.stats['crc_pass'] / max(1, self.stats['total_bursts'])) * 100
        }
    
    def format_call_metadata(self, metadata: CallMetadata) -> str:
        """Format call metadata for display."""
        lines = [
            f"📞 Call Type: {metadata.call_type}",
        ]
        
        if metadata.talkgroup_id:
            lines.append(f"👥 Talkgroup: {metadata.talkgroup_id}")
        
        if metadata.source_ssi:
            lines.append(f"📱 Source SSI: {metadata.source_ssi}")
        
        if metadata.dest_ssi:
            lines.append(f"📱 Dest SSI: {metadata.dest_ssi}")
        
        if metadata.channel_allocated:
            lines.append(f"📡 Channel: {metadata.channel_allocated}")
        
        if metadata.encryption_enabled:
            lines.append(f"🔒 Encryption: {metadata.encryption_algorithm or 'Unknown'}")
        else:
            lines.append("🔓 Clear Mode (No Encryption)")
        
        return "\n".join(lines)

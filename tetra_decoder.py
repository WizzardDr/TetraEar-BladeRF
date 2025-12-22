"""
TETRA frame decoder module.
"""

import numpy as np
from bitstring import BitArray
import logging
from typing import Optional

from tetra_crypto import TEADecryptor, TetraKeyManager
from tetra_protocol import TetraProtocolParser, TetraBurst, MacPDU, CallMetadata

logger = logging.getLogger(__name__)


class TetraDecoder:
    """Decodes TETRA frames from demodulated symbols."""
    
    def __init__(self, key_manager: Optional[TetraKeyManager] = None, auto_decrypt: bool = True):
        """
        Initialize TETRA decoder.
        
        Args:
            key_manager: Optional key manager for decryption
            auto_decrypt: Automatically try common keys if no key manager provided
        """
        # TETRA frame structure constants
        self.SYNC_PATTERN = [0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0,
                            1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0]
        self.FRAME_LENGTH = 510  # bits per frame
        self.key_manager = key_manager
        self.auto_decrypt = auto_decrypt
        self.protocol_parser = TetraProtocolParser()  # Add protocol parser
        self._setup_common_keys()
    
    def _setup_common_keys(self):
        """Setup common/known TETRA keys for auto-decryption (OpenEar style)."""
        self.common_keys = {
            'TEA1': [
                # Null/default keys
                bytes.fromhex('00000000000000000000'),  # All zeros
                bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFF'),  # All ones
                
                # Test patterns
                bytes.fromhex('0123456789ABCDEF0123'),  # Sequential
                bytes.fromhex('FEDCBA9876543210FEDC'),  # Reverse sequential
                
                # Common weak keys
                bytes.fromhex('1111111111111111111111'),  # All 1s
                bytes.fromhex('AAAAAAAAAAAAAAAAAAAA'),  # Pattern A
                bytes.fromhex('5555555555555555555555'),  # Pattern 5
                
                # Default manufacturer keys (common in testing)
                bytes.fromhex('0001020304050607080910'),
                bytes.fromhex('1234567890ABCDEF1234'),
                bytes.fromhex('DEADBEEFCAFEBABEFACE'),
                
                # Network default keys (some networks use these)
                bytes.fromhex('A0B1C2D3E4F506172839'),
                bytes.fromhex('112233445566778899AA'),
                bytes.fromhex('0F0F0F0F0F0F0F0F0F0F'),
            ],
            'TEA2': [
                # Null/default keys
                bytes.fromhex('00000000000000000000000000000000'),  # All zeros
                bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'),  # All ones
                
                # Test patterns
                bytes.fromhex('0123456789ABCDEF0123456789ABCDEF'),  # Sequential
                bytes.fromhex('FEDCBA9876543210FEDCBA9876543210'),  # Reverse
                
                # Common patterns
                bytes.fromhex('11111111111111111111111111111111'),
                bytes.fromhex('AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'),
                bytes.fromhex('55555555555555555555555555555555'),
                
                # Manufacturer defaults
                bytes.fromhex('000102030405060708091011121314151617'),
                bytes.fromhex('1234567890ABCDEF1234567890ABCDEF'),
                bytes.fromhex('DEADBEEFCAFEBABEDEADBEEFCAFEBABE'),
                
                # Network defaults
                bytes.fromhex('A0B1C2D3E4F5061728394A5B6C7D8E9F'),
                bytes.fromhex('1122334455667788990011223344556677'),
            ],
            'TEA3': [
                # TEA3 keys (similar structure to TEA2 usually 128-bit or 80-bit depending on implementation)
                # Standard TEA3 is 128-bit
                bytes.fromhex('00000000000000000000000000000000'),
                bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'),
            ],
            'TEA4': [
                # TEA4 keys
                bytes.fromhex('00000000000000000000000000000000'),
                bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'),
            ]
        }
        logger.debug(f"Auto-decrypt enabled with {sum(len(v) for v in self.common_keys.values())} common keys (OpenEar style)")
        
    def symbols_to_bits(self, symbols):
        """
        Convert demodulated symbols to bits (2 bits per symbol).
        Handles both 0-7 (8-PSK) and 0-3 (π/4-DQPSK) input formats.
        """
        bits = []
        mapped_symbols = []
        
        # Check if symbols are already in 0-3 format (π/4-DQPSK)
        max_symbol = np.max(symbols) if len(symbols) > 0 else 0
        is_dqpsk = max_symbol <= 3
        
        for s in symbols:
            if is_dqpsk:
                # Already in 0-3 format (π/4-DQPSK) - pass through
                # Symbols 0-3 directly represent the bit pairs
                val = int(s) & 0x3  # Ensure it's in range 0-3
            else:
                # Map 0-7 (8-PSK) to 0-3 (QPSK)
                # Handle neighbors for noise tolerance
                if s in [0, 1, 2]: val = 0   # 00
                elif s in [3, 4]: val = 1    # 01
                elif s in [5]: val = 3       # 11
                elif s in [6, 7]: val = 2    # 10
                else: val = 0
            
            mapped_symbols.append(val)
            bits.extend([val >> 1, val & 1])
            
        return np.array(bits), np.array(mapped_symbols)
    
    def find_sync(self, bits, threshold=0.85):
        """
        Find TETRA synchronization pattern (Training Sequence 1).
        """
        sync_positions = []
        # Training Sequence 1 (from TetraProtocolParser)
        # [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1]
        # Converted to bits (assuming 0->00, 1->01? No, these are likely bits)
        # Standard TS1 is 22 bits.
        # Let's use a known TS1 bit pattern: 1101000011101001110100
        # Or try to match what TetraProtocolParser uses.
        
        # Let's use the pattern from TetraProtocolParser but expanded to bits
        # If parser uses [0, 1...], let's assume they are bits.
        ts1_bits = [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1] # 14 bits? Too short.
        
        # Let's use the standard 22-bit TS1
        self.sync_patterns = {
            'TS1': np.array([1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1, 0, 0]),
            'TS2': np.array([0, 1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1, 0, 0]) # Example TS2
        }
        
        if len(bits) < 22:
            return sync_positions
        
        # Check every bit position (step=1) to ensure we don't miss sync
        # Use numpy for faster correlation if possible
        
        # Convert bits to numpy array if not already
        if not isinstance(bits, np.ndarray):
            bits = np.array(bits)
            
        # Sliding window correlation
        # Create a view of sliding windows
        # shape: (num_windows, window_size)
        sync_len = 22
        num_windows = len(bits) - sync_len + 1
        if num_windows <= 0:
            return sync_positions
            
        # Simple loop is safer and easier to debug than stride_tricks for now
        # Optimization: only check if first few bits match to avoid full correlation
        
        i = 0
        max_corr = 0.0
        while i < num_windows:
            # Try both TS1 and TS2
            for name, pattern in self.sync_patterns.items():
                # Full correlation check - removed fragile "quick check"
                window = bits[i:i+sync_len]
                match_count = np.sum(window == pattern)
                correlation = match_count / sync_len
                
                if correlation > max_corr:
                    max_corr = correlation
                
                if correlation >= threshold:
                    sync_positions.append(i)
                    # logger.debug(f"Found {name} sync at position {i}, correlation: {correlation:.2f}")
                    # Skip ahead to avoid duplicate detections (at least half a frame)
                    i += 250  # TETRA frame is ~510 bits
                    break # Found one, move to next frame
            
            i += 1
            
        if not sync_positions:
             logger.debug(f"No sync found at threshold {threshold}. Max correlation: {max_corr:.4f}")
        else:
             logger.debug(f"Found {len(sync_positions)} syncs at threshold {threshold}. Max correlation: {max_corr:.4f}")
        
        return sync_positions
    
    def decode_frame(self, bits, start_pos, symbols=None):
        """
        Decode a TETRA frame starting at given position.
        
        Args:
            bits: Bit stream
            start_pos: Start position of frame
            symbols: Optional pre-calculated symbols (0-3)
            
        Returns:
            Decoded frame data or None
        """
        if start_pos + self.FRAME_LENGTH > len(bits):
            return None
        
        frame_bits = bits[start_pos:start_pos+self.FRAME_LENGTH]
        frame = BitArray(frame_bits)
        
        # Extract frame header (first 32 bits)
        header = frame[0:32]
        
        # Extract frame type (first 4 bits)
        frame_type = header[0:4].uint
        
        # Extract frame number (next 8 bits)
        frame_number = header[4:12].uint
        
        # Parse additional fields based on frame type
        additional_info = {}
        
        # Map frame types (MAC PDU types for downlink)
        # ... (rest of function)
        
        frame_type_name = "Unknown"
        
        # Heuristic: If it's a TCH (Traffic Channel) burst, it might be Type 1 (Traffic)
        # But standard MAC PDUs use the values below.
        # We'll try to infer from context or just map standard PDUs
        
        if frame_type == 0:
            frame_type_name = "MAC-RESOURCE"
            additional_info['description'] = 'Resource allocation'
            if len(header) >= 24:
                additional_info['network_id'] = header[12:24].uint
        elif frame_type == 1:
            # Could be MAC-FRAG or Traffic depending on context
            # For this decoder, we'll assume Traffic if it looks like voice
            frame_type_name = "MAC-FRAG" 
            additional_info['description'] = 'Fragment'
        elif frame_type == 2:
            frame_type_name = "MAC-END"
            additional_info['description'] = 'End of transmission'
        elif frame_type == 3:
            frame_type_name = "MAC-BROADCAST"
            additional_info['description'] = 'Broadcast info'
        elif frame_type == 4:
            frame_type_name = "MAC-SUPPL"
            additional_info['description'] = 'Supplementary'
        elif frame_type == 5:
            frame_type_name = "MAC-U-SIGNAL" # Or D-MAC-SYNC?
            additional_info['description'] = 'Signaling'
        elif frame_type == 6:
            frame_type_name = "MAC-DATA"
            additional_info['description'] = 'User Data'
        elif frame_type == 7:
            frame_type_name = "MAC-U-BLK"
            additional_info['description'] = 'Block'
        else:
            frame_type_name = f"Type {frame_type}"
            additional_info['description'] = f'Raw type {frame_type}'

        # Extract encryption indicator - be aggressive, assume encrypted unless proven clear
        encrypted = True  # Default to encrypted
        encryption_algorithm = 'TEA1'  # Default algorithm
        key_id = '0'
        
        # Check for clear mode indicators
        # In MAC-RESOURCE (type 0), encryption flag is often at bit 39 (after fill bits)
        # This is highly dependent on PDU type.
        # Simplified check: Look for "Air Interface Encryption" element
        
        # For now, we'll rely on the protocol parser for detailed analysis
        # but keep the basic structure here
        
        frame_data = {
            'type': frame_type,
            'type_name': frame_type_name, # Add human readable name
            'number': frame_number,
            'bits': frame_bits,
            'header': header.bin,
            'position': start_pos,
            'encrypted': encrypted,
            'encryption_algorithm': encryption_algorithm,
            'key_id': key_id,
            'additional_info': additional_info
        }
        
        # Parse protocol layers (PHY/MAC/higher) - with error handling
        try:
            # Use provided symbols if available, otherwise reconstruct
            if symbols is None:
                # Reconstruct 0-3 symbols from bits
                symbols = []
                for i in range(0, len(frame_bits), 2):
                    val = (frame_bits[i] << 1) | frame_bits[i+1]
                    symbols.append(val)
                symbols = np.array(symbols)

            # Parse burst structure - be more lenient
            burst = self.protocol_parser.parse_burst(
                symbols, 
                slot_number=frame_number % 4
            )
            
            if burst:
                frame_data['burst_crc'] = burst.crc_ok
                
                # Parse MAC PDU even if CRC failed (may still be partially valid)
                try:
                    mac_pdu = self.protocol_parser.parse_mac_pdu(burst.data_bits)
                    
                    if mac_pdu:
                        frame_data['mac_pdu'] = {
                            'type': mac_pdu.pdu_type.name,
                            'encrypted': mac_pdu.encrypted,
                            'address': mac_pdu.address,
                            'length': mac_pdu.length,
                            'data': mac_pdu.data  # Add data field
                        }
                        
                        # Update encryption status from MAC PDU
                        # Be more conservative: only trust MAC PDU if we have strong evidence
                        if mac_pdu.encrypted:
                            # MAC PDU explicitly says encrypted - trust it
                            encrypted = True
                            frame_data['encrypted'] = True
                            if not encryption_algorithm:
                                encryption_algorithm = 'TEA1'
                                frame_data['encryption_algorithm'] = 'TEA1'
                        else:
                            # MAC PDU says not encrypted - verify with heuristics
                            # Check data entropy to confirm it's really clear mode
                            if len(mac_pdu.data) > 0:
                                # Calculate simple entropy check
                                unique_bytes = len(set(mac_pdu.data))
                                total_bytes = len(mac_pdu.data)
                                entropy_ratio = unique_bytes / max(total_bytes, 1)
                                
                                # Low entropy suggests clear mode (structured data)
                                # High entropy suggests encrypted (random-looking)
                                # Threshold: if >70% unique bytes, likely encrypted
                                if entropy_ratio > 0.7 and total_bytes > 8:
                                    # High entropy - likely encrypted despite flag
                                    logger.debug(f"Frame {frame_number}: High entropy ({entropy_ratio:.2f}) suggests encryption despite clear flag")
                                    encrypted = True
                                    frame_data['encrypted'] = True
                                else:
                                    # Low entropy - likely clear mode
                                    encrypted = False
                                    frame_data['encrypted'] = False
                                    frame_data['encryption_algorithm'] = None
                                    logger.debug(f"Frame {frame_number}: Low entropy ({entropy_ratio:.2f}) confirms clear mode")
                            else:
                                # No data to check - trust MAC PDU flag
                                encrypted = False
                                frame_data['encrypted'] = False
                                frame_data['encryption_algorithm'] = None
                        
                        # Extract call metadata if available
                        call_meta = self.protocol_parser.parse_call_metadata(mac_pdu)
                        if call_meta:
                            frame_data['call_metadata'] = {
                                'call_type': call_meta.call_type,
                                'talkgroup_id': call_meta.talkgroup_id,
                                'source_ssi': call_meta.source_ssi,
                                'dest_ssi': call_meta.dest_ssi,
                                'channel': call_meta.channel_allocated,
                                'encryption': call_meta.encryption_enabled,
                                'encryption_alg': call_meta.encryption_algorithm
                            }
                            
                            # Update additional_info with metadata
                            if call_meta.talkgroup_id:
                                additional_info['talkgroup'] = call_meta.talkgroup_id
                            if call_meta.source_ssi:
                                additional_info['source_ssi'] = call_meta.source_ssi
                        
                        # Try to decode SDS message if not encrypted
                        # Use reassembled data if available, otherwise use current PDU data
                        payload_to_decode = mac_pdu.reassembled_data if mac_pdu.reassembled_data else mac_pdu.data
                        
                        if not mac_pdu.encrypted and len(payload_to_decode) > 0:
                            # Try parsing as SDS message
                            sds_text = self.protocol_parser.parse_sds_data(payload_to_decode)
                            if sds_text and not sds_text.startswith("[BIN]"):  # Only if it's actual text, not hex
                                frame_data['sds_message'] = sds_text
                                frame_data['decoded_text'] = sds_text  # Always set decoded_text when sds_message exists
                                additional_info['sds_text'] = sds_text[:50]  # First 50 chars
                                
                                # If reassembled, mark it
                                if mac_pdu.reassembled_data:
                                    frame_data['is_reassembled'] = True
                                    additional_info['description'] += " (Reassembled)"
                except Exception as e:
                    logger.debug(f"MAC PDU parsing error: {e}")
                    # Continue even if MAC parsing fails
        except Exception as e:
            logger.debug(f"Protocol parsing error: {e}")
        
        # NOW attempt decryption if marked as encrypted
        if frame_data.get('encrypted') and (self.key_manager or self.auto_decrypt):
            frame_data = self._decrypt_frame(frame_data)
            
            # If decryption successful, try to parse SDS again with decrypted data
            if frame_data.get('decrypted') and 'decrypted_bytes' in frame_data:
                try:
                    # Create a temporary MacPDU with decrypted data
                    decrypted_bytes = bytes.fromhex(frame_data['decrypted_bytes'])
                    
                    # Use protocol parser to handle SDS data properly
                    sds_text = self.protocol_parser.parse_sds_data(decrypted_bytes)
                    if sds_text:
                        frame_data['sds_message'] = sds_text
                        frame_data['decoded_text'] = sds_text  # Ensure decoded_text is set
                        additional_info['sds_text'] = sds_text[:50]
                    else:
                        # Fallback: try to decode as text if it looks printable
                        printable_count = sum(1 for b in decrypted_bytes if 32 <= b <= 126 or b in (10, 13))
                        if len(decrypted_bytes) > 0 and (printable_count / len(decrypted_bytes)) > 0.7:
                            try:
                                text = decrypted_bytes.decode('latin-1', errors='replace')
                                # Remove null bytes and control chars except newline/carriage return
                                text = ''.join(c if (32 <= ord(c) <= 126 or c in '\n\r') else ' ' for c in text)
                                text = text.strip()
                                if text:
                                    frame_data['decoded_text'] = f"[TXT] {text}"
                                    frame_data['sds_message'] = frame_data['decoded_text']
                            except:
                                pass
                except Exception as e:
                    logger.debug(f"Error parsing decrypted SDS: {e}")
                    pass
        
        return frame_data

    def _decrypt_frame(self, frame_data: dict) -> dict:
        """
        Decrypt frame payload - AGGRESSIVE bruteforce with all common keys.
        Auto-tries common keys if no key manager or key not found.
        
        Args:
            frame_data: Frame data dictionary
            
        Returns:
            Updated frame data with decrypted payload
        """
        algorithm = frame_data.get('encryption_algorithm', 'TEA1')
        key_id = frame_data.get('key_id', '0')
        
        # Extract payload once (after header, typically starts at bit 32)
        payload_bits = frame_data['bits'][32:]
        
        # Convert to bytes
        try:
            payload_bytes = BitArray(payload_bits).tobytes()
        except Exception as e:
            frame_data['decrypted'] = False
            frame_data['decryption_error'] = f'Invalid payload format: {e}'
            logger.debug(f"Payload format error: {e}")
            return frame_data
        
        # Ensure payload is multiple of 8 bytes for block cipher
        if len(payload_bytes) < 8:
            frame_data['decrypted'] = False
            frame_data['decryption_error'] = 'Payload too short for decryption'
            return frame_data
        
        if len(payload_bytes) % 8 != 0:
            padding = 8 - (len(payload_bytes) % 8)
            payload_bytes += b'\x00' * padding
        
        keys_to_try = []
        
        # Try key from key manager first
        if self.key_manager and self.key_manager.has_key(algorithm, key_id):
            key = self.key_manager.get_key(algorithm, key_id)
            keys_to_try.append((key, f"{algorithm} key_id={key_id} (from file)"))
            logger.info(f"Trying key from file for {algorithm}")
        
        # ALWAYS add common keys for bruteforce (OpenEar style)
        if algorithm in self.common_keys:
            for idx, common_key in enumerate(self.common_keys[algorithm]):
                keys_to_try.append((common_key, f"{algorithm} common_key_{idx}"))
        
        # Add BYPASS attempt (treat as clear) - User requested "try common,bypass"
        # This handles cases where frames are marked encrypted but are actually clear (network config error)
        keys_to_try.append((None, "BYPASS (Treat as Clear)"))
        
        # Also try with other algorithms if primary fails
        for other_alg in ['TEA1', 'TEA2', 'TEA3', 'TEA4']:
            if other_alg != algorithm and other_alg in self.common_keys:
                for idx, common_key in enumerate(self.common_keys[other_alg][:5]):  # Try first 5
                    keys_to_try.append((common_key, f"{other_alg} common_key_{idx} (cross-try)"))
        
        # If no keys to try, bail out
        if not keys_to_try:
            frame_data['decrypted'] = False
            frame_data['decryption_error'] = 'No keys available'
            logger.warning("No keys available for decryption")
            return frame_data
        
        logger.info(f"Trying {len(keys_to_try)} keys for frame {frame_data['number']}")
        
        # Try each key
        best_result = None
        best_score = 0
        
        for key, key_desc in keys_to_try:
            try:
                if key is None:
                    # BYPASS mode - use payload as is
                    decrypted_payload = payload_bytes
                else:
                    decryptor = TEADecryptor(key, algorithm)
                    decrypted_payload = decryptor.decrypt(payload_bytes)
                
                # Score the decrypted data (how "good" it looks)
                # More lenient scoring for TETRA
                score = 0
                
                # Count printable ASCII (32-126)
                printable_count = sum(1 for b in decrypted_payload if 32 <= b <= 126)
                score += printable_count * 2
                
                # Check for reasonable byte distribution (not all same)
                unique_bytes = len(set(decrypted_payload))
                if unique_bytes > len(decrypted_payload) // 8:  # At least 12.5% unique (more lenient)
                    score += 30
                
                # Penalize all zeros or all 0xFF (but less)
                if decrypted_payload == b'\x00' * len(decrypted_payload):
                    score -= 50  # Less penalty
                if decrypted_payload == b'\xFF' * len(decrypted_payload):
                    score -= 50
                
                # Check for common TETRA patterns
                if len(decrypted_payload) >= 4:
                    # Look for reasonable header patterns
                    first_bytes = decrypted_payload[:4]
                    # Add points if it looks like structured data
                    if first_bytes[0] != 0 and first_bytes[0] != 0xFF:
                        score += 10
                    
                    # Check for TETRA-specific byte patterns (common in traffic)
                    # TETRA often has specific sync bytes
                    if first_bytes[0] in [0x01, 0x02, 0x03, 0x04, 0x05, 0x08, 0x0A, 0x0C]:
                        score += 20
                
                # More lenient entropy check
                if unique_bytes > 1:  # Any diversity is good
                    score += 10
                
                # --- Advanced Scoring: Try to parse as MAC PDU ---
                try:
                    # Convert bytes to bits for parser
                    decrypted_bits = []
                    for b in decrypted_payload:
                        for i in range(7, -1, -1):
                            decrypted_bits.append((b >> i) & 1)
                    decrypted_bits = np.array(decrypted_bits)
                    
                    # Check CRC if possible (heuristic)
                    if self.protocol_parser._check_crc(decrypted_bits):
                        score += 100  # Big bonus for valid CRC/Structure
                        
                    # Try to parse as MAC PDU
                    pdu = self.protocol_parser.parse_mac_pdu(decrypted_bits)
                    if pdu and pdu.pdu_type != self.protocol_parser.PDUType.MAC_DATA: # If it parses as a specific type
                         score += 50
                except:
                    pass
                
                if score > best_score:
                    best_score = score
                    best_result = (decrypted_payload, key_desc)
                
                # Lower threshold - accept more attempts
                if score > 80:  # Was 50, increased due to CRC bonus
                    logger.info(f"Good decryption score {score} with {key_desc}")
                    break
                    
            except Exception as e:
                logger.debug(f"Key {key_desc} failed: {e}")
                continue
        
        # Use the best result if we found one (more lenient threshold)
        if best_result and best_score > 10:  # Was > 0, now > 10 to avoid total garbage
            decrypted_payload, key_desc = best_result
            
            # Convert back to bits
            decrypted_bits = BitArray(decrypted_payload)
            
            frame_data['decrypted'] = True
            frame_data['decrypted_payload'] = decrypted_bits.bin
            frame_data['decrypted_bytes'] = decrypted_payload.hex()
            frame_data['key_used'] = key_desc
            frame_data['decrypt_confidence'] = best_score
            
            # Update algorithm if detected from key
            if "TEA1" in key_desc: frame_data['encryption_algorithm'] = "TEA1"
            elif "TEA2" in key_desc: frame_data['encryption_algorithm'] = "TEA2"
            elif "TEA3" in key_desc: frame_data['encryption_algorithm'] = "TEA3"
            elif "TEA4" in key_desc: frame_data['encryption_algorithm'] = "TEA4"
            
            logger.info(f"[OK] Decrypted frame {frame_data['number']} using {key_desc} (confidence: {best_score})")
        else:
            # All keys failed or low confidence
            frame_data['decrypted'] = False
            if not keys_to_try:
                frame_data['decryption_error'] = 'No keys available'
            else:
                frame_data['decryption_error'] = f'Tried {len(keys_to_try)} key(s), best score: {best_score}'
                logger.debug(f"All keys failed for frame {frame_data['number']}, best score: {best_score}")
        
        return frame_data
    
    def decode(self, symbols):
        """
        Decode TETRA frames from symbol stream.
        """
        # Convert symbols to bits and mapped symbols (0-3)
        bits, mapped_symbols = self.symbols_to_bits(symbols)
        
        # Find synchronization patterns (Training Sequence)
        # Use progressively lower thresholds to catch weaker/noisy signals
        sync_positions = self.find_sync(bits, threshold=0.75)
        
        if not sync_positions:
            sync_positions = self.find_sync(bits, threshold=0.65)  # Lowered from 0.70
            if not sync_positions:
                sync_positions = self.find_sync(bits, threshold=0.55)  # Even more lenient
                if not sync_positions:
                    # If still no sync found, try to decode at regular intervals anyway
                    # This helps with signals that have sync but it's corrupted
                    # TETRA slots are 510 bits, so try every 510 bits
                    if len(bits) >= self.FRAME_LENGTH:
                        # Try decoding from start of bit stream (might be misaligned)
                        sync_positions = [0]
        
        # Decode frames
        frames = []
        for pos in sync_positions:
            # Adjust position to start of burst
            # TS starts at bit 216 (symbol 108)
            # But we need to be careful about array bounds
            start_pos = pos - 216
            
            if start_pos >= 0:
                # Extract symbols for this frame
                # 255 symbols = 510 bits
                start_sym = start_pos // 2
                if start_sym + 255 <= len(mapped_symbols):
                    frame_symbols = mapped_symbols[start_sym : start_sym + 255]
                    
                    # Reconstruct bits for decode_frame (it expects bits)
                    # But decode_frame logic for header/type is based on bits
                    # We pass the bits corresponding to the frame
                    frame_bits = bits[start_pos : start_pos + 510]
                    
                    # Calculate a pseudo frame number based on position
                    # Assuming continuous stream, 510 bits per timeslot
                    current_frame_num = start_pos // 510
                    
                    frame = self.decode_frame(frame_bits, 0, frame_symbols, frame_number=current_frame_num)
                    if frame:
                        frames.append(frame)
                        logger.info(f"Decoded frame {frame['number']} (type: {frame['type']})")
        
        return frames

    def decode_frame(self, bits, start_pos, symbols=None, frame_number=0):
        """
        Decode a TETRA frame.
        """
        if len(bits) < self.FRAME_LENGTH:
            return None
            
        frame_bits = bits
        frame = BitArray(frame_bits)
        
        # Extract frame header (first 32 bits)
        header = frame[0:32]
        
        # Extract frame type (first 2 bits for MAC PDU type)
        # The previous logic took 4 bits, which confused PDU Type with Encryption Mode
        # Standard Downlink MAC PDU Type is 2 bits.
        pdu_type_int = header[0:2].uint
        
        # Encryption Mode is usually next 2 bits (bits 2-3)
        encryption_mode_int = header[2:4].uint
        
        # Extract frame number (next 8 bits? No, frame number is not in MAC header)
        # Frame number is passed from the burst/slot counter in the decoder loop
        # We'll keep using the passed 'frame_number' or 'number' from arguments if available
        # But here we are parsing the bits.
        
        # Let's stick to the previous structure but fix the type mapping
        frame_type = pdu_type_int
        
        # Parse additional fields based on frame type
        additional_info = {}
        
        frame_type_name = "Unknown"
        
        if frame_type == 0:
            frame_type_name = "MAC-RESOURCE"
            additional_info['description'] = 'Resource allocation'
            # Network ID is not in fixed position, depends on TM-SDU
        elif frame_type == 1:
            frame_type_name = "MAC-FRAG" 
            additional_info['description'] = 'Fragment'
        elif frame_type == 2:
            frame_type_name = "MAC-BROADCAST"
            additional_info['description'] = 'Broadcast info'
        elif frame_type == 3:
            # Type 3 is often MAC-END or MAC-U-SIGNAL depending on context
            # For Downlink, 11 is often reserved or proprietary, or MAC-D-BLCK
            frame_type_name = "MAC-END/RES"
            additional_info['description'] = 'End/Reserved'
        else:
            frame_type_name = f"Type {frame_type}"
            additional_info['description'] = f'Raw type {frame_type}'

        # Extract encryption indicator
        # Encryption Mode: 0=Clear, 1=SCK, 2=DCK, 3=Reserved
        encrypted = encryption_mode_int > 0
        encryption_algorithm = None
        
        if encryption_mode_int == 1:
            encryption_algorithm = 'TEA1' # Default assumption for Class 2
            additional_info['encryption_mode'] = 'Class 2 (SCK)'
        elif encryption_mode_int == 2:
            encryption_algorithm = 'TEA2' # Default assumption for Class 3
            additional_info['encryption_mode'] = 'Class 3 (DCK)'
        elif encryption_mode_int == 3:
            encryption_algorithm = 'TEA3' # Assumption
            additional_info['encryption_mode'] = 'Reserved'
            
        key_id = '0'
        
        frame_data = {
            'type': frame_type,
            'type_name': frame_type_name, # Add human readable name
            'number': frame_number,
            'timeslot': frame_number % 4,  # Add timeslot (0-3)
            'bits': frame_bits,
            'header': header.bin,
            'position': start_pos,
            'encrypted': encrypted,
            'encryption_algorithm': encryption_algorithm,
            'key_id': key_id,
            'additional_info': additional_info
        }
        
        # Parse protocol layers
        try:
            # Use provided symbols if available, otherwise reconstruct
            if symbols is None:
                # Reconstruct 0-3 symbols from bits
                symbols = []
                for i in range(0, len(frame_bits), 2):
                    val = (frame_bits[i] << 1) | frame_bits[i+1]
                    symbols.append(val)
                symbols = np.array(symbols)

            # Parse burst structure
            burst = self.protocol_parser.parse_burst(
                symbols, 
                slot_number=frame_number % 4
            )
            
            if burst:
                frame_data['burst_crc'] = burst.crc_ok
                
                # Parse MAC PDU even if CRC failed (may still be partially valid)
                try:
                    mac_pdu = self.protocol_parser.parse_mac_pdu(burst.data_bits)
                    
                    if mac_pdu:
                        frame_data['mac_pdu'] = {
                            'type': mac_pdu.pdu_type.name,
                            'encrypted': mac_pdu.encrypted,
                            'address': mac_pdu.address,
                            'length': mac_pdu.length,
                            'data': mac_pdu.data  # Add data field
                        }
                        
                        # Update encryption status from MAC PDU
                        if mac_pdu.encrypted:
                            encrypted = True
                            frame_data['encrypted'] = True
                            
                            # Use encryption mode to hint algorithm
                            # 0=Clear, 1=Class2(TEA1/2), 2=Class3(TEA2/3/4), 3=Reserved
                            enc_mode = getattr(mac_pdu, 'encryption_mode', 0)
                            
                            if enc_mode == 1:
                                # Class 2 - usually TEA1, sometimes TEA2
                                encryption_algorithm = 'TEA1'
                                frame_data['encryption_algorithm'] = 'TEA1'
                                additional_info['encryption_mode'] = 'Class 2 (SCK)'
                            elif enc_mode == 2:
                                # Class 3 - usually TEA2, sometimes TEA3/4
                                encryption_algorithm = 'TEA2'
                                frame_data['encryption_algorithm'] = 'TEA2'
                                additional_info['encryption_mode'] = 'Class 3 (DCK)'
                            elif enc_mode == 3:
                                # Reserved - assume TEA3/4
                                encryption_algorithm = 'TEA3'
                                frame_data['encryption_algorithm'] = 'TEA3'
                                additional_info['encryption_mode'] = 'Reserved'
                            else:
                                # Default
                                if not encryption_algorithm:
                                    encryption_algorithm = 'TEA1'
                                    frame_data['encryption_algorithm'] = 'TEA1'
                        else:
                            # Check data entropy
                            if len(mac_pdu.data) > 0:
                                unique_bytes = len(set(mac_pdu.data))
                                total_bytes = len(mac_pdu.data)
                                entropy_ratio = unique_bytes / max(total_bytes, 1)
                                
                                if entropy_ratio > 0.7 and total_bytes > 8:
                                    encrypted = True
                                    frame_data['encrypted'] = True
                                else:
                                    encrypted = False
                                    frame_data['encrypted'] = False
                                    frame_data['encryption_algorithm'] = None
                            else:
                                encrypted = False
                                frame_data['encrypted'] = False
                                frame_data['encryption_algorithm'] = None
                        
                        # Extract call metadata
                        call_meta = self.protocol_parser.parse_call_metadata(mac_pdu)
                        if call_meta:
                            frame_data['call_metadata'] = {
                                'call_type': call_meta.call_type,
                                'talkgroup_id': call_meta.talkgroup_id,
                                'source_ssi': call_meta.source_ssi,
                                'dest_ssi': call_meta.dest_ssi,
                                'channel': call_meta.channel_allocated,
                                'call_identifier': call_meta.call_identifier,
                                'priority': call_meta.call_priority,
                                'mcc': call_meta.mcc,
                                'mnc': call_meta.mnc,
                                'encryption': call_meta.encryption_enabled,
                                'encryption_alg': call_meta.encryption_algorithm
                            }
                            if call_meta.talkgroup_id:
                                additional_info['talkgroup'] = call_meta.talkgroup_id
                            if call_meta.source_ssi:
                                additional_info['source_ssi'] = call_meta.source_ssi
                            if call_meta.mcc:
                                additional_info['mcc'] = call_meta.mcc
                            if call_meta.mnc:
                                additional_info['mnc'] = call_meta.mnc
                        
                        # Try to decode SDS message
                        payload_to_decode = mac_pdu.reassembled_data if mac_pdu.reassembled_data else mac_pdu.data
                        
                        if not mac_pdu.encrypted and len(payload_to_decode) > 0:
                            sds_text = self.protocol_parser.parse_sds_data(payload_to_decode)
                            if sds_text and not sds_text.startswith("[BIN]"):
                                frame_data['sds_message'] = sds_text
                                frame_data['decoded_text'] = sds_text
                                additional_info['sds_text'] = sds_text[:50]
                                if mac_pdu.reassembled_data:
                                    frame_data['is_reassembled'] = True
                                    additional_info['description'] += " (Reassembled)"
                except Exception as e:
                    logger.debug(f"MAC PDU parsing error: {e}")

        except Exception as e:
            logger.debug(f"Protocol parsing error: {e}")
        
        # Decryption logic
        if frame_data.get('encrypted') and (self.key_manager or self.auto_decrypt):
            frame_data = self._decrypt_frame(frame_data)
            if frame_data.get('decrypted') and 'decrypted_bytes' in frame_data:
                try:
                    decrypted_bytes = bytes.fromhex(frame_data['decrypted_bytes'])
                    sds_text = self.protocol_parser.parse_sds_data(decrypted_bytes)
                    if sds_text:
                        frame_data['sds_message'] = sds_text
                        frame_data['decoded_text'] = sds_text
                        additional_info['sds_text'] = sds_text[:50]
                except:
                    pass
        
        return frame_data

    def format_frame_info(self, frame):
        info = f"Frame #{frame['number']} (Type: {self._get_frame_type_name(frame['type'])})"
        info += f"\n  Position: {frame['position']}"
        info += f"\n  Header: {frame['header'][:32]}..."
        
        # Add frame type specific info
        frame_type = frame['type']
        if frame_type == 0:
            info += "\n  📡 MAC-RESOURCE - Resource allocation/Start of message"
        elif frame_type == 1:
            info += "\n  📞 MAC-FRAG - Message fragment"
        elif frame_type == 2:
            info += "\n  🔗 MAC-END - End of message"
        elif frame_type == 3:
            info += "\n  📋 MAC-BROADCAST - Broadcast information"
        
        # Show SDS message if available (PRIORITY)
        if 'sds_message' in frame and frame['sds_message']:
            info += f"\n  💬 Message: {frame['sds_message']}"
        elif 'decoded_text' in frame and frame['decoded_text']:
            info += f"\n  💬 Text: {frame['decoded_text']}"
        
        # Show encryption status
        if frame.get('encrypted'):
            info += f"\n  [ENC] Encrypted: Yes ({frame.get('encryption_algorithm', 'Unknown')})"
            if frame.get('decrypted'):
                info += f"\n  [DEC] Decrypted: Yes"
                if 'key_used' in frame:
                    info += f" - {frame['key_used']}"
                if 'decrypted_bytes' in frame and not frame.get('sds_message'):
                    # Try to interpret payload
                    payload_hex = frame['decrypted_bytes'][:64]
                    info += f"\n  [PAY] Payload (hex): {payload_hex}..."
            else:
                info += f"\n  [ERR] Decrypted: No"
                if 'decryption_error' in frame:
                    info += f" ({frame['decryption_error']})"
        else:
            info += f"\n  [CLR] Encrypted: No"
            
            # Show MAC PDU data if available and no SDS message
            if 'mac_pdu' in frame and 'data' in frame['mac_pdu'] and not frame.get('sds_message'):
                data = frame['mac_pdu']['data']
                if isinstance(data, (bytes, bytearray)) and len(data) > 0:
                    # Try to show as text first
                    printable_count = sum(1 for b in data if 32 <= b <= 126 or b in (10, 13))
                    if (printable_count / len(data)) > 0.7:
                        try:
                            text = data.decode('latin-1', errors='replace').strip()
                            if text:
                                info += f"\n  [TXT] Data: {text[:80]}"
                            else:
                                info += f"\n  [HEX] Data: {data.hex()[:64]}..."
                        except:
                            info += f"\n  [HEX] Data: {data.hex()[:64]}..."
                    else:
                        info += f"\n  [HEX] Data: {data.hex()[:64]}..."
        
        # Show reassembly status
        if frame.get('is_reassembled'):
            info += "\n  ✅ (Reassembled from fragments)"
        
        # Show voice indicator
        if frame.get('has_voice'):
            info += "\n  🔊 Contains voice data"
        
        return info
    
    def _get_frame_type_name(self, frame_type):
        """Get human-readable frame type name."""
        frame_types = {
            0: "Broadcast",
            1: "Traffic",
            2: "Control", 
            3: "MAC",
            4: "Supplementary",
            5: "Reserved",
            6: "Reserved",
            7: "Reserved"
        }
        return frame_types.get(frame_type, f"Unknown({frame_type})")

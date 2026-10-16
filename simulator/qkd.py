import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional
import json
class BB84QKDSimulator:
    def __init__(self, key_length: int = 256, error_threshold: float = 0.15, fast_mode: bool = True):
        self.key_length = key_length
        self.error_threshold = error_threshold
        self.fast_mode = fast_mode
        self.simulator = AerSimulator()
        if fast_mode:
            self.raw_key_multiplier = 2  
            self.sample_size = min(32, key_length // 8)  
        else:
            self.raw_key_multiplier = 4  
            self.sample_size = max(64, key_length // 4)  
    def generate_random_bits(self, length: int) -> List[int]:
        return [secrets.randbelow(2) for _ in range(length)]
    def generate_random_bases(self, length: int) -> List[int]:
        return [secrets.randbelow(2) for _ in range(length)]
    def create_bb84_states(self, bits: List[int], bases: List[int]) -> List[QuantumCircuit]:
        circuits = []
        for bit, basis in zip(bits, bases):
            qc = QuantumCircuit(1, 1)
            if basis == 0:  
                if bit == 1:
                    qc.x(0)  
            else:  
                if bit == 0:
                    qc.h(0)  
                else:
                    qc.x(0)
                    qc.h(0)  
            circuits.append(qc)
        return circuits
    def measure_bb84_states(self, circuits: List[QuantumCircuit], 
                           bob_bases: List[int]) -> List[int]:
        if self.fast_mode and len(circuits) > 50:
            return self._measure_bb84_states_batch(circuits, bob_bases)
        measurements = []
        for qc, bob_basis in zip(circuits, bob_bases):
            measure_qc = qc.copy()
            if bob_basis == 1:  
                measure_qc.h(0)  
            measure_qc.measure(0, 0)
            transpiled_qc = transpile(measure_qc, self.simulator)
            job = self.simulator.run(transpiled_qc, shots=1)
            result = job.result()
            counts = result.get_counts()
            measured_bit = int(list(counts.keys())[0])
            measurements.append(measured_bit)
        return measurements
    def _measure_bb84_states_batch(self, circuits: List[QuantumCircuit], 
                                  bob_bases: List[int]) -> List[int]:
        measurements = []
        batch_size = 50  
        for i in range(0, len(circuits), batch_size):
            batch_circuits = circuits[i:i+batch_size]
            batch_bases = bob_bases[i:i+batch_size]
            measure_circuits = []
            for qc, bob_basis in zip(batch_circuits, batch_bases):
                measure_qc = qc.copy()
                if bob_basis == 1:  
                    measure_qc.h(0)
                measure_qc.measure(0, 0)
                measure_circuits.append(measure_qc)
            transpiled_circuits = transpile(measure_circuits, self.simulator)
            job = self.simulator.run(transpiled_circuits, shots=1)
            result = job.result()
            for j, qc in enumerate(measure_circuits):
                counts = result.get_counts(j)
                measured_bit = int(list(counts.keys())[0])
                measurements.append(measured_bit)
        return measurements
    def sift_key(self, alice_bits: List[int], alice_bases: List[int],
                 bob_measurements: List[int], bob_bases: List[int]) -> Tuple[List[int], List[int]]:
        alice_sifted = []
        bob_sifted = []
        for i, (a_basis, b_basis) in enumerate(zip(alice_bases, bob_bases)):
            if a_basis == b_basis:  
                alice_sifted.append(alice_bits[i])
                bob_sifted.append(bob_measurements[i])
        return alice_sifted, bob_sifted
    def estimate_error_rate(self, alice_key: List[int], bob_key: List[int],
                           sample_size: int) -> float:
        if len(alice_key) < sample_size:
            sample_size = len(alice_key) // 2
        if sample_size == 0:
            return 0.0
        total_length = len(alice_key)
        sample_positions = secrets.SystemRandom().sample(range(total_length), sample_size)
        errors = 0
        for pos in sample_positions:
            if alice_key[pos] != bob_key[pos]:
                errors += 1
        return errors / sample_size
    def add_channel_noise(self, circuits: List[QuantumCircuit], 
                         noise_level: float = 0.05) -> List[QuantumCircuit]:
        noisy_circuits = []
        for qc in circuits:
            noisy_qc = qc.copy()
            if secrets.SystemRandom().random() < noise_level:
                noisy_qc.x(0)  
            noisy_circuits.append(noisy_qc)
        return noisy_circuits
    def add_measurement_noise(self, measurements: List[int], 
                             noise_level: float = 0.05) -> List[int]:
        noisy_measurements = []
        for measurement in measurements:
            if secrets.SystemRandom().random() < noise_level:
                noisy_measurements.append(1 - measurement)
            else:
                noisy_measurements.append(measurement)
        return noisy_measurements
    def generate_qkd_key(self, target_length: int = None, 
                        eavesdropper_present: bool = False) -> Dict:
        if target_length is None:
            target_length = self.key_length
        raw_length = target_length * self.raw_key_multiplier
        if raw_length > 100:  
            print(f"  🔬 BB84 Protocol: Generating {raw_length} raw bits for {target_length}-bit key...")
        alice_bits = self.generate_random_bits(raw_length)
        alice_bases = self.generate_random_bases(raw_length)
        quantum_states = self.create_bb84_states(alice_bits, alice_bases)
        base_noise = 0.01 + (secrets.SystemRandom().random() * 0.07)  
        if eavesdropper_present:
            base_noise += 0.08 + (secrets.SystemRandom().random() * 0.12)  
        noisy_states = self.add_channel_noise(quantum_states, base_noise)
        bob_bases = self.generate_random_bases(raw_length)
        bob_measurements = self.measure_bb84_states(noisy_states, bob_bases)
        measurement_noise = 0.005 + (secrets.SystemRandom().random() * 0.015)  
        bob_measurements = self.add_measurement_noise(bob_measurements, measurement_noise)
        alice_sifted, bob_sifted = self.sift_key(alice_bits, alice_bases, 
                                               bob_measurements, bob_bases)
        error_rate = self.estimate_error_rate(alice_sifted, bob_sifted, 
                                            self.sample_size)
        if len(alice_sifted) >= target_length:
            final_key = alice_sifted[:target_length]
        else:
            final_key = alice_sifted
            while len(final_key) < target_length:
                additional_bits = self.generate_random_bits(
                    min(32, target_length - len(final_key))
                )
                final_key.extend(additional_bits)
            final_key = final_key[:target_length]
        hex_key = self._bits_to_hex(final_key)
        sifting_efficiency = len(alice_sifted) / len(alice_bits) if alice_bits else 0
        quantum_fidelity = 1.0 - error_rate
        fidelity_variation = (secrets.SystemRandom().random() - 0.5) * 0.02  
        quantum_fidelity = max(0.0, min(1.0, quantum_fidelity + fidelity_variation))
        if error_rate <= 0.02 and quantum_fidelity >= 0.98:
            security_level = 1  
        elif error_rate <= 0.05 and quantum_fidelity >= 0.95:
            security_level = 2  
        elif error_rate <= 0.10 and quantum_fidelity >= 0.90:
            security_level = 3  
        elif error_rate <= 0.15 and quantum_fidelity >= 0.85:
            security_level = 4  
        else:
            security_level = 5  
        timestamp = int(time.time() * 1000)
        key_id = f"qkd_bb84_{timestamp}_{secrets.randbelow(1000)}"
        qkd_key_data = {
            "key_id": key_id,
            "key": hex_key,
            "metadata": {
                "length": len(final_key),
                "error_rate": round(error_rate, 4),
                "protocol": "BB84",
                "security_level": security_level,
                "fidelity": round(quantum_fidelity, 4),
                "distance_km": round(10 + (secrets.randbelow(90)), 1),  
                "sifting_efficiency": round(sifting_efficiency, 4),
                "raw_bits_generated": len(alice_bits),
                "sifted_bits": len(alice_sifted),
                "sample_size": self.sample_size,
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'),
                "status": "available",
                "quantum_parameters": {
                    "basis_reconciliation_rate": round(sifting_efficiency, 4),
                    "channel_noise_level": round(base_noise, 4),
                    "measurement_noise_level": round(measurement_noise, 4),
                    "total_noise_level": round(base_noise + measurement_noise, 4),
                    "eavesdropper_detected": error_rate > self.error_threshold,
                    "bb84_efficiency": round(len(final_key) / raw_length, 4)
                }
            }
        }
        return qkd_key_data
    def _bits_to_hex(self, bits: List[int]) -> str:
        padded_bits = bits[:]
        while len(padded_bits) % 4 != 0:
            padded_bits.append(0)
        hex_string = ""
        for i in range(0, len(padded_bits), 4):
            nibble = padded_bits[i:i+4]
            hex_value = 0
            for j, bit in enumerate(nibble):
                hex_value += bit * (2 ** (3-j))
            hex_string += format(hex_value, 'x')
        return hex_string
    def generate_multiple_keys(self, count: int = 5, key_length: int = None) -> List[Dict]:
        keys = []
        for i in range(count):
            eavesdropper = secrets.SystemRandom().random() < 0.1
            key_data = self.generate_qkd_key(
                target_length=key_length,
                eavesdropper_present=eavesdropper
            )
            keys.append(key_data)
            time.sleep(0.1)
        return keys
    def validate_key_security(self, key_data: Dict) -> Dict:
        metadata = key_data.get("metadata", {})
        error_rate = metadata.get("error_rate", 0)
        fidelity = metadata.get("fidelity", 1)
        validation = {
            "is_secure": error_rate <= self.error_threshold,
            "security_grade": metadata.get("security_level", 4),
            "recommendations": []
        }
        if error_rate > self.error_threshold:
            validation["recommendations"].append(
                f"ERROR RATE TOO HIGH: {error_rate*100:.2f}% > {self.error_threshold*100}% threshold"
            )
        if fidelity < 0.85:
            validation["recommendations"].append(
                f"LOW FIDELITY: {fidelity:.3f} < 0.85 minimum"
            )
        if metadata.get("quantum_parameters", {}).get("eavesdropper_detected", False):
            validation["recommendations"].append("EAVESDROPPING DETECTED: Consider key rejection")
        return validation
def create_bb84_simulator(fast_mode: bool = True) -> BB84QKDSimulator:
    return BB84QKDSimulator(key_length=256, error_threshold=0.15, fast_mode=fast_mode)
def test_bb84_simulation():
    print("🔬 Testing BB84 QKD Simulator...")
    simulator = create_bb84_simulator()
    print("\n📝 Generating single QKD key...")
    key_data = simulator.generate_qkd_key()
    print(f"✅ Key ID: {key_data['key_id']}")
    print(f"🔑 Key Length: {key_data['metadata']['length']} bits")
    print(f"📊 Error Rate: {key_data['metadata']['error_rate']*100:.2f}%")
    print(f"🎯 Fidelity: {key_data['metadata']['fidelity']:.3f}")
    print(f"🔒 Security Level: {key_data['metadata']['security_level']}")
    validation = simulator.validate_key_security(key_data)
    print(f"✅ Security Valid: {validation['is_secure']}")
    print("\n📝 Generating multiple QKD keys...")
    keys = simulator.generate_multiple_keys(count=3)
    for i, key in enumerate(keys):
        print(f"Key {i+1}: {key['key_id']} "
              f"(Level {key['metadata']['security_level']}, "
              f"{key['metadata']['error_rate']*100:.1f}% error)")
    print("\n✅ BB84 QKD Simulator test completed!")
    return key_data
if __name__ == "__main__":
    test_bb84_simulation()

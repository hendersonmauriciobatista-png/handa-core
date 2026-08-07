# ============================================================
# core/sensors/volume_sensor.py
# Sensor institucional de volume do H&A
# ============================================================

from enum import Enum


class VolumeState(Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class VolumeSensor:
    """
    Detecta intensidade de volume no mercado.
    """

    @staticmethod
    def detect(volume_ratio: float) -> VolumeState:

        if volume_ratio > 1.5:
            return VolumeState.HIGH

        if volume_ratio > 1.2:
            return VolumeState.MODERATE

        return VolumeState.LOW
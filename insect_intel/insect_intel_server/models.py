from django.db import models

class Device(models.Model):
    device_id = models.CharField(max_length=50, unique=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.device_id

class DeviceDiagnostic(models.Model):
    # Identity
    device_id = models.CharField(max_length=50)
    received_at = models.DateTimeField(auto_now_add=True)
    device_timestamp = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(blank=True, null=True)

    # Status Indicators

    # Battery State
    soc = models.IntegerField(null=True, blank=True)
    soh = models.IntegerField(null=True, blank=True)
    cycles = models.IntegerField(null=True, blank=True)
    lowbattery = models.BooleanField(default=False)

    # Voltages & Currents (Units: mV, mA, mW)
    vbat = models.IntegerField(null=True, blank=True)
    ibat = models.IntegerField(null=True, blank=True)
    vchg = models.IntegerField(null=True, blank=True)
    vsys = models.IntegerField(null=True, blank=True)
    ichg = models.IntegerField(null=True, blank=True)
    avgi = models.IntegerField(null=True, blank=True)
    avgpwr = models.IntegerField(null=True, blank=True)

    # Temperatures
    gtmp = models.IntegerField(null=True, blank=True) # °C
    ctmp = models.IntegerField(null=True, blank=True) # °C
    btmp = models.IntegerField(null=True, blank=True) # dC (tenths of °C)

    # System State
    state = models.CharField(max_length=50, null=True, blank=True)
    wake = models.CharField(max_length=50, null=True, blank=True)
    adapter = models.BooleanField(default=False)

    # Connectivity (STM)
    lte_stat = models.IntegerField(null=True, blank=True) # 1=LTE, 0=WiFi
    lte_sig = models.IntegerField(null=True, blank=True)  # dBm
    sim_pres = models.BooleanField(default=False)
    sim_num = models.CharField(max_length=50, null=True, blank=True)
    net = models.CharField(max_length=50, null=True, blank=True)
    wifi_stat = models.IntegerField(null=True, blank=True)
    last_comm_epoch = models.BigIntegerField(null=True, blank=True)
    sd_pres = models.BooleanField(default=False)
    sd_free = models.IntegerField(null=True, blank=True) # MB
    lte_sent = models.IntegerField(null=True, blank=True)
    cam_res = models.CharField(max_length=20, null=True, blank=True)

    # Unit Configuration (MSPM0 Snapshot)
    cfg_wake_interval = models.IntegerField(null=True, blank=True)
    cfg_vreg = models.IntegerField(null=True, blank=True)
    cfg_ichg = models.IntegerField(null=True, blank=True)
    cfg_iindpm = models.IntegerField(null=True, blank=True)
    cfg_vindpm = models.IntegerField(null=True, blank=True)
    cfg_vsysmin = models.IntegerField(null=True, blank=True)
    cfg_iprechg = models.IntegerField(null=True, blank=True)
    cfg_iterm = models.IntegerField(null=True, blank=True)

    # Flags (hex strings)
    safety = models.CharField(max_length=20, null=True, blank=True)
    battstat = models.CharField(max_length=20, null=True, blank=True)
    chgflags = models.CharField(max_length=20, null=True, blank=True)
    faultflags = models.CharField(max_length=20, null=True, blank=True)
    chgstat = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"Diagnostic for {self.device_id} at {self.received_at.isoformat()}"

    @property
    def btmp_c(self):
        return self.btmp / 10.0 if self.btmp is not None else None

    @property
    def gtmp_c(self):
        return self.gtmp

    @property
    def ctmp_c(self):
        return self.ctmp

    @property
    def vbat_v(self):
        return self.vbat / 1000.0 if self.vbat is not None else None

    @property
    def vchg_v(self):
        return self.vchg / 1000.0 if self.vchg is not None else None

    @property
    def vsys_v(self):
        return self.vsys / 1000.0 if self.vsys is not None else None

    @property
    def connection_type(self):
        if self.lte_stat == 1:
            return "LTE"
        elif self.lte_stat == 0:
            return "WiFi"
        return "Unknown"

    @property
    def signal_quality(self):
        if self.lte_sig is None:
            return "N/A"
        if self.lte_sig > -70:
            return "Excellent"
        if self.lte_sig > -85:
            return "Good"
        if self.lte_sig > -100:
            return "Fair"
        return "Poor"

    @property
    def last_comm_time(self):
        if self.last_comm_epoch:
            from datetime import datetime, timezone
            return datetime.fromtimestamp(self.last_comm_epoch, tz=timezone.utc)
        return None

    def get_decoded_alerts(self):
        """
        Decodes hex flags into human-readable alerts.
        Returns a list of dicts: {'type': 'FAULT'|'INFO', 'msg': 'text'}
        """
        alerts = []
        
        # 1. BQ27Z746 SafetyStatus (32-bit)
        if self.safety:
            try:
                val = int(self.safety, 16)
                safety_map = {
                    0x00000001: "CUV: Cell Undervoltage",
                    0x00000002: "COV: Cell Overvoltage",
                    0x00000004: "OCC: Overcurrent During Charge",
                    0x00000010: "OCD: Overcurrent During Discharge",
                    0x00000040: "HOCD: Overload During Discharge",
                    0x00000100: "HOCC: Short-Circuit During Charge",
                    0x00000400: "HSCD: Hardware Short-Circuit Discharge",
                    0x00001000: "OTC: Over-Temperature During Charge",
                    0x00002000: "OTD: Over-Temperature During Discharge",
                    0x00010000: "OTF: Over-Temperature FET",
                    0x00040000: "PTO: Precharge Timeout",
                    0x00100000: "CTO: Charge Timeout",
                    0x04000000: "UTC: Under-Temperature During Charge",
                    0x08000000: "UTD: Under-Temperature During Discharge",
                    0x40000000: "HCOV: Hardware Cell Overvoltage",
                    0x80000000: "HCUV: Hardware Cell Undervoltage",
                }
                for mask, msg in safety_map.items():
                    if val & mask:
                        alerts.append({'type': 'FAULT', 'msg': msg})
            except ValueError:
                pass

        # 2. BQ27Z746 BatteryStatus (16-bit)
        if self.battstat:
            try:
                val = int(self.battstat, 16)
                status_map = {
                    (1 << 4): "FD: Fully Discharged",
                    (1 << 5): "FC: Fully Charged",
                    (1 << 9): "RCA: Remaining Capacity Alarm",
                    (1 << 11): "TDA: Terminate Discharge Alarm",
                    (1 << 12): "OTA: Over Temperature Alarm",
                    (1 << 14): "OCA: Over Charge Alarm",
                }
                for mask, msg in status_map.items():
                    if val & mask:
                        alerts.append({'type': 'INFO', 'msg': msg})
                if val & (1 << 6):
                    alerts.append({'type': 'INFO', 'msg': "Discharging"})
                else:
                    alerts.append({'type': 'INFO', 'msg': "Charging"})
            except ValueError:
                pass

        # 3. BQ25628E Charger Faults
        if self.faultflags:
            try:
                val = int(self.faultflags, 16)
                if val & (1 << 7): alerts.append({'type': 'FAULT', 'msg': "VBUS: Over-Voltage or Sleep"})
                if val & (1 << 6): alerts.append({'type': 'FAULT', 'msg': "BAT: Discharge OCP or VBAT OVP"})
                if val & (1 << 5): alerts.append({'type': 'FAULT', 'msg': "SYS: System Over-Voltage or Short Circuit"})
                if val & (1 << 3): alerts.append({'type': 'FAULT', 'msg': "THERMAL: IC Thermal Shutdown"})
                if val & (1 << 0): alerts.append({'type': 'INFO', 'msg': "TS: Temperature status change"})
            except ValueError:
                pass

        # 4. BQ25628E Charge Status
        if self.chgstat:
            try:
                # Based on bits 4:3
                val = int(self.chgstat, 16)
                chg_code = (val & 0x18) >> 3
                modes = {
                    0: "Not Charging / Terminated",
                    1: "Pre/Trickle/Fast Charge",
                    2: "Taper Charge (CV)",
                    3: "Top-off Timer Active"
                }
                alerts.append({'type': 'INFO', 'msg': f"Charger: {modes.get(chg_code, 'Unknown')}"})
            except ValueError:
                pass

        if self.lowbattery:
            alerts.append({'type': 'CRITICAL', 'msg': "Device reported critical low battery before sleep."})

        return alerts


class RawFrameUpload(models.Model):
    raw_file = models.FileField(upload_to='raw_frames/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    device_timestamp = models.DateTimeField(null=True, blank=True)
    device_id = models.CharField(max_length=50, blank=True, null=True)
    linked_diagnostic = models.ForeignKey(DeviceDiagnostic, on_delete=models.SET_NULL, null=True, blank=True, related_name='raw_frames')

    def __str__(self):
        return f"Raw frame from {self.device_id} at {self.uploaded_at.isoformat()}"


class DeviceImage(models.Model):
    image_file = models.ImageField(upload_to='images/%Y/%m/%d/', width_field='width', height_field='height')
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    device_id = models.CharField(max_length=50, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    device_timestamp = models.DateTimeField(null=True, blank=True)
    linked_diagnostic = models.ForeignKey(DeviceDiagnostic, on_delete=models.SET_NULL, null=True, blank=True, related_name='images')

    def __str__(self):
        return f"Image from {self.device_id} at {self.uploaded_at.isoformat()}"

    @property
    def megapixels(self):
        if self.width and self.height:
            return round((self.width * self.height) / 1_000_000, 1)
        return None



class DeviceCommand(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    device_id = models.CharField(max_length=50)
    command_type = models.CharField(max_length=50, default='CONFIG')
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Command {self.command_type} ({self.status}) for {self.device_id}"


class UploadLog(models.Model):
    UPLOAD_TYPES = [
        ('DIAGNOSTIC', 'Diagnostic Telemetry'),
        ('IMAGE', 'Device Image'),
        ('RAW_FRAME', 'Raw Frame'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    device_id = models.CharField(max_length=50, blank=True, null=True)
    upload_type = models.CharField(max_length=20, choices=UPLOAD_TYPES)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    status_code = models.IntegerField(null=True, blank=True)
    filename = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{self.upload_type} from {self.device_id} at {self.timestamp} - {status}"

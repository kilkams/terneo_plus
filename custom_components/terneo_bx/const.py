DOMAIN = "terneo_bx"
DEFAULT_SCAN_INTERVAL = 20
API_ENDPOINT = "/api.cgi"
CMD_TELEMETRY = 4
CMD_PARAMS = 1
CMD_SET_PARAM = 1
CMD_SCHEDULE = 2
PAR_TARGET_TEMP = 31
LOGGER = None

# Типы данных параметров (из документации Terneo)
# 1 = int8
# 2 = uint8
# 4 = uint16
# 6 = uint32
# 7 = bool

# Параметры с их типами [id, type]
PARAM_TYPES = {
    0: 6,    # startAwayTime (uint32)
    1: 6,    # endAwayTime (uint32)
    2: 2,    # mode (uint8) - режим работы
    3: 2,    # controlType (uint8) - режим контроля
    4: 1,    # manualAir (int8)
    5: 1,    # manualFloorTemperature (int8)
    6: 1,    # awayAirTemperature (int8)
    7: 1,    # awayFloorTemperature (int8)
    14: 2,   # minTempAdvancedMode (uint8)
    15: 2,   # maxTempAdvancedMode (uint8)
    17: 4,   # power (uint16)
    18: 2,   # sensorType (uint8)
    19: 2,   # histeresis (uint8)
    20: 1,   # airCorrection (int8)
    21: 1,   # floorCorrection (int8)
    23: 2,   # brightness (uint8)
    25: 2,   # propKoef (uint8)
    26: 1,   # upperLimit (int8)
    27: 1,   # lowerLimit (int8)
    28: 2,   # maxSchedulePeriod (uint8)
    29: 2,   # tempTemperature (uint8)
    31: 2,   # setTemperature (uint8) - целевая температура
    33: 1,   # upperAirLimit (int8)
    34: 1,   # lowerAirLimit (int8)
    52: 4,   # nightBrightStart (uint16)
    53: 4,   # nightBrightEnd (uint16)
    109: 7,  # offButtonLock (bool)
    114: 7,  # androidBlock (bool)
    115: 7,  # cloudBlock (bool)
    117: 7,  # NCContactControl (bool)
    118: 7,  # coolingControlWay (bool)
    120: 7,  # useNightBright (bool)
    121: 7,  # preControl (bool)
    122: 7,  # windowOpenControl (bool)
    124: 7,  # childrenLock (bool)
    125: 7,  # powerOff (bool) - выключение
}
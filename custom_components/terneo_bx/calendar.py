from __future__ import annotations
from datetime import datetime, timedelta
import homeassistant.util.dt as dt_util

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.calendar.const import CalendarEntityFeature

from .const import DOMAIN, LOGGER
from .coordinator import TerneoCoordinator


class TerneoCalendar(CalendarEntity):
    """Terneo weekly schedule calendar (tt)."""

    def __init__(self, coordinator: TerneoCoordinator, host: str):
        self.coordinator = coordinator
        self._host = host

        self._attr_name = f"Terneo {host} Schedule"
        self._attr_unique_id = f"terneo_{host}_schedule"
        self._attr_supported_features = (
            CalendarEntityFeature.CREATE_EVENT
            | CalendarEntityFeature.UPDATE_EVENT
            | CalendarEntityFeature.DELETE_EVENT
        )

    #
    # █████  INTERNAL: BUILD SCHEDULE FROM RAW PARAMS (par.25–29, 55)
    #

    def _read_schedule_from_params(self):
        """Convert raw_params from coordinator into internal tt{wd: [(minute,temp)]}."""
        params = (self.coordinator.data or {}).get("raw_params") or {}
        if not params:
            return {}

        tt = {str(i): [] for i in range(7)}

        try:
            # Weekdays
            count_wd = int(params.get("par.55", 0))
            wd_minutes = params.get("par.25", []) or []
            wd_temps = params.get("par.26", []) or []

            # Weekends
            count_we = int(params.get("par.27", 0))
            we_minutes = params.get("par.28", []) or []
            we_temps = params.get("par.29", []) or []

            # Build wd
            for i in range(min(count_wd, len(wd_minutes), len(wd_temps))):
                minute = int(wd_minutes[i])
                temp = int(wd_temps[i])
                for wd in range(5):
                    tt[str(wd)].append([minute, temp])

            # Build we
            for i in range(min(count_we, len(we_minutes), len(we_temps))):
                minute = int(we_minutes[i])
                temp = int(we_temps[i])
                for wd in (5, 6):
                    tt[str(wd)].append([minute, temp])

        except Exception as e:
            LOGGER.error(f"[calendar] error parsing schedule: {e}")

        # sort periods inside each weekday
        for wd in tt:
            tt[wd] = sorted(tt[wd], key=lambda p: p[0])

        return tt

    #
    # █████  INTERNAL: BUILD EVENTS
    #

    def _tt_to_events(self, start_date, end_date):
        """Convert internal tt to list[CalendarEvent]."""
        schedule = self._read_schedule_from_params()
        events = []

        current_day = dt_util.start_of_local_day(start_date)
        while current_day <= end_date:
            wd = str(current_day.weekday())
            periods = schedule.get(wd, [])

            for minute_of_day, temp_tenths in periods:
                event_start = current_day + timedelta(minutes=minute_of_day)

                if start_date <= event_start <= end_date:
                    summary = f"{temp_tenths/10:.1f}°C"

                    events.append(
                        CalendarEvent(
                            start=event_start,
                            end=event_start + timedelta(minutes=30),
                            summary=summary,
                            description=str(temp_tenths),
                            uid=f"{wd}-{minute_of_day}-{temp_tenths}"
                        )
                    )

            current_day += timedelta(days=1)

        return events

    #
    # █████  API: GET EVENTS
    #

    async def async_get_events(self, hass, start_date, end_date):
        return self._tt_to_events(start_date, end_date)

    #
    # █████  CREATE EVENT
    #

    async def async_create_event(self, **kwargs):
        start = kwargs.get("start_date_time") or kwargs.get("start_date")
        if start is None:
            LOGGER.error("[calendar] create_event missing start")
            return

        # extract temperature
        temp = None

        if (desc := kwargs.get("description")):
            try:
                temp = int(desc)
            except:
                pass

        if temp is None and (summary := kwargs.get("summary")):
            try:
                temp = int(float(summary.rstrip("°C")) * 10)
            except:
                pass

        if temp is None:
            LOGGER.error("[calendar] unable to parse temperature")
            return

        wd = str(start.weekday())
        minute = start.hour * 60 + start.minute

        tt = self._read_schedule_from_params()

        tt.setdefault(wd, [])
        tt[wd].append([minute, temp])

        await self._save_schedule_to_device(tt)
        await self.coordinator.async_request_refresh()

    #
    # █████  UPDATE EVENT
    #

    async def async_update_event(self, uid, **kwargs):
        await self.async_delete_event(uid)
        await self.async_create_event(**kwargs)

    #
    # █████  DELETE EVENT
    #

    async def async_delete_event(self, uid):
        try:
            wd, minute_str, temp_str = uid.split("-")
            minute = int(minute_str)
            temp = int(temp_str)
        except:
            LOGGER.error(f"[calendar] invalid uid {uid}")
            return

        tt = self._read_schedule_from_params()

        if wd in tt:
            tt[wd] = [
                p for p in tt[wd]
                if not (p[0] == minute and p[1] == temp)
            ]

        await self._save_schedule_to_device(tt)
        await self.coordinator.async_request_refresh()

    #
    # █████  SAVE TO DEVICE (new API!)
    #

    async def _save_schedule_to_device(self, tt):
        """
        Convert schedule dict to Terneo parameter format and push to device.
        """

        api = self.coordinator.api

        # build weekday/weekend arrays
        wd_minutes = []
        wd_temps = []
        we_minutes = []
        we_temps = []

        for wd in range(5):  # 0–4
            for minute, temp in tt.get(str(wd), []):
                wd_minutes.append(minute)
                wd_temps.append(temp)

        for wd in (5, 6):
            for minute, temp in tt.get(str(wd), []):
                we_minutes.append(minute)
                we_temps.append(temp)

        params = {
            55: len(wd_minutes),
            25: wd_minutes,
            26: wd_temps,
            27: len(we_minutes),
            28: we_minutes,
            29: we_temps,
        }

        LOGGER.debug(f"[calendar] saving schedule to device: {params}")

        # NEW API → device does not require SN in calendar writes,
        # just cmd=3 parameters (your current api implementation)
        await api.set_parameters(params)

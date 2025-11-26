from datetime import datetime, timedelta
import homeassistant.util.dt as dt_util
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.calendar.const import CalendarEntityFeature

from .const import DOMAIN, LOGGER


class TerneoCalendar(CalendarEntity):
    """Calendar entity mapping Terneo weekly schedule (tt) to HA calendar."""

    def __init__(self, coordinator, host):
        self.coordinator = coordinator
        self._host = host

        self._attr_name = f"Terneo {host} Schedule"
        self._attr_unique_id = f"terneo_{host}_schedule"
        self._attr_supported_features = (
            CalendarEntityFeature.CREATE_EVENT |
            CalendarEntityFeature.UPDATE_EVENT |
            CalendarEntityFeature.DELETE_EVENT
        )

    #
    # ████   INTERNAL CONVERSION
    #

    def _tt_to_events(self, start_date, end_date):
        """Convert internal tt schedule into HA CalendarEvent list."""
        events = []
        data = self.coordinator.data or {}
        schedule = (data.get("schedule") or {}).get("tt") or {}

        current = dt_util.start_of_local_day(start_date)

        while current <= end_date:
            wd = current.weekday()
            periods = schedule.get(str(wd), [])

            for minute_of_day, temp_tenths in periods:
                event_start = current + timedelta(minutes=minute_of_day)

                if start_date <= event_start <= end_date:
                    summary = f"Terneo: {temp_tenths / 10:.1f}°C"

                    events.append(
                        CalendarEvent(
                            start=event_start,
                            end=event_start + timedelta(minutes=30),
                            summary=summary,
                            description=str(temp_tenths),
                            uid=f"{wd}-{minute_of_day}-{temp_tenths}"
                        )
                    )

            current += timedelta(days=1)

        return events

    #
    # ████   HA CALENDAR API
    #

    async def async_get_events(self, hass, start_date, end_date):
        """Return list of events within the time range."""
        return self._tt_to_events(start_date, end_date)

    #
    # ████   CREATE EVENT
    #

    async def async_create_event(self, **kwargs):
        """Add a new scheduled temperature event."""
        start = kwargs.get("start_date_time") or kwargs.get("start_date")
        if start is None:
            LOGGER.error("[calendar] create_event: missing start_time")
            return

        # Extract temp from description or summary
        temp = None

        if (desc := kwargs.get("description")):
            try:
                temp = int(desc)
            except:
                pass

        if temp is None and (summary := kwargs.get("summary")):
            try:
                temp = int(float(summary.split(":")[1].strip().rstrip("°C")) * 10)
            except:
                pass

        if temp is None:
            LOGGER.error("[calendar] create_event: cannot extract temp")
            return

        minutes = start.hour * 60 + start.minute
        wd = start.weekday()

        # Copy existing schedule
        schedule_all = self.coordinator.data.get("schedule", {})
        tt = schedule_all.get("tt", {})
        tt = {k: list(v) for k, v in tt.items()}

        tt.setdefault(str(wd), [])
        tt[str(wd)].append([minutes, temp])

        await self._save_schedule_to_device(tt)
        await self.coordinator.async_request_refresh()

    #
    # ████   UPDATE EVENT
    #

    async def async_update_event(self, uid, **kwargs):
        await self.async_delete_event(uid)
        await self.async_create_event(**kwargs)

    #
    # ████   DELETE EVENT
    #

    async def async_delete_event(self, uid):
        try:
            wd_str, minute_str, temp_str = uid.split("-")
            wd = wd_str
            minute = int(minute_str)
            temp = int(temp_str)
        except:
            LOGGER.error(f"[calendar] delete_event: invalid uid {uid}")
            return

        schedule_all = self.coordinator.data.get("schedule", {})
        tt = schedule_all.get("tt", {})
        tt = {k: list(v) for k, v in tt.items()}

        if wd in tt:
            tt[wd] = [
                p for p in tt[wd]
                if not (p[0] == minute and p[1] == temp)
            ]

        await self._save_schedule_to_device(tt)
        await self.coordinator.async_request_refresh()

    #
    # ████   LOW LEVEL SAVE TO DEVICE
    #

    async def _save_schedule_to_device(self, tt):
        """
        Converts schedule dict to Terneo API parameters (par.*)
        and sends via cmd=3.
        """
        api = self.coordinator.api
        sn = self.coordinator.serial

        if sn is None:
            LOGGER.error("[calendar] no serial in coordinator")
            return

        #
        # Конвертация tt -> параметры Тернео
        #
        # Формат из документации:
        # par.55 — N записей
        # par.25 — массив минут по будням
        # par.26 — массив температур по будням
        #
        # par.27,28,29 — аналогично по выходным
        #
        # Мы уже договорились о формате расписания в интеграции.
        #

        weekdays = []
        weekdays_temp = []
        weekends = []
        weekends_temp = []

        for wd in range(7):
            key = str(wd)
            if key not in tt:
                continue

            for minutes, temp in tt[key]:
                if wd < 5:     # Пн–Пт
                    weekdays.append(minutes)
                    weekdays_temp.append(temp)
                else:          # Сб–Вс
                    weekends.append(minutes)
                    weekends_temp.append(temp)

        params = {
            55: len(weekdays),  # count weekdays
            25: weekdays,
            26: weekdays_temp,
            27: len(weekends),
            28: weekends,
            29: weekends_temp,
        }

        LOGGER.debug(f"[calendar] Saving schedule params {params}")

        await api.set_parameters(sn, params)

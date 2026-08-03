from homeassistant.const import Platform

DOMAIN = "classcharts"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_STUDENT_ID = "student_id"
CONF_STUDENT_NAME = "student_name"
CONF_MORNING_REFRESH_HOUR = "morning_refresh_hour"  # local time

DEFAULT_MORNING_REFRESH_HOUR = 5  # 05:00 Europe/London
PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]

# Update intervals
REWARDS_REFRESH_MINUTES = 30  # frequent enough to feel fresh, cheap calls
TIMETABLE_DAY_CACHE_SECONDS = 3600  # we also schedule a morning refresh
PUPIL_SUMMARY_REFRESH_MINUTES = 30  # single cheap call, same cadence as rewards
HOMEWORK_REFRESH_MINUTES = 30  # single cheap call, same cadence as rewards

CALENDAR_DAYS_AHEAD = 14


from enum import Enum


class SKeys(Enum):
    last_human_detected = "last_human_detected"
    last_cleanup = "last_cleanup"
    last_notify = "last_notify"
    last_silence = "last_silence"
    last_on = "last_on"
    offset_tg = "offset_tg"
    last_click = "last_click"
    clicks = "clicks"
    lights_locked = "lights_locked"
    adaptive_locked = "adaptive_locked"
    skip = "skip"
    random_colors = "random_colors"
    random_colors_passive = "random_colors_passive"
    random_colors_mode = "random_colors_mode"
    rc_lock = "rc_lock"
    button_checked = "button_checked"
    button_shadowed = "button_shadowed"
    last_hydro = "last_hydro"
    max_brightness = "max_brightness"
    alarm = "alarm"
    alarmed = "alarmed"
    sleep = "sleep"
    wc_lights = "wc_lights"
    wc_lock = "wc_lock"
    balcony_lock = "balcony_lock"
    exit_lock = "exit_lock"
    balcony_lights = "balcony_lights"
    previous_b_t = "previous_b_t"
    night = "night"
    water_notified = "water_notified"
    last_click_b_2 = "last_click_b_2"
    stop_alarm = "stop_alarm"
    last_quieting = "last_quieting"
    cleanups = "cleanups"
    evening = "evening"
    paint = "paint"
    modes_stats = "modes_stats"
    last_mode_on = "last_mode_on"
    humidifier_offed = "humidifier_offed"
    humidifier_ond = "humidifier_ond"
    humidifier_locked = "humidifier_locked"
    humidifier_locked_door = "humidifier_locked_door"
    last_off = "last_off"

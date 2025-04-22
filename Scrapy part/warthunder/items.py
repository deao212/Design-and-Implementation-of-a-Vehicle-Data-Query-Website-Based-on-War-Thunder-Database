# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class WarThunderItem(scrapy.Item):
    # Define item field
    AB = scrapy.Field()
    RB = scrapy.Field()
    SB = scrapy.Field()
    name = scrapy.Field()
    nation = scrapy.Field()
    rank = scrapy.Field()
    main_role = scrapy.Field()
    research = scrapy.Field()
    purchase = scrapy.Field()
    max_speed = scrapy.Field()
    at_height = scrapy.Field()
    rate_of_climb = scrapy.Field()
    turn_time = scrapy.Field()
    takeoff_run = scrapy.Field()
    max_altitude = scrapy.Field()
    crew = scrapy.Field()
    length = scrapy.Field()
    gross_weight = scrapy.Field()
    wingspan = scrapy.Field()
    engine = scrapy.Field()
    max_speed_limit_ias = scrapy.Field()
    flap_speed_limit_ias = scrapy.Field()
    mach_number_limit = scrapy.Field()
    armor_hull = scrapy.Field()
    armor_turret = scrapy.Field()
    visibility = scrapy.Field()
    optics_gunner_zoom = scrapy.Field()
    optics_gunner_device = scrapy.Field()
    optics_commander_zoom = scrapy.Field()
    optics_commander_device = scrapy.Field()
    optics_driver_zoom = scrapy.Field()
    optics_driver_device = scrapy.Field()
    max_speed_forward = scrapy.Field()
    max_speed_backward = scrapy.Field()
    power_to_weight_ratio = scrapy.Field()
    engine_power = scrapy.Field()
    weight = scrapy.Field()
    main_rotor_diameter = scrapy.Field()
    category = scrapy.Field()

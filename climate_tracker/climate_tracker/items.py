# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ClimateTrackerItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class RatingsOverview(scrapy.Item):
    country_name = scrapy.Field()
    overall_rating = scrapy.Field()
    policies_action_domestic = scrapy.Field()
    ndc_target_domestic = scrapy.Field()
    ndc_target_fair = scrapy.Field()
    climate_finance = scrapy.Field()
    net_zero_target_year = scrapy.Field()
    net_zero_target_rating = scrapy.Field()
    land_forestry_use = scrapy.Field()

class RatingsDescription(scrapy.Item):
    country_name = scrapy.Field()
    header = scrapy.Field()
    rating = scrapy.Field()
    content_text = scrapy.Field()

class CountryTargets(scrapy.Item):
    country_name = scrapy.Field()
    target = scrapy.Field()
    target_description = scrapy.Field()
    #tables = scrapy.Field()

class PolicyAction(scrapy.Item):
    country_name = scrapy.Field()
    policy = scrapy.Field()
    action_description = scrapy.Field()


class NetZeroTargets(scrapy.Item):
    country_name = scrapy.Field()
    target = scrapy.Field()
    target_description = scrapy.Field()

class Assumptions(scrapy.Item):
    country_name = scrapy.Field()
    assumption = scrapy.Field()
    assumption_description = scrapy.Field()
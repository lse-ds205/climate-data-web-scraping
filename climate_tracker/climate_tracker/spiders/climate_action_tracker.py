import scrapy
import logging
import pandas as pd
from climate_tracker.items import RatingsOverview, RatingsDescription, CountryTargets, PolicyAction, NetZeroTargets, Assumptions

logger = logging.getLogger(__name__)

class ClimateActionTrackerSpider(scrapy.Spider):
    name = "climate_action_tracker"
    allowed_domains = ["climateactiontracker.org"]
    start_urls = ["https://climateactiontracker.org/countries/"]

    def parse(self, response):
        logger.info('Discovering country URLs ...')
        country_links_xpath = '//a[starts-with(@href, "/countries")]/@href'
        country_links = response.xpath(country_links_xpath).getall()
        logger.info(f'Found {len(country_links)} country links.')

        # Here is where you can put the limit for how many links you want to be going through
        for href in country_links:  # Limiting to first 3 for testing
            country_url = response.urljoin(href)
            logger.debug(f"Found country URL: {country_url}")
            yield response.follow(
                country_url, 
                callback=self.parse_country
            )

    def parse_country(self, response):
        logger.info(f'Starting to parse country page: {response.url}')
        ratings_overview_item = RatingsOverview()
        try:
            ratings_overview_item['country_name'] = self.extract_with_default(response, 'h1::text')
            ratings_overview_item['overall_rating'] = self.extract_with_default(response, 'dt:contains("Overall rating") + dd::text')
            sub_ratings = response.css('div.ratings-matrix__second-row-cell dl > dt:nth-child(1) + dd > b::text').getall()
            ratings_overview_item['policies_action_domestic'] = sub_ratings[0] if len(sub_ratings) > 0 else "NA"
            ratings_overview_item['ndc_target_domestic'] = sub_ratings[1] if len(sub_ratings) > 1 else "NA"
            ratings_overview_item['ndc_target_fair'] = sub_ratings[2] if len(sub_ratings) > 2 else "NA"
            ratings_overview_item['climate_finance'] = sub_ratings[3] if len(sub_ratings) > 3 else "NA"
            ratings_overview_item['net_zero_target_year'] = self.extract_with_default(response, 'div.ratings-matrix__third-row-cell dl.ratings-matrix__net_zero_target dd:nth-child(2) b::text')
            ratings_overview_item['net_zero_target_rating'] = self.extract_with_default(response, 'div.ratings-matrix__third-row-cell dl.ratings-matrix__net_zero_target dd:nth-child(3) b::text', strip=True)
            ratings_overview_item['land_forestry_use'] = self.extract_with_default(response, 'div.ratings-matrix__third-row-cell dl.ratings-matrix__land_use_forestry dd b::text', strip=True)
        except Exception as e:
            logger.error(f'Error parsing country page: {response.url} - {e}')
        yield ratings_overview_item

        ratings_description_item = RatingsDescription()
        try:
            containers_with_content_block = response.xpath('//div[contains(@class, "container")][.//div[contains(@class, "content-block")]]')
            for s in containers_with_content_block:
                header = s.css('div.ratings-section-header dt::text').get()
                if header is None:
                    p_text = s.css('div.ratings-section-header p::text').get()
                    if p_text:
                        br_text = s.css('div.ratings-section-header p br + ::text').get()
                        if br_text:
                            header = p_text + " " + br_text
                        else:
                            header = p_text
                rating = None
                if header is None:
                    header = s.css('h3::text').get().strip()
                    rating = 'no rating'
                else:
                    rating = s.css('div.ratings-section-header dd::text').get()
                content_text = ' '.join(t.strip() for t in s.css('div.content-block ::text').getall() if t.strip())
                
                ratings_description_item['country_name'] = self.extract_with_default(response, 'h1::text')
                ratings_description_item['header'] = header
                ratings_description_item['rating'] = rating
                ratings_description_item['content_text'] = content_text
                yield ratings_description_item

        except Exception as e:
            logger.error(f'Error parsing country texts portion: {response.url} - {e}')

        logger.info(f'Finished parsing country page: {response.url}')

        # Follow the target page link
        target_page_url = response.css('a[href*="/target"]::attr(href)').get()
        if target_page_url:
            target_page_url = response.urljoin(target_page_url)
            yield response.follow(target_page_url, callback=self.parse_country_target)

        # Follow the policies action page link
        policies_action_url = response.css('a[href*="/policies-action"]::attr(href)').get()
        if policies_action_url:
            policies_action_url = response.urljoin(policies_action_url)
            yield response.follow(policies_action_url, callback=self.parse_policies_action)

        # Follow the net-zero targets page link
        net_zero_targets_url = response.css('a[href*="/net-zero-targets"]::attr(href)').get()
        if net_zero_targets_url:
            net_zero_targets_url = response.urljoin(net_zero_targets_url)
            yield response.follow(net_zero_targets_url, callback=self.parse_net_zero_targets)

        assumptions_url = response.css('a[href*="/assumptions"]::attr(href)').get()
        if assumptions_url:
            assumptions_url = response.urljoin(assumptions_url)
            yield response.follow(assumptions_url, callback=self.parse_assumptions)

        logger.info(f'Finished parsing country page: {response.url}')


        logger.info(f'Finished parsing country page: {response.url}')

    #Country Target Page Core
    def parse_country_target(self, response):
        logger.info(f'Starting to parse country target page: {response.url}')

        country_targets_item = CountryTargets()

        try:
            containers_with_content_block = response.xpath('//div[contains(@class, "container")][.//div[contains(@class, "content-block")]]')
            for s in containers_with_content_block:
                target = s.css('h3::text').get().strip()
                target_description = ' '.join(t.strip() for t in s.css('div.content-block ::text').getall() if t.strip())
                logger.info(f'Extracted target content: {target} - {target_description}')

                country_targets_item['country_name'] = self.extract_with_default(response, 'h1::text')
                country_targets_item['target'] = target
                country_targets_item['target_description'] = target_description

                yield country_targets_item

        except Exception as e:
            logger.error(f'Error parsing country target page: {response.url} - {e}')

        logger.info(f'Finished parsing country target page: {response.url}')


    #Policies and Action Page Core
    def parse_policies_action(self, response):
        logger.info(f'Starting to parse policies action page: {response.url}')

        policy_action_item = PolicyAction()

        try:
            containers_with_content_block = response.xpath('//div[contains(@class, "container")][.//div[contains(@class, "content-block")]]')
            for s in containers_with_content_block:
                policy = s.css('h3::text').get()
                if policy:
                    policy = policy.strip()
                else:
                    policy = s.css('p::text').get().strip()
                action_description = ' '.join(t.strip() for t in s.css('div.content-block ::text').getall() if t.strip())
                logger.info(f'Extracted policy and action content: {policy} - {action_description}')

                policy_action_item['country_name'] = self.extract_with_default(response, 'h1::text')
                policy_action_item['policy'] = policy
                policy_action_item['action_description'] = action_description
                yield policy_action_item

        except Exception as e:
            logger.error(f'Error parsing policies action page: {response.url} - {e}')

        logger.info(f'Finished parsing policies action page: {response.url}')

    #Net Zero Targets Page Core
    def parse_net_zero_targets(self, response):
        logger.info(f'Starting to parse net-zero targets page: {response.url}')

        net_zero_targets_item = NetZeroTargets()

        try:
            containers_with_content_block = response.xpath('//div[contains(@class, "container")][.//div[contains(@class, "content-block")]]')
            for s in containers_with_content_block:
                target = s.css('h3::text').get().strip()
                target_description = ' '.join(t.strip() for t in s.css('div.content-block ::text').getall() if t.strip())
                logger.info(f'Extracted net-zero target content: {target} - {target_description}')

                net_zero_targets_item['country_name'] = self.extract_with_default(response, 'h1::text')
                net_zero_targets_item['target'] = target
                net_zero_targets_item['target_description'] = target_description

                yield net_zero_targets_item

        except Exception as e:
            logger.error(f'Error parsing net-zero targets page: {response.url} - {e}')

        logger.info(f'Finished parsing net-zero targets page: {response.url}')

    #Assumptions Core
    def parse_assumptions(self, response):
        logger.info(f'Starting to parse assumptions page: {response.url}')

        assumptions_item = Assumptions()

        try:
            containers_with_content_block = response.xpath('//div[contains(@class, "container")][.//div[contains(@class, "content-block")]]')
            for s in containers_with_content_block:
                assumption = s.css('h3::text').get().strip()
                assumption_description = ' '.join(t.strip() for t in s.css('div.content-block ::text').getall() if t.strip())
                logger.info(f'Extracted assumption content: {assumption} - {assumption_description}')

                assumptions_item['country_name'] = self.extract_with_default(response, 'h1::text')
                assumptions_item['assumption'] = assumption
                assumptions_item['assumption_description'] = assumption_description

                yield assumptions_item

        except Exception as e:
            logger.error(f'Error parsing assumptions page: {response.url} - {e}')

    def extract_with_default(self, response, css_selector, default="NA", strip=False):
        value = response.css(css_selector).get()
        if value:
            return value.strip() if strip else value
        else:
            logger.warning(f'Missing value for selector: {css_selector} on page: {response.url}')
            return default





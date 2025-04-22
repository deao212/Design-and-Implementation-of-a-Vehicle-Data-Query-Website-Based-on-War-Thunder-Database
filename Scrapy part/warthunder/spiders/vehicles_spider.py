import traceback
from selenium.common import TimeoutException, NoSuchElementException
from warthunder.items import WarThunderItem
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options as EdgeOptions
import scrapy
import mysql.connector
import re

class VehiclesSpider(scrapy.Spider):
    name = 'vehicles'
    allowed_domains = ['wiki.warthunder.com']
    start_urls = [
        'https://wiki.warthunder.com/aviation',
        'https://wiki.warthunder.com/ground',
        'https://wiki.warthunder.com/helicopters'
    ]

    def __init__(self, *args, **kwargs):
        super(VehiclesSpider, self).__init__(*args, **kwargs)
        edge_options = EdgeOptions()
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheet": 2
        }
        edge_options.add_experimental_option("prefs", prefs)
        #  Set the Edge WebDriver path
        service = Service(executable_path='C:/Program Files/edgedriver_win64/msedgedriver.exe')
        self.driver = webdriver.Edge(service=service, options=edge_options)  # Start WebDriver with Service

        # Create a database connection
        self.db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="123456",
            database="warthunder_vehicle_data"
        )
        self.cursor = self.db.cursor()

    def parse(self, response):
        category = response.url.split('/')[-1]
        self.logger.info(f" Start processing sort: {category}")

        try:
            self.driver.get(response.url)

            # Cookie popup processing
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: "cookie" in d.page_source.lower() or
                              "consent" in d.page_source.lower()
                )
                accept_btn = self.driver.find_element(
                    By.XPATH,
                    '//button[contains(translate(., "ACCEPTALL", "acceptall"), "accept all")]'
                )
                self.driver.execute_script("arguments[0].click();", accept_btn)
                self.logger.info(" Cookie popup accepted ")
                # Wait for content to load
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.unit-tree'))
                )
            except (NoSuchElementException, TimeoutException):
                self.logger.debug(" No Cookie popup ")

            # Get all country containers directly
            country_containers = WebDriverWait(self.driver, 20).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'div.unit-tree[data-tree-id]')
                )
            )
            self.logger.info(f" find {len(country_containers)} country containers")

            # Traverse each country container
            for container in country_containers:
                try:
                    # Get country code
                    country_code = container.get_attribute('data-tree-id').upper()
                    self.logger.info(f" Country in process: {country_code}")

                    # Gets the vehicle link in the container
                    vehicle_links = container.find_elements(
                        By.CSS_SELECTOR, 'a.wt-tree_item-link'
                    )
                    self.logger.info(f" find {len(vehicle_links)} vehicle link")

                    # Handle each vehicle link
                    for link in vehicle_links:  # Limit the number when testing
                        vehicle_url = link.get_attribute('href')
                        if vehicle_url:
                            self.logger.debug(f" Extract to link: {vehicle_url}")
                            yield scrapy.Request(
                                vehicle_url,
                                callback=self.parse_vehicle_details,
                                meta={
                                    'country': country_code,
                                    'category': category,
                                    'referer': response.url
                                }
                            )

                except Exception as e:
                    self.logger.error(f" handel country {country_code} failed: {str(e)}")
                    self.driver.save_screenshot(f"error_{country_code}.png")

        except Exception as ex:
            self.logger.error(f"Global error : {str(ex)}")
            traceback.print_exc()
            self.driver.save_screenshot("global_error.png")

    def parse_vehicle_details(self, response):

        category = response.meta['category']  # Get vehicle categories (aviation, ground, helicopters)
        self.logger.info(f"Parsing vehicle details in category {category}: {response.url}")
        # use Selenium load page
        self.driver.get(response.url)
        item = WarThunderItem()

        # wait for the core container to load
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.game-unit_name"))
            )
        except TimeoutException:
            self.logger.error(f"core container not loaded: {response.url}")
            self.driver.save_screenshot("core_container_timeout.png")
            return item

        def clean_text(text, is_numeric=False):
            if not text:
                return 'Unknown' if not is_numeric else '0'

            # Retain numbers, decimal points and units
            if is_numeric:
                cleaned = re.sub(r'[^\d.]', '', text)
                return cleaned if cleaned else '0'

            # Remove the control characters
            return re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text).strip()

        def safe_find_text(xpath, is_numeric=False, default='Unknown'):
            try:
                element = self.driver.find_element(By.XPATH, xpath)
                return clean_text(element.text, is_numeric=is_numeric)
            except NoSuchElementException:
                return default

        item['category'] = category
        # Extract basic vehicle information and add default values to avoid errors
        item['name'] = clean_text(
            self.driver.find_element(By.XPATH, '//div[contains(@class, "game-unit_name")]')
            .text.strip() or 'Unknown'
        )

        item['nation'] = clean_text(
            self.driver.find_element(
                By.XPATH,
                '//div[@class="game-unit_card-info_title" and text()="Game nation"]/../div[@class="game-unit_card-info_value"]/div[@class="text-truncate"]')
            .text.strip() or 'Unknown'
        )

        item['rank'] = clean_text(
            self.driver.find_element(By.XPATH,
                 '//div[contains(@class, "game-unit_card-info_item") and contains(@class, "game-unit_rank")]//div[contains(@class, "game-unit_card-info_value")]')
            .text.strip() or 'Unknown'
        )

        item['main_role'] = clean_text(
            self.driver.find_element(
                By.XPATH,
                '//div[contains(@class, "game-unit_card-info_title") and contains(text(), "Main role")]/../div[contains(@class, "game-unit_card-info_value")]//div[contains(@class, "text-truncate")]'
            ).text.strip() or 'Unknown'
        )

        # AB
        item['AB'] = clean_text(
            self.driver.find_element(
                By.XPATH,
                '//div[contains(@class, "game-unit_br-item")]//*[contains(@class, "mode") and contains(text(), "AB")]/following-sibling::*[contains(@class, "value")][1]'
            ).text.strip() if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_br-item")]//*[contains(@class, "mode") and contains(text(), "AB")]/following-sibling::*[contains(@class, "value")][1]'
            ) else 'Unknown'
        )

        # RB
        item['RB'] = clean_text(
            self.driver.find_element(
                By.XPATH,
                '//div[contains(@class, "game-unit_br-item")]//*[contains(@class, "mode") and contains(text(), "RB")]/following-sibling::*[contains(@class, "value")][1]'
            ).text.strip() if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_br-item")]//*[contains(@class, "mode") and contains(text(), "RB")]/following-sibling::*[contains(@class, "value")][1]'
            ) else 'Unknown'
        )

        # SB
        item['SB'] = clean_text(
            self.driver.find_element(
                By.XPATH,
                '//div[contains(@class, "game-unit_br-item")]//*[contains(@class, "mode") and contains(text(), "SB")]/following-sibling::*[contains(@class, "value")][1]'
            ).text.strip() if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_br-item")]//*[contains(@class, "mode") and contains(text(), "SB")]/following-sibling::*[contains(@class, "value")][1]'
            ) else 'Unknown'
        )

        # Research
        item['research'] = clean_text(
            self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_card-info_title") and normalize-space(text())="Research"]/preceding-sibling::div[contains(@class, "game-unit_card-info_value")]//div'
            )[0].text.strip() if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_card-info_title") and normalize-space(text())="Research"]/preceding-sibling::div[contains(@class, "game-unit_card-info_value")]//div'
            ) else '0'
        )

        # Purchase
        item['purchase'] = clean_text(
            self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_card-info_title") and normalize-space(text())="Purchase"]/preceding-sibling::div[contains(@class, "game-unit_card-info_value")]//div'
            )[0].text.strip() if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_card-info_title") and normalize-space(text())="Purchase"]/preceding-sibling::div[contains(@class, "game-unit_card-info_value")]//div'
            ) else '0'
        )

        # Extract different data based on the page type
        if category == 'aviation':
            # Extract detailed data for aviation (aircraft) vehicles

            # Max speed
            item['max_speed'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
            ) else 'Unknown'

            # at_height
            item['at_height'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[1]/span[1]'
                )[0].text.strip().replace(',', '')
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[1]/span[1]'
            ) else 'Unknown'

            # Rate of Climb
            item['rate_of_climb'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Rate of Climb")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Rate of Climb")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
            ) else 'Unknown'

            # Turn time
            item['turn_time'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Turn time")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Turn time")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
            ) else 'Unknown'

            # Max altitude
            item['max_altitude'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Max altitude")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max altitude")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

            # Takeoff Run
            item['takeoff_run'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Takeoff Run")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Takeoff Run")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

            # Crew
            item['crew'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Crew")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Crew")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

            # Length
            item['length'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Length")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Length")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

            # Gross weight
            item['gross_weight'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Gross weight")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Gross weight")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

            # Wingspan
            item['wingspan'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Wingspan")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Wingspan")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

            # Engine
            item['engine'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Engine")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Engine")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

            # Max Speed Limit (IAS)
            item['max_speed_limit_ias'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Max Speed Limit (IAS)")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip().split(' ')[0]
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max Speed Limit (IAS)")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

            # Flap Speed Limit (IAS)
            item['flap_speed_limit_ias'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Flap Speed Limit (IAS)")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip().split(' ')[0]
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Flap Speed Limit (IAS)")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

            # Mach Number Limit
            item['mach_number_limit'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Mach Number Limit")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip().split(' ')[0]
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Mach Number Limit")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'

        elif category == 'ground':

            # Armour - Hull
            item['armor_hull'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Hull")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Hull")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
            ) else 'Unknown'

            # Armour - Turret
            item['armor_turret'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Turret")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Turret")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
            ) else 'Unknown'

            # Visibility
            item['visibility'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line")]/span[contains(text(), "Visibility")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line")]/span[contains(text(), "Visibility")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
            ) else 'Unknown'

            # Crew
            item['crew'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line")]/span[contains(text(), "Crew")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line")]/span[contains(text(), "Crew")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
            ) else 'Unknown'

            # Max speed forward
            item['max_speed_forward'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Forward")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span[contains(@class, "show-char-rb")]'
                )[0].text.strip().split()[0]
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Forward")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span[contains(@class, "show-char-rb")]'
            ) else 'Unknown'

            # Max speed backward
            item['max_speed_backward'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Backward")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span'
                )[0].text.strip().split()[0]
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Backward")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span'
            ) else 'Unknown'

            # Power-to-weight ratio
            item['power_to_weight_ratio'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line")]/span[contains(text(), "Power-to-weight ratio")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span[contains(@class, "show-char-rb-mod-ref")]'
                )[0].text.strip().replace(',', '')
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line")]/span[contains(text(), "Power-to-weight ratio")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span[contains(@class, "show-char-rb-mod-ref")]'
            ) else 'Unknown'

            # Engine power
            item['engine_power'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Engine power")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span[contains(@class, "show-char-rb-mod-ref")]'
                )[0].text.strip().replace(',', '')
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Engine power")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span[contains(@class, "show-char-rb-mod-ref")]'
            ) else 'Unknown'

            # Weight
            item['weight'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Weight")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
                )[0].text.strip().replace(',', '')
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Weight")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
            ) else 'Unknown'


            def get_optics_field(path_suffix: str, index: int, processor=None):
                elements = self.driver.find_elements(
                    By.XPATH,
                    f'//div[contains(@class, "form-text mb-1") and contains(text(), "{path_suffix}")]/following-sibling::div[contains(@class, "gunit_specs-table_row")]/div[{index}]'
                )
                if not elements:
                    return 'Unknown'
                text = elements[0].text.strip()
                return clean_text(processor(text)) if processor else clean_text(text)

            # Optics zoom
            item['optics_gunner_zoom'] = get_optics_field("Optics zoom", 1)
            item['optics_commander_zoom'] = get_optics_field("Optics zoom", 2)
            item['optics_driver_zoom'] = get_optics_field("Optics zoom", 3)

            # Optical device
            item['optics_gunner_device'] = get_optics_field("Optical device", 1, lambda x: x.split('\n')[0])
            item['optics_commander_device'] = get_optics_field("Optical device", 2, lambda x: x.split('\n')[0])
            item['optics_driver_device'] = get_optics_field("Optical device", 3, lambda x: x.split('\n')[0])



        elif category == 'helicopters':

            # Extract detailed data from helicopter vehicles

            # Max speed
            item['max_speed'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
            ) else 'Unknown'

            # at_height
            item['at_height'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[1]/span[1]'
                )[0].text.strip().replace(',', '')
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[1]/span[1]'
            ) else 'Unknown'

            # Rate of Climb
            item['rate_of_climb'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Rate of Climb")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Rate of Climb")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]'
            ) else 'Unknown'

            # Max altitude
            item['max_altitude'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-line") and contains(., "Max altitude")]/span[@class="game-unit_chars-value"]'
                )[0].text.strip()
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max altitude")]/span[@class="game-unit_chars-value"]'
            ) else 'Unknown'


            def get_block_field(field_name: str, default='Unknown') -> str:
                elements = self.driver.find_elements(
                    By.XPATH,
                    f'//div[contains(@class, "game-unit_chars-block")]/div/span[contains(text(), "{field_name}")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
                )
                return clean_text(elements[0].text.strip()) if elements else default

            # Crew
            item['crew'] = get_block_field("Crew")

            # Gross weight
            item['gross_weight'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-block")]/div/span[contains(text(), "Gross weight")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
                )[0].text.strip().replace(',', '')
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-block")]/div/span[contains(text(), "Gross weight")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
            ) else 'Unknown'

            # Engine
            item['engine'] = get_block_field("Engine")

            # Main rotor diameter
            item['main_rotor_diameter'] = clean_text(
                self.driver.find_elements(
                    By.XPATH,
                    '//div[contains(@class, "game-unit_chars-block")]/div/span[contains(text(), "Main rotor diameter")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
                )[0].text.strip().split()[0]
            ) if self.driver.find_elements(
                By.XPATH,
                '//div[contains(@class, "game-unit_chars-block")]/div/span[contains(text(), "Main rotor diameter")]/following-sibling::span[contains(@class, "game-unit_chars-value")]'
            ) else 'Unknown'

        pass
        # save to db
        self.save_to_db(item, category)

        return item

    def save_to_db(self, item, category):
        """
        Inserts the scraped data for each vehicle into the MySQL database.
        """
        table_name = category.lower()

        # Clean up field values, remove units (e.g. "1.5T" to 1.5)
        def clean_number(value):
            if value is None:
                return None

            if isinstance(value, str):
                # Remove Spaces and invisible characters before and after
                cleaned = value.strip()
                # Remove unit symbols and redundant characters (e.g. km/h, %, etc.)
                cleaned = re.sub(r'[^\d.]+', '', cleaned)
                if not cleaned:  # handle empty string
                    return None

                # change data type
                try:
                    # Convert to floating point and keep 1 decimal place
                    num = round(float(cleaned), 1)
                    # Validate numeric ranges (example ranges, adjusted based on actual field definitions)
                    if not (-999.9 <= num <= 999.9):
                        print(f"value is out of range: {num}，set to empty")
                        return None
                    return num
                except (ValueError, TypeError):
                    return None

                # Process existing numeric types
            elif isinstance(value, (int, float)):
                return round(float(value), 1)

                return None

        # Clean the crew field and keep the numbers
        def clean_crew(value):
            if isinstance(value, str):
                return ''.join(c for c in value if c.isdigit())
            return value

        # Dynamically build the fields and values of SQL queries
        def build_values(item, category):
            if category == 'aviation':
                values = (
                    clean_number(item.get('AB', 'Unknown')), clean_number(item.get('RB', 'Unknown')),
                    clean_number(item.get('SB', 'Unknown')),
                    item.get('at_height', None), clean_crew(item.get('crew', 'Unknown')),
                    item.get('engine', None), clean_number(item.get('flap_speed_limit_ias', None)),
                    clean_number(item.get('gross_weight', None)),
                    clean_number(item.get('length', None)), clean_number(item.get('mach_number_limit', None)),
                    item.get('main_role', 'Unknown'),
                    clean_number(item.get('max_altitude', None)), clean_number(item.get('max_speed', None)),
                    clean_number(item.get('max_speed_limit_ias', None)),
                    item.get('name', 'Unknown'), item.get('nation', 'Unknown'), item.get('purchase', '0'),
                    item.get('rank', 'Unknown'), clean_number(item.get('rate_of_climb', None)),
                    item.get('research', '0'),
                    clean_number(item.get('takeoff_run', None)), item.get('turn_time', None), clean_number(item.get('wingspan', None))
                )
            elif category == 'ground':
                values = (
                    clean_number(item.get('AB', 'Unknown')), clean_number(item.get('RB', 'Unknown')),
                    clean_number(item.get('SB', 'Unknown')),
                    item.get('armor_hull', None), item.get('armor_turret', None),
                    clean_crew(item.get('crew', 'Unknown')), clean_number(item.get('engine_power', None)),
                    item.get('main_role', 'Unknown'),
                    clean_number(item.get('max_speed_backward', None)),
                    clean_number(item.get('max_speed_forward', None)),
                    item.get('name', 'Unknown'),
                    item.get('nation', 'Unknown'), item.get('optics_commander_device', None),
                    item.get('optics_commander_zoom', None), item.get('optics_driver_device', None),
                    item.get('optics_driver_zoom', None), item.get('optics_gunner_device', None),
                    item.get('optics_gunner_zoom', None), clean_number(item.get('power_to_weight_ratio', None)),
                    item.get('purchase', '0'), item.get('rank', 'Unknown'), item.get('research', '0'),
                    clean_number(item.get('visibility', None)), clean_number(item.get('weight', None))
                )
            elif category == 'helicopters':
                values = (
                    clean_number(item.get('AB', 'Unknown')), clean_number(item.get('RB', 'Unknown')),
                    clean_number(item.get('SB', 'Unknown')),
                    item.get('at_height', None), clean_crew(item.get('crew', 'Unknown')),
                    item.get('engine', None), clean_number(item.get('gross_weight', None)),
                    item.get('main_role', 'Unknown'),
                    clean_number(item.get('main_rotor_diameter', None)), clean_number(item.get('max_altitude', None)),
                    clean_number(item.get('max_speed', None)),
                    item.get('name', 'Unknown'), item.get('nation', 'Unknown'), item.get('purchase', '0'),
                    item.get('rank', 'Unknown'), clean_number(item.get('rate_of_climb', None)),
                    item.get('research', '0')
                )

            return values

        # Get data adapted to specific vehicle classes
        values = build_values(item, category)

        # Build SQL queries dynamically based on vehicle type
        if category == 'aviation':
            fields = [
                "AB", "RB", "SB", "at_height", "crew", "engine", "flap_speed_limit_ias",
                "gross_weight", "length", "mach_number_limit", "main_role", "max_altitude", "max_speed",
                "max_speed_limit_ias", "name", "nation", "purchase", "`rank`", "`rate_of_climb`", "`research`",
                "`takeoff_run`", "`turn_time`", "`wingspan`"
            ]
        elif category == 'ground':
            fields = [
                "AB", "RB", "SB", "armor_hull", "armor_turret", "crew", "engine_power",
                "main_role", "max_speed_backward", "max_speed_forward", "name", "nation",
                "optics_commander_device", "optics_commander_zoom", "optics_driver_device", "optics_driver_zoom",
                "optics_gunner_device", "optics_gunner_zoom", "power_to_weight_ratio", "purchase", "`rank`",
                "`research`", "`visibility`", "`weight`"
            ]
        elif category == 'helicopters':
            fields = [
                "AB", "RB", "SB", "at_height", "crew", "engine", "gross_weight", "main_role",
                "main_rotor_diameter", "max_altitude", "max_speed", "name", "nation", "purchase", "`rank`",
                "`rate_of_climb`", "`research`"
            ]

        # Build SQL queries dynamically
        sql = f"""
            INSERT INTO {table_name} ({', '.join(fields)})
            VALUES ({', '.join(['%s'] * len(fields))})
        """

        # Debug: Print out SQL and values
        # print("Executing SQL:", sql)
        # print("With values:", values)
        # print("SQL Query:", sql)
        # print("Values:", values)
        # print(f"Number of placeholders: {len(fields)}")
        # print(f"Number of values: {len(values)}")

        # Perform SQL insert
        try:
            self.cursor.execute(sql, values)
            self.db.commit()
            self.logger.info(f"Successfully inserted vehicle data for {item['name']} into {table_name} table.")
        except mysql.connector.Error as err:
            self.db.rollback()
            self.logger.error(f"Error inserting vehicle data for {item['name']}: {err}")

    def close(self, reason):
        # Close the browser and database connection
        self.driver.quit()
        self.cursor.close()
        self.db.close()

import traceback
from selenium.common import TimeoutException, NoSuchElementException, StaleElementReferenceException
from warthunder.items import WarThunderItem
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
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

        #  Set the Edge WebDriver path
        service = Service(executable_path='C:/Program Files/edgedriver_win64/msedgedriver.exe')
        self.driver = webdriver.Edge(service=service)  # Start WebDriver with Service

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

        item = WarThunderItem()

        def clean_text(text):
            # Use regular expressions to remove all non-print characters (including control characters)
            if text:
                return re.sub(r'[^\x20-\x7E]+', '', text)  # Keep only printable characters
            return text
        item['category'] = category
        # Extract basic vehicle information and add default values to avoid errors
        item['name'] = clean_text(response.css('div.game-unit_name::text').get().strip() if response.css(
            'div.game-unit_name::text').get() else 'Unknown')

        item['nation'] = clean_text(response.css(
            'div.game-unit_card-info_item:contains("Game nation") div.game-unit_card-info_value div.text-truncate::text').get() or 'Unknown')

        item['rank'] = clean_text(response.css(
            'div.game-unit_card-info_item.game-unit_rank div.game-unit_card-info_value::text').get().strip() if response.css(
            'div.game-unit_card-info_item.game-unit_rank div.game-unit_card-info_value::text').get() else 'Unknown')

        item['main_role'] = clean_text(response.xpath(
            '//div[contains(@class, "game-unit_card-info_title") and contains(text(), "Main role")]/preceding-sibling::div[contains(@class, "game-unit_card-info_value")]//div[contains(@class, "text-truncate")]/text()'
        ).get() or 'Unknown')

        item['AB'] = clean_text(response.css(
            'div.game-unit_br-item .mode:contains("AB") + .value::text').get().strip() if response.css(
            'div.game-unit_br-item .mode:contains("AB") + .value::text').get() else 'Unknown')

        item['RB'] = clean_text(response.css(
            'div.game-unit_br-item .mode:contains("RB") + .value::text').get().strip() if response.css(
            'div.game-unit_br-item .mode:contains("RB") + .value::text').get() else 'Unknown')

        item['SB'] = clean_text(response.css(
            'div.game-unit_br-item .mode:contains("SB") + .value::text').get().strip() if response.css(
            'div.game-unit_br-item .mode:contains("SB") + .value::text').get() else 'Unknown')

        # Gets the number in the previous sibling element of Research
        item['research'] = clean_text(response.xpath(
            '//div[contains(@class, "game-unit_card-info_title") and text()="Research"]/preceding-sibling::div[contains(@class, "game-unit_card-info_value")]//div/text()'
        ).get().strip() if response.xpath(
            '//div[contains(@class, "game-unit_card-info_title") and text()="Research"]/preceding-sibling::div[contains(@class, "game-unit_card-info_value")]//div/text()'
        ).get() else '0')

        # Read the Purchase field and make sure to get the adjacent value
        item['purchase'] = clean_text(response.xpath(
            '//div[contains(@class, "game-unit_card-info_title") and text()="Purchase"]/preceding-sibling::div[contains(@class, "game-unit_card-info_value")]//div/text()'
        ).get().strip() if response.xpath(
            '//div[contains(@class, "game-unit_card-info_title") and text()="Purchase"]/preceding-sibling::div[contains(@class, "game-unit_card-info_value")]//div/text()'
        ).get() else '0')

        # Extract different data based on the page type
        if category == 'aviation':
            # Extract detailed data for aviation (aircraft) vehicles
            # max_speed
            item['max_speed'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get() else 'Unknown')

            # at_height
            item['at_height'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[1]//span[1]/text()'
            ).get().strip().replace(',', '') if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[1]//span[1]/text()'
            ).get() else 'Unknown')

            # Rate of Climb
            item['rate_of_climb'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Rate of Climb")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Rate of Climb")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get() else 'Unknown')

            # Turn time
            item['turn_time'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Turn time")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Turn time")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get() else 'Unknown')

            # Max altitude
            item['max_altitude'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max altitude")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max altitude")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Takeoff Run
            item['takeoff_run'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Takeoff Run")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Takeoff Run")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Crew
            item['crew'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Crew")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Crew")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Length
            item['length'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Length")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Length")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Gross weight
            item['gross_weight'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Gross weight")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Gross weight")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Wingspan
            item['wingspan'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Wingspan")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Wingspan")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Engine
            item['engine'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Engine")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Engine")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Max Speed Limit (IAS)
            item['max_speed_limit_ias'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max Speed Limit (IAS)")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip().split(' ')[0] if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max Speed Limit (IAS)")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Flap Speed Limit (IAS)
            item['flap_speed_limit_ias'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Flap Speed Limit (IAS)")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip().split(' ')[0] if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Flap Speed Limit (IAS)")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Mach Number Limit
            item['mach_number_limit'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Mach Number Limit")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip().split(' ')[0] if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Mach Number Limit")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

        elif category == 'ground':

            armour_hull = None

            armour_turret = None

            visibility = None

            crew = None

            max_speed_forward = None

            max_speed_backward = None

            power_to_weight_ratio = None

            engine_power = None

            weight = None

            optics_gunner_zoom = None

            optics_commander_zoom = None

            optics_driver_zoom = None

            optics_gunner_device = None

            optics_commander_device = None

            optics_driver_device = None

            # Hull

            hull_data = response.xpath(

                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Hull")]/following-sibling::span[contains(@class, "game-unit_chars-value")]/text()').get()

            if hull_data:
                armour_hull = clean_text(hull_data.strip())

            # Turret

            turret_data = response.xpath(

                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Turret")]/following-sibling::span[contains(@class, "game-unit_chars-value")]/text()').get()

            if turret_data:
                armour_turret = clean_text(turret_data.strip())

            # Visibility

            visibility_data = response.xpath(

                '//div[contains(@class, "game-unit_chars-line")]/span[contains(text(), "Visibility")]/following-sibling::span[contains(@class, "game-unit_chars-value")]/text()').get()

            if visibility_data:
                visibility = clean_text(visibility_data.strip())

            # Crew

            crew_data = response.xpath(

                '//div[contains(@class, "game-unit_chars-line")]/span[contains(text(), "Crew")]/following-sibling::span[contains(@class, "game-unit_chars-value")]/text()').get()

            if crew_data:
                crew = clean_text(crew_data.strip())

            # Max speed forward

            max_speed_forward_data = response.xpath(

                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Forward")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span[contains(@class, "show-char-rb")]/text()').get()

            if max_speed_forward_data:
                max_speed_forward = clean_text(max_speed_forward_data.strip())

            # Max speed backward

            max_speed_backward_data = response.xpath(

                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Backward")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span/text()').get()

            if max_speed_backward_data:
                max_speed_backward = clean_text(max_speed_backward_data.strip())

            # Power-to-weight ratio

            power_to_weight_ratio_data = response.xpath(

                '//div[contains(@class, "game-unit_chars-line")]/span[contains(text(), "Power-to-weight ratio")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span[contains(@class, "show-char-rb-mod-ref")]/text()').get()

            if power_to_weight_ratio_data:
                power_to_weight_ratio = clean_text(power_to_weight_ratio_data.strip())

            # Engine power

            engine_power_data = response.xpath(

                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Engine power")]/following-sibling::span[contains(@class, "game-unit_chars-value")]//span[contains(@class, "show-char-rb-mod-ref")]/text()').get()

            if engine_power_data:
                engine_power = clean_text(engine_power_data.strip())

            # Weight

            weight_data = response.xpath(

                '//div[contains(@class, "game-unit_chars-subline")]/span[contains(text(), "Weight")]/following-sibling::span[contains(@class, "game-unit_chars-value")]/text()').get()

            if weight_data:
                weight = clean_text(weight_data.strip())

            #   Optics zoom for Gunner、Commander and Driver

            optics_zoom_data = response.xpath(

                '//div[contains(@class, "form-text mb-1") and contains(text(), "Optics zoom")]/following-sibling::div[contains(@class, "gunit_specs-table_row")]/div[1]/text()').get()

            if optics_zoom_data:
                optics_gunner_zoom = clean_text(optics_zoom_data.strip())

            optics_zoom_data = response.xpath(

                '//div[contains(@class, "form-text mb-1") and contains(text(), "Optics zoom")]/following-sibling::div[contains(@class, "gunit_specs-table_row")]/div[2]/text()').get()

            if optics_zoom_data:
                optics_commander_zoom = clean_text(optics_zoom_data.strip())

            optics_zoom_data = response.xpath(

                '//div[contains(@class, "form-text mb-1") and contains(text(), "Optics zoom")]/following-sibling::div[contains(@class, "gunit_specs-table_row")]/div[3]/text()').get()

            if optics_zoom_data:
                optics_driver_zoom = clean_text(optics_zoom_data.strip())

            # Optical device for Gunner、Commander and Driver

            optics_device_data = response.xpath(

                '//div[contains(@class, "form-text mb-1") and contains(text(), "Optical device")]/following-sibling::div[contains(@class, "gunit_specs-table_row")]/div[1]//button/span/text()').get()

            if optics_device_data:
                optics_gunner_device = clean_text(optics_device_data.strip())

            optics_device_data = response.xpath(

                '//div[contains(@class, "form-text mb-1") and contains(text(), "Optical device")]/following-sibling::div[contains(@class, "gunit_specs-table_row")]/div[2]//button/span/text()').get()

            if optics_device_data:
                optics_commander_device = clean_text(optics_device_data.strip())

            optics_device_data = response.xpath(

                '//div[contains(@class, "form-text mb-1") and contains(text(), "Optical device")]/following-sibling::div[contains(@class, "gunit_specs-table_row")]/div[3]//button/span/text()').get()

            if optics_device_data:
                optics_driver_device = clean_text(optics_device_data.strip())

            # store data to item

            item['power_to_weight_ratio'] = clean_text(power_to_weight_ratio if power_to_weight_ratio else 'Unknown')

            item['engine_power'] = clean_text(engine_power if engine_power else 'Unknown')

            item['weight'] = clean_text(weight if weight else 'Unknown')

            item['armor_hull'] = clean_text(armour_hull if armour_hull else 'Unknown')

            item['armor_turret'] = clean_text(armour_turret if armour_turret else 'Unknown')

            item['visibility'] = clean_text(visibility if visibility else 'Unknown')

            item['crew'] = clean_text(crew if crew else 'Unknown')

            item['max_speed_forward'] = clean_text(max_speed_forward if max_speed_forward else 'Unknown')

            item['max_speed_backward'] = clean_text(max_speed_backward if max_speed_backward else 'Unknown')

            item['optics_gunner_zoom'] = clean_text(optics_gunner_zoom if optics_gunner_zoom else '—')

            item['optics_commander_zoom'] = clean_text(optics_commander_zoom if optics_commander_zoom else '—')

            item['optics_driver_zoom'] = clean_text(optics_driver_zoom if optics_driver_zoom else '—')

            item['optics_gunner_device'] = clean_text(optics_gunner_device if optics_gunner_device else '—')

            item['optics_commander_device'] = clean_text(optics_commander_device if optics_commander_device else '—')

            item['optics_driver_device'] = clean_text(optics_driver_device if optics_driver_device else '—')

            # save to database

            self.save_to_db(item)

            return item

        elif category == 'helicopters':

            # Extract detailed data from helicopter vehicles

            item['max_speed'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get() else 'Unknown')

            item['at_height'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[1]//span[1]/text()'
            ).get().strip().replace(',', '') if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max speed")]/following-sibling::div[contains(@class, "game-unit_chars-subline")]//span[1]//span[1]/text()'
            ).get() else 'Unknown')

            # Rate of Climb
            item['rate_of_climb'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Rate of Climb")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Rate of Climb")]/span[@class="game-unit_chars-value"]/span[@class="show-char-rb-mod-ref"]/text()'
            ).get() else 'Unknown')

            # Max altitude
            item['max_altitude'] = clean_text(response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max altitude")]/span[@class="game-unit_chars-value"]/text()'
            ).get().strip() if response.xpath(
                '//div[contains(@class, "game-unit_chars-line") and contains(., "Max altitude")]/span[@class="game-unit_chars-value"]/text()'
            ).get() else 'Unknown')

            # Crew、Gross weight、Engine and Main rotor diameter
            crew = None
            gross_weight = None
            engine = None
            main_rotor_diameter = None

            crew_data = response.xpath(
                '//div[contains(@class, "game-unit_chars-block")]/div/span[contains(text(), "Crew")]/following-sibling::span[contains(@class, "game-unit_chars-value")]/text()').get()
            if crew_data:
                crew = clean_text(crew_data.strip())

            gross_weight_data = response.xpath(
                '//div[contains(@class, "game-unit_chars-block")]/div/span[contains(text(), "Gross weight")]/following-sibling::span[contains(@class, "game-unit_chars-value")]/text()').get()
            if gross_weight_data:
                gross_weight = clean_text(gross_weight_data.strip())

            engine_data = response.xpath(
                '//div[contains(@class, "game-unit_chars-block")]/div/span[contains(text(), "Engine")]/following-sibling::span[contains(@class, "game-unit_chars-value")]/text()').get()
            if engine_data:
                engine = clean_text(engine_data.strip())

            main_rotor_diameter_data = response.xpath(
                '//div[contains(@class, "game-unit_chars-block")]/div/span[contains(text(), "Main rotor diameter")]/following-sibling::span[contains(@class, "game-unit_chars-value")]/text()').get()
            if main_rotor_diameter_data:
                main_rotor_diameter = clean_text(main_rotor_diameter_data.strip())

            # store to item
            item['crew'] = clean_text(crew if crew else 'Unknown')
            item['gross_weight'] = clean_text(gross_weight if gross_weight else 'Unknown')
            item['engine'] = clean_text(engine if engine else 'Unknown')
            item['main_rotor_diameter'] = clean_text(main_rotor_diameter if main_rotor_diameter else 'Unknown')

        pass
        # save to db
        self.save_to_db(item)

        return item

    def save_to_db(self, item):
        """
        Inserts the scraped data for each vehicle into the MySQL database.
        """
        category = item.get('category', 'unknown').lower()
        table_name = category if category else 'unknown'

        # Clean up field values, remove units (e.g. "1.5T" to 1.5)
        def clean_number(value):

            if isinstance(value, str):
                # Keep only numbers and decimal points
                return ''.join(c for c in value if c.isdigit() or c == '.')
            return value

        # Clean the crew field and keep the numbers
        def clean_crew(value):
            if isinstance(value, str):
                return ''.join(c for c in value if c.isdigit())
            return value

        if 'category' in item:
            del item['category']  # Delete the 'category' field

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

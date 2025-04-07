# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import mysql.connector

class WarthunderPipeline:
    def __init__(self, mysql_host, mysql_database, mysql_user, mysql_password, mysql_port):
        self.mysql_host = mysql_host
        self.mysql_database = mysql_database
        self.mysql_user = mysql_user
        self.mysql_password = mysql_password
        self.mysql_port = mysql_port
        self.conn = None
        self.cursor = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        return cls(
            mysql_host=crawler.settings.get('MYSQL_HOST'),
            mysql_database=crawler.settings.get('MYSQL_DATABASE'),
            mysql_user=crawler.settings.get('MYSQL_USER'),
            mysql_password=crawler.settings.get('MYSQL_PASSWORD'),
            mysql_port=crawler.settings.get('MYSQL_PORT')
        )

    def open_spider(self, spider):
        """连接数据库"""
        self.conn = mysql.connector.connect(
            host=self.mysql_host,
            database=self.mysql_database,
            user=self.mysql_user,
            password=self.mysql_password,
            port=self.mysql_port
        )
        self.cursor = self.conn.cursor()

    def close_spider(self, spider):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def process_item(self, item, spider):
        """处理每一个爬取到的 item"""
        table_name = ''
        if item['category'] == 'aviation':
            table_name = 'aviations'
        elif item['category'] == 'ground':
            table_name = 'ground'
        elif item['category'] == 'helicopters':
            table_name = 'helicopters'

        # 构建插入 SQL 语句
        sql = f"""
            INSERT INTO {table_name} 
            (name, nation, rank, AB, RB, SB, purchase, research, main_role, 
            max_speed, at_height, max_altitude, rate_of_climb, turn_time, takeoff_run, crew, length, 
            gross_weight, wingspan, engine, max_speed_limit_ias, flap_speed_limit_ias, mach_number_limit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # 插入的值
        values = (
            item['name'],
            item['nation'],
            item['rank'],
            item.get('AB', None),
            item.get('RB', None),
            item.get('SB', None),
            item['purchase'],
            item['research'],
            item['main_role'],
            item.get('max_speed', None),
            item.get('at_height', None),
            item.get('max_altitude', None),
            item.get('rate_of_climb', None),
            item.get('turn_time', None),
            item.get('takeoff_run', None),
            item.get('crew', None),
            item.get('length', None),
            item.get('gross_weight', None),
            item.get('wingspan', None),
            item.get('engine', None),
            item.get('max_speed_limit_ias', None),
            item.get('flap_speed_limit_ias', None),
            item.get('mach_number_limit', None)
        )

        try:
            self.cursor.execute(sql, values)
            self.conn.commit()
        except mysql.connector.Error as e:
            spider.logger.error(f"Error inserting data: {e}")
            self.conn.rollback()
        return item

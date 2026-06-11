"""
天气数据获取模块

功能:
1. 根据比赛地点和时间获取天气数据
2. 计算天气对比赛的影响
3. 支持历史天气查询和预测天气

数据源:
- wttr.in API (免费，无需API Key)
- OpenWeatherMap API (可选)
"""

import requests
import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import time


class WeatherAnalyzer:
    """天气分析器"""

    # OpenWeatherMap免费API Key (需要替换为真实Key)
    OPENWEATHERMAP_API_KEY = None

    # 天气影响系数
    WEATHER_IMPACT = {
        'temperature': {
            'optimal': (15, 25),  # 最佳温度范围
            'hot': {'threshold': 30, 'goal_factor': 0.9, 'stamina_factor': 0.85},
            'cold': {'threshold': 5, 'goal_factor': 0.95, 'stamina_factor': 0.95}
        },
        'rain': {
            'none': {'factor': 1.0},
            'light': {'factor': 0.9, 'description': '小雨'},
            'moderate': {'factor': 0.8, 'description': '中雨'},
            'heavy': {'factor': 0.7, 'description': '大雨'}
        },
        'wind': {
            'low': {'threshold': 5, 'factor': 1.0},
            'moderate': {'threshold': 15, 'factor': 0.9},
            'high': {'threshold': 25, 'factor': 0.85}
        },
        'humidity': {
            'low': {'threshold': 40, 'factor': 1.0},
            'moderate': {'threshold': 70, 'factor': 0.95},
            'high': {'threshold': 85, 'factor': 0.9}
        }
    }

    # 球队名称到城市的映射 (从venue.py复制并扩展)
    STADIUM_TO_CITY = {
        # 英超
        'Old Trafford': 'Manchester',
        'Anfield': 'Liverpool',
        'Stamford Bridge': 'London',
        'Emirates Stadium': 'London',
        'Emirates': 'London',
        'Etihad Stadium': 'Manchester',
        'Etihad': 'Manchester',
        'Tottenham Hotspur Stadium': 'London',
        'Tottenham Hotspur': 'London',
        "St James' Park": 'Newcastle',
        'St James Park': 'Newcastle',
        'Villa Park': 'Birmingham',
        'Goodison Park': 'Liverpool',
        'Selhurst Park': 'London',
        'Craven Cottage': 'London',
        'Bramall Lane': 'Sheffield',
        'Molineux Stadium': 'Wolverhampton',
        'Molineux': 'Wolverhampton',
        'The American Express Community Stadium': 'Brighton',
        'Amex': 'Brighton',
        'Vitality Stadium': 'Bournemouth',
        'Dean Court': 'Bournemouth',
        'City Ground': 'Nottingham',
        'Kenilworth Road': 'Luton',
        'Portman Road': 'Ipswich',
        'Pride Park': 'Derby',
        'Riverside Stadium': 'Middlesbrough',
        'St Marys Stadium': 'Southampton',
        'St Marys': 'Southampton',
        'Vicarage Road': 'Watford',
        'Loftus Road': 'London',
        'Gtech Community Stadium': 'Brentford',
        'Brentford Community Stadium': 'Brentford',
        # 西甲
        'Santiago Bernabeu': 'Madrid',
        'Santiago Bernabéu': 'Madrid',
        'Camp Nou': 'Barcelona',
        'Spotify Camp Nou': 'Barcelona',
        'Wanda Metropolitano': 'Madrid',
        'Metropolitano': 'Madrid',
        'Estadio de Mestalla': 'Valencia',
        'Mestalla': 'Valencia',
        'Estadio Benito Villamarin': 'Seville',
        'Benito Villamarin': 'Seville',
        'Estadio Ramon Sanchez Pizjuan': 'Seville',
        'Ramon Sanchez Pizjuan': 'Seville',
        'Estadio San Mames': 'Bilbao',
        'San Mames': 'Bilbao',
        'Estadio de Balaidos': 'Vigo',
        'Balaidos': 'Vigo',
        'Estadio El Sadar': 'Pamplona',
        'El Sadar': 'Pamplona',
        'Estadio de la Ceramica': 'Villarreal',
        'Estadio de la Cerámica': 'Villarreal',
        'Estadio Municipal de Butarque': 'Leganes',
        'Estadio Municipal de Ipurua': 'Eibar',
        'Estadio Manuel Martinez Valero': 'Elche',
        # 意甲
        'San Siro': 'Milan',
        'Stadio San Siro': 'Milan',
        'Stadio Giuseppe Meazza': 'Milan',
        'Allianz Stadium': 'Turin',
        'Juventus Stadium': 'Turin',
        'Stadio Olimpico': 'Rome',
        'Stadio Olimpico di Roma': 'Rome',
        'Stadio San Paolo': 'Naples',
        'Stadio Diego Armando Maradona': 'Naples',
        'Stadio Artemio Franchi': 'Florence',
        'Stadio Comunale Artemio Franchi': 'Florence',
        'Stadio Marcantonio Bentegodi': 'Verona',
        'Stadio Atleti Azzurri dItalia': 'Bergamo',
        'Gewiss Stadium': 'Bergamo',
        # 德甲
        'Allianz Arena': 'Munich',
        'Signal Iduna Park': 'Dortmund',
        'Westfalenstadion': 'Dortmund',
        'Red Bull Arena': 'Leipzig',
        'Red Bull Arena Leipzig': 'Leipzig',
        'Volkswagen Arena': 'Wolfsburg',
        'Veltins Arena': 'Gelsenkirchen',
        'Parken Stadion': 'Gelsenkirchen',
        'Weserstadion': 'Bremen',
        'Borussia Park': 'Monchengladbach',
        'Borussia-Park': 'Monchengladbach',
        'Commerzbank Arena': 'Frankfurt',
        'Deutsche Bank Park': 'Frankfurt',
        'Waldstadion': 'Frankfurt',
        'Millerntor Stadion': 'Hamburg',
        'Millerntor': 'Hamburg',
        'Volksparkstadion': 'Hamburg',
        'Europa Park Stadion': 'Freiburg',
        'Schwarzwald Stadion': 'Freiburg',
        'BayArena': 'Leverkusen',
        'MHPArena': 'Stuttgart',
        'Mercedes Benz Arena': 'Stuttgart',
        # 法甲
        'Parc des Princes': 'Paris',
        'Parc Olympique Lyonnais': 'Lyon',
        'Groupama Stadium': 'Lyon',
        'Stade Velodrome': 'Marseille',
        'Orange Velodrome': 'Marseille',
        'Stade Pierre Mauroy': 'Lille',
        'Decathlon Arena': 'Lille',
        'Matmut Atlantique': 'Bordeaux',
        'Stade Matmut Atlantique': 'Bordeaux',
        'Stade Geoffroy Guichard': 'Saint-Etienne',
        'Allianz Riviera': 'Nice',
        # 荷甲
        'Johan Cruijff Arena': 'Amsterdam',
        'Johan Cruijff ArenA': 'Amsterdam',
        'Amsterdam Arena': 'Amsterdam',
        'Feijenoord': 'Rotterdam',
        'De Kuip': 'Rotterdam',
        'Stadion Feijenoord': 'Rotterdam',
        'Philips Stadion': 'Eindhoven',
        'GelreDome': 'Arnhem',
        'AFAS Stadion': 'Alkmaar',
        # 葡超
        'Estadio da Luz': 'Lisbon',
        'Estadio do Dragao': 'Porto',
        'Estadio do Dragão': 'Porto',
        'Estadio Jose Alvalade': 'Lisbon',
        'Estadio Municipal de Braga': 'Braga',
        # 苏超
        'Celtic Park': 'Glasgow',
        'Ibrox Stadium': 'Glasgow',
        'Ibrox': 'Glasgow',
        'Easter Road': 'Edinburgh',
        'Tynecastle': 'Edinburgh',
        'Pittodrie': 'Aberdeen',
        # 巴西
        'Maracana': 'Rio de Janeiro',
        'Estadio do Maracana': 'Rio de Janeiro',
        'Estadio do Morumbi': 'Sao Paulo',
        'Morumbi': 'Sao Paulo',
        'Allianz Parque': 'Sao Paulo',
        'Estadio Beira Rio': 'Porto Alegre',
        'Estadio Governador Magalhaes Pinto': 'Belo Horizonte',
        'Mineirao': 'Belo Horizonte',
        # 阿根廷
        'Estadio Monumental': 'Buenos Aires',
        'Estadio Alberto J Armando': 'Buenos Aires',
        'La Bombonera': 'Buenos Aires',
        # 美职联
        'SoFi Stadium': 'Los Angeles',
        'Levis Stadium': 'San Francisco',
        'Lumen Field': 'Seattle',
        'Providence Park': 'Portland',
        'Red Bull Arena New York': 'New York',
        'Yankee Stadium': 'New York',
        # 澳大利亚/新西兰
        'Central Coast Stadium': 'Gosford',
        'Go Media Stadium': 'Auckland',
        'Mount Smart Stadium': 'Auckland',
        'Eden Park': 'Auckland',
        'Sky Stadium': 'Wellington',
        'Westpac Stadium': 'Wellington',
        'Bankwest Stadium': 'Sydney',
        'CommBank Stadium': 'Sydney',
        'Allianz Stadium Sydney': 'Sydney',
        'Parramatta Stadium': 'Sydney',
        'Suncorp Stadium': 'Brisbane',
        'Lang Park': 'Brisbane',
        'AAMI Park': 'Melbourne',
        'Melbourne Rectangular Stadium': 'Melbourne',
        'Marvel Stadium': 'Melbourne',
        'Hindmarsh Stadium': 'Adelaide',
        'Coopers Stadium': 'Adelaide',
        'NIB Stadium': 'Perth',
        'HBF Park': 'Perth',
        'Marden Sports Complex': 'Adelaide',
        # 日本
        'Japan National Stadium': 'Tokyo',
        'Ajimomoto Stadium': 'Tokyo',
        'Saitama Stadium': 'Saitama',
        'Yokohama Stadium': 'Yokohama',
        # 韩国
        'Seoul World Cup Stadium': 'Seoul',
        'Jeonju World Cup Stadium': 'Jeonju',
    }

    # 球队名称到城市的映射 (当stadium为空时使用)
    TEAM_TO_CITY = {
        # 澳大利亚 A联赛
        'Central Coast Mariners': 'Gosford',
        'Melbourne Victory': 'Melbourne',
        'Melbourne City': 'Melbourne',
        'Melbourne City FC': 'Melbourne',
        'Sydney FC': 'Sydney',
        'Western Sydney Wanderers': 'Sydney',
        'Brisbane Roar': 'Brisbane',
        'Adelaide United': 'Adelaide',
        'Perth Glory': 'Perth',
        'Wellington Phoenix': 'Wellington',
        'Auckland FC': 'Auckland',
        'Western United': 'Melbourne',
        'Newcastle Jets': 'Newcastle',
        'Newcastle United Jets': 'Newcastle',
        'Macarthur FC': 'Sydney',
        # 英超
        'Manchester United': 'Manchester',
        'Manchester City': 'Manchester',
        'Liverpool': 'Liverpool',
        'Chelsea': 'London',
        'Arsenal': 'London',
        'Tottenham': 'London',
        'Tottenham Hotspur': 'London',
        'Newcastle': 'Newcastle',
        'Newcastle United': 'Newcastle',
        'Aston Villa': 'Birmingham',
        'Brighton': 'Brighton',
        'Bournemouth': 'Bournemouth',
        'Wolves': 'Wolverhampton',
        'Wolverhampton': 'Wolverhampton',
        'Everton': 'Liverpool',
        'Fulham': 'London',
        'Crystal Palace': 'London',
        'Brentford': 'Brentford',
        'West Ham': 'London',
        'Nottingham Forest': 'Nottingham',
        'Sheffield United': 'Sheffield',
        'Burnley': 'Burnley',
        'Luton': 'Luton',
        'Leicester': 'Leicester',
        'Leeds': 'Leeds',
        'Southampton': 'Southampton',
        'Ipswich': 'Ipswich',
        'Derby': 'Derby',
        'Middlesbrough': 'Middlesbrough',
        # 西甲
        'Real Madrid': 'Madrid',
        'Barcelona': 'Barcelona',
        'Atletico Madrid': 'Madrid',
        'Atleti': 'Madrid',
        'Valencia': 'Valencia',
        'Sevilla': 'Seville',
        'Real Betis': 'Seville',
        'Athletic Bilbao': 'Bilbao',
        'Athletic Club': 'Bilbao',
        'Villarreal': 'Villarreal',
        'Real Sociedad': 'San Sebastian',
        'Getafe': 'Madrid',
        'Celta Vigo': 'Vigo',
        'Osasuna': 'Pamplona',
        # 意甲
        'AC Milan': 'Milan',
        'Inter Milan': 'Milan',
        'Inter': 'Milan',
        'Juventus': 'Turin',
        'Roma': 'Rome',
        'Lazio': 'Rome',
        'Napoli': 'Naples',
        'Fiorentina': 'Florence',
        'Atalanta': 'Bergamo',
        'Torino': 'Turin',
        'Bologna': 'Bologna',
        'Genoa': 'Genoa',
        'Sampdoria': 'Genoa',
        'Verona': 'Verona',
        'Udinese': 'Udine',
        'Cagliari': 'Cagliari',
        # 德甲
        'Bayern Munich': 'Munich',
        'Bayern': 'Munich',
        'Borussia Dortmund': 'Dortmund',
        'Dortmund': 'Dortmund',
        'RB Leipzig': 'Leipzig',
        'Leipzig': 'Leipzig',
        'Bayer Leverkusen': 'Leverkusen',
        'Leverkusen': 'Leverkusen',
        'Wolfsburg': 'Wolfsburg',
        'Frankfurt': 'Frankfurt',
        'Eintracht Frankfurt': 'Frankfurt',
        'Freiburg': 'Freiburg',
        'Mainz': 'Mainz',
        'Augsburg': 'Augsburg',
        'Stuttgart': 'Stuttgart',
        'Hoffenheim': 'Sinsheim',
        'Borussia Monchengladbach': 'Monchengladbach',
        'Mgladbach': 'Monchengladbach',
        'Werder Bremen': 'Bremen',
        'Bremen': 'Bremen',
        'Hamburg': 'Hamburg',
        'Hertha Berlin': 'Berlin',
        'Union Berlin': 'Berlin',
        'Bochum': 'Bochum',
        'Darmstadt': 'Darmstadt',
        'Heidenheim': 'Heidenheim',
        'Koln': 'Cologne',
        'Cologne': 'Cologne',
        # 法甲
        'Paris SG': 'Paris',
        'PSG': 'Paris',
        'Paris Saint-Germain': 'Paris',
        'Lyon': 'Lyon',
        'Marseille': 'Marseille',
        'Lille': 'Lille',
        'Monaco': 'Monaco',
        'Nice': 'Nice',
        'Lens': 'Lens',
        'Rennes': 'Rennes',
        'Montpellier': 'Montpellier',
        'Nantes': 'Nantes',
        'Strasbourg': 'Strasbourg',
        'Toulouse': 'Toulouse',
        'Reims': 'Reims',
        'Brest': 'Brest',
        'Le Havre': 'Le Havre',
        'Metz': 'Metz',
        'Lorient': 'Lorient',
        # 荷甲
        'Ajax': 'Amsterdam',
        'Feyenoord': 'Rotterdam',
        'PSV': 'Eindhoven',
        'AZ Alkmaar': 'Alkmaar',
        'Utrecht': 'Utrecht',
        'Twente': 'Enschede',
        'Vitesse': 'Arnhem',
        'Groningen': 'Groningen',
        'Heerenveen': 'Heerenveen',
        'NEC': 'Nijmegen',
        'Sparta Rotterdam': 'Rotterdam',
        'Excelsior': 'Rotterdam',
        'RKC Waalwijk': 'Waalwijk',
        'Cambuur': 'Leeuwarden',
        'Emmen': 'Emmen',
        'Fortuna Sittard': 'Sittard',
        'Go Ahead Eagles': 'Deventer',
        'Heracles': 'Almelo',
        'PEC Zwolle': 'Zwolle',
        'Willem II': 'Tilburg',
        'NAC Breda': 'Breda',
        # 葡超
        'Benfica': 'Lisbon',
        'Porto': 'Porto',
        'Sporting': 'Lisbon',
        'Sporting CP': 'Lisbon',
        'Braga': 'Braga',
        'Guimaraes': 'Guimaraes',
        'Famalicao': 'Famalicao',
        'Rio Ave': 'Vila do Conde',
        'Gil Vicente': 'Barcelos',
        'Boavista': 'Porto',
        'Santa Clara': 'Ponta Delgada',
        'Farense': 'Faro',
        'Estoril': 'Estoril',
        'Arouca': 'Arouca',
        'Casa Pia': 'Lisbon',
        'Vizela': 'Vizela',
        'Chaves': 'Chaves',
        'Moreirense': 'Moreira de Conegos',
        'Estrela Amadora': 'Amadora',
        'Nacional': 'Funchal',
        'AVS': 'Vila das Aves',
        # 苏超
        'Celtic': 'Glasgow',
        'Rangers': 'Glasgow',
        'Aberdeen': 'Aberdeen',
        'Hearts': 'Edinburgh',
        'Hibernian': 'Edinburgh',
        'Dundee United': 'Dundee',
        'Dundee': 'Dundee',
        'St Johnstone': 'Perth',
        'Ross County': 'Dingwall',
        'Kilmarnock': 'Kilmarnock',
        'St Mirren': 'Paisley',
        'Motherwell': 'Motherwell',
        'Livingston': 'Livingston',
        # 土超
        'Galatasaray': 'Istanbul',
        'Fenerbahce': 'Istanbul',
        'Besiktas': 'Istanbul',
        'Trabzonspor': 'Trabzon',
        'Basaksehir': 'Istanbul',
        # 比甲
        'Club Brugge': 'Bruges',
        'Anderlecht': 'Brussels',
        'Genk': 'Genk',
        'Antwerp': 'Antwerp',
        'Gent': 'Ghent',
        'Standard Liege': 'Liege',
        'Charleroi': 'Charleroi',
        'Mechelen': 'Mechelen',
        'Kortrijk': 'Kortrijk',
        'Oostende': 'Ostend',
        'Sint-Truiden': 'Sint-Truiden',
        'Cercle Brugge': 'Bruges',
        'Eupen': 'Eupen',
        'Westerlo': 'Westerlo',
        # 奥甲
        'Salzburg': 'Salzburg',
        'Red Bull Salzburg': 'Salzburg',
        'Rapid Vienna': 'Vienna',
        'Austria Vienna': 'Vienna',
        'Sturm Graz': 'Graz',
        'LASK': 'Linz',
        'Wolfsberger AC': 'Wolfsberg',
        'Hartberg': 'Hartberg',
        'Altach': 'Altach',
        'Austria Klagenfurt': 'Klagenfurt',
        'Ried': 'Ried',
        'Blau Weiss Linz': 'Linz',
        # 丹麦超
        'Copenhagen': 'Copenhagen',
        'Brondby': 'Brondby',
        'Midtjylland': 'Herning',
        'AGF': 'Aarhus',
        'Viborg': 'Viborg',
        'Nordsjaelland': 'Farum',
        'Odense': 'Odense',
        'Randers': 'Randers',
        'Vejle': 'Vejle',
        'Silkeborg': 'Silkeborg',
        'Lyngby': 'Lyngby',
        # 瑞典超
        'Malmo FF': 'Malmo',
        'AIK': 'Stockholm',
        'Djurgardens': 'Stockholm',
        'Hammarby': 'Stockholm',
        'IFK Goteborg': 'Gothenburg',
        'Hacken': 'Gothenburg',
        'Elfsborg': 'Boras',
        'Kalmar': 'Kalmar',
        'Degerfors': 'Degerfors',
        'Varbergs BoIS': 'Varberg',
        'Sirius': 'Uppsala',
        'Halmstad': 'Halmstad',
        'Brommapojkarna': 'Stockholm',
        'Vasteras SK': 'Vasteras',
        'GIF Sundsvall': 'Sundsvall',
        # 挪威超
        'Molde': 'Molde',
        'Rosenborg': 'Trondheim',
        'Bodo/Glimt': 'Bodo',
        'Viking': 'Stavanger',
        'Brann': 'Bergen',
        'Lillestrom': 'Lillestrom',
        'Valerenga': 'Oslo',
        'Odd': 'Skien',
        'Tromso': 'Tromso',
        'Stromsgodset': 'Drammen',
        'Sandefjord': 'Sandefjord',
        'Sarpsborg 08': 'Sarpsborg',
        'Aalesund': 'Alesund',
        'Haugesund': 'Haugesund',
        'KFUM Oslo': 'Oslo',
        'Fredrikstad': 'Fredrikstad',
        'Haugesund': 'Haugesund',
        'Kristiansund': 'Kristiansund',
        'HamKam': 'Hamar',
        'Odds BK': 'Skien',
        # 芬兰超
        'HJK': 'Helsinki',
        'KuPS': 'Kuopio',
        'Ilves': 'Tampere',
        'Inter Turku': 'Turku',
        'Honka': 'Espoo',
        'Lahti': 'Lahti',
        'SJK': 'Seinajoki',
        'IFK Mariehamn': 'Mariehamn',
        'HIFK': 'Helsinki',
        'AC Oulu': 'Oulu',
        'RoPS': 'Rovaniemi',
        'Gnistan': 'Helsinki',
        # 超联/英格兰低级别联赛
        'Leeds United': 'Leeds',
        'Leicester City': 'Leicester',
        'Ipswich Town': 'Ipswich',
        'Southampton FC': 'Southampton',
        'West Brom': 'West Bromwich',
        'West Bromwich Albion': 'West Bromwich',
        'Norwich City': 'Norwich',
        'Sunderland': 'Sunderland',
        'Hull City': 'Hull',
        'Preston': 'Preston',
        'Preston North End': 'Preston',
        'QPR': 'London',
        'Queens Park Rangers': 'London',
        'Blackburn': 'Blackburn',
        'Blackburn Rovers': 'Blackburn',
        'Swansea': 'Swansea',
        'Swansea City': 'Swansea',
        'Cardiff': 'Cardiff',
        'Cardiff City': 'Cardiff',
        'Bristol City': 'Bristol',
        'Millwall': 'London',
        'Stoke City': 'Stoke-on-Trent',
        'Coventry City': 'Coventry',
        'Plymouth Argyle': 'Plymouth',
        'Watford': 'Watford',
        'Reading': 'Reading',
        'Huddersfield': 'Huddersfield',
        'Huddersfield Town': 'Huddersfield',
        'Rotherham United': 'Rotherham',
        'Birmingham City': 'Birmingham',
        'Sheffield Wednesday': 'Sheffield',
        'Charlton Athletic': 'London',
        'Oxford United': 'Oxford',
        'Portsmouth': 'Portsmouth',
        'Wycombe': 'High Wycombe',
        'Wigan Athletic': 'Wigan',
        'Barnsley': 'Barnsley',
        'Peterborough United': 'Peterborough',
        'Derby County': 'Derby',
        'Shrewsbury Town': 'Shrewsbury',
        'Lincoln City': 'Lincoln',
        'Burton Albion': 'Burton upon Trent',
        'Exeter City': 'Exeter',
        'Cambridge United': 'Cambridge',
        'Northampton Town': 'Northampton',
        'Fleetwood Town': 'Fleetwood',
        'Cheltenham Town': 'Cheltenham',
        'Stevenage': 'Stevenage',
        'Leyton Orient': 'London',
        'Bolton': 'Bolton',
        'Bolton Wanderers': 'Bolton',
        'Wigan': 'Wigan',
        'Stockport County': 'Stockport',
        'Wrexham': 'Wrexham',
        'Bradford City': 'Bradford',
        'Doncaster Rovers': 'Doncaster',
        'Crewe Alexandra': 'Crewe',
        'Barrow': 'Barrow-in-Furness',
        'Grimsby Town': 'Grimsby',
        'Mansfield Town': 'Mansfield',
        'Salford City': 'Salford',
        'Accrington Stanley': 'Accrington',
        'Morecambe': 'Morecambe',
        'Newport County': 'Newport',
        'Tranmere Rovers': 'Birkenhead',
        'Crawley Town': 'Crawley',
        'Sutton United': 'Sutton',
        'Colchester United': 'Colchester',
        'Swindon Town': 'Swindon',
        'AFC Wimbledon': 'London',
        'MK Dons': 'Milton Keynes',
        'Harrogate Town': 'Harrogate',
        'Forest Green Rovers': 'Nailsworth',
        'Gillingham': 'Gillingham',
        # 苏格兰冠军
        'Dundee FC': 'Dundee',
        'Greenock Morton': 'Greenock',
        'Queen of the South': 'Dumfries',
        'Partick Thistle': 'Glasgow',
        'Inverness CT': 'Inverness',
        'Arbroath': 'Arbroath',
        'Ayr United': 'Ayr',
        'Raith Rovers': 'Kirkcaldy',
        'Hamilton': 'Hamilton',
        'Queens Park': 'Glasgow',
    }

    # 国家到首都/主要城市的映射 (fallback)
    COUNTRY_TO_CITY = {
        'England': 'London',
        'Scotland': 'Glasgow',
        'Wales': 'Cardiff',
        'France': 'Paris',
        'Germany': 'Berlin',
        'Italy': 'Rome',
        'Spain': 'Madrid',
        'Portugal': 'Lisbon',
        'Netherlands': 'Amsterdam',
        'Belgium': 'Brussels',
        'Austria': 'Vienna',
        'Switzerland': 'Zurich',
        'Poland': 'Warsaw',
        'Czech Republic': 'Prague',
        'Turkey': 'Istanbul',
        'Greece': 'Athens',
        'Russia': 'Moscow',
        'Ukraine': 'Kyiv',
        'Sweden': 'Stockholm',
        'Norway': 'Oslo',
        'Denmark': 'Copenhagen',
        'Finland': 'Helsinki',
        'Brazil': 'Sao Paulo',
        'Argentina': 'Buenos Aires',
        'Chile': 'Santiago',
        'Colombia': 'Bogota',
        'Mexico': 'Mexico City',
        'USA': 'New York',
        'China': 'Beijing',
        'Japan': 'Tokyo',
        'Korea': 'Seoul',
        'South Korea': 'Seoul',
        'Australia': 'Sydney',
        'Saudi Arabia': 'Riyadh',
        'Qatar': 'Doha',
        'UAE': 'Dubai',
        'Egypt': 'Cairo',
        'South Africa': 'Johannesburg',
        'Morocco': 'Casablanca',
        'Nigeria': 'Lagos',
    }

    def __init__(self, db_path: str, api_key: str = None):
        self.db_path = db_path
        self.api_key = api_key or self.OPENWEATHERMAP_API_KEY

        # 禁用代理
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 天气缓存
        self.cache = {}
        self.cache_duration = 3600  # 1小时缓存

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def resolve_city(self, venue_city: str = None, stadium: str = None, team_name: str = None, country: str = None) -> str:
        """
        解析城市名 - 按优先级尝试多种方式
        """
        # 1. 直接使用 venue_city
        if venue_city and venue_city.strip():
            return venue_city.strip()

        # 2. 从体育场名查找
        if stadium and stadium.strip():
            # 直接匹配
            if stadium in self.STADIUM_TO_CITY:
                return self.STADIUM_TO_CITY[stadium]
            # 模糊匹配
            stadium_lower = stadium.lower()
            for name, city in self.STADIUM_TO_CITY.items():
                if name.lower() in stadium_lower or stadium_lower in name.lower():
                    return city

        # 3. 从球队名提取城市 (如 "Manchester United" -> "Manchester")
        if team_name and team_name.strip():
            # 常见模式: 城市名 + 后缀
            city_patterns = [
                ('Manchester', ['Manchester United', 'Manchester City']),
                ('London', ['Arsenal', 'Chelsea', 'Tottenham', 'West Ham', 'Fulham', 'Brentford', 'Crystal Palace']),
                ('Liverpool', ['Liverpool', 'Everton']),
                ('Birmingham', ['Aston Villa', 'Birmingham']),
                ('Newcastle', ['Newcastle']),
                ('Leeds', ['Leeds']),
                ('Sheffield', ['Sheffield United', 'Sheffield Wednesday']),
                ('Wolverhampton', ['Wolves', 'Wolverhampton']),
                ('Brighton', ['Brighton']),
                ('Southampton', ['Southampton']),
                ('Leicester', ['Leicester']),
                ('Norwich', ['Norwich']),
                ('Bournemouth', ['Bournemouth']),
                ('Nottingham', ['Nottingham Forest']),
                ('Madrid', ['Real Madrid', 'Atletico Madrid', 'Atleti']),
                ('Barcelona', ['Barcelona']),
                ('Valencia', ['Valencia']),
                ('Seville', ['Sevilla', 'Real Betis']),
                ('Bilbao', ['Athletic Bilbao', 'Athletic Club']),
                ('Milan', ['AC Milan', 'Inter Milan', 'Inter']),
                ('Rome', ['Roma', 'Lazio']),
                ('Naples', ['Napoli']),
                ('Turin', ['Juventus', 'Torino']),
                ('Florence', ['Fiorentina']),
                ('Munich', ['Bayern Munich', 'Bayern']),
                ('Dortmund', ['Dortmund', 'Borussia Dortmund']),
                ('Frankfurt', ['Ein Frankfurt', 'Frankfurt']),
                ('Hamburg', ['Hamburg', 'HSV']),
                ('Leipzig', ['Leipzig', 'RB Leipzig']),
                ('Leverkusen', ['Leverkusen', 'Bayer Leverkusen']),
                ('Stuttgart', ['Stuttgart']),
                ('Paris', ['Paris SG', 'PSG', 'Paris Saint-Germain']),
                ('Lyon', ['Lyon']),
                ('Marseille', ['Marseille']),
                ('Lille', ['Lille']),
                ('Amsterdam', ['Ajax']),
                ('Rotterdam', ['Feyenoord']),
                ('Eindhoven', ['PSV']),
                ('Lisbon', ['Benfica', 'Sporting']),
                ('Porto', ['Porto']),
                ('Glasgow', ['Celtic', 'Rangers']),
                ('Edinburgh', ['Hearts', 'Hibernian']),
            ]
            team_lower = team_name.lower()
            for city, patterns in city_patterns:
                for pattern in patterns:
                    if pattern.lower() in team_lower or team_lower in pattern.lower():
                        return city

        # 4. 从国家查找首都
        if country and country.strip():
            if country in self.COUNTRY_TO_CITY:
                return self.COUNTRY_TO_CITY[country]

        # 5. 最后返回 None
        return None

    def get_weather_wttr(self, city: str, date_time: datetime = None) -> Dict:
        """
        使用 wttr.in 获取天气 (免费，无需API Key)
        """
        if not city:
            return None

        # 检查缓存
        cache_key = f"{city}_{date_time.strftime('%Y%m%d%H') if date_time else 'current'}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_duration:
                return cached['data']

        try:
            # wttr.in 格式: city?format=j1 返回JSON
            url = f"https://wttr.in/{city}?format=j1"
            # 创建无代理的会话
            session = requests.Session()
            session.trust_env = False  # 不使用环境变量中的代理
            session.headers.update({
                'User-Agent': 'curl/7.68.0'  # wttr.in 喜欢 curl UA
            })
            resp = session.get(url, timeout=10, proxies={'http': None, 'https': None})

            if resp.status_code != 200:
                return None

            data = resp.json()
            current = data.get('current_condition', [{}])[0]

            weather = {
                'city': city,
                'temperature': int(current.get('temp_C', 0)),
                'feels_like': int(current.get('FeelsLikeC', 0)),
                'humidity': int(current.get('humidity', 0)),
                'pressure': int(current.get('pressure', 0)),
                'wind_speed': float(current.get('windspeedKmph', 0)),
                'wind_direction': int(current.get('winddirDegree', 0)),
                'weather_main': current.get('weatherDesc', [{}])[0].get('value', ''),
                'weather_description': current.get('weatherDesc', [{}])[0].get('value', ''),
                'clouds': int(current.get('cloudcover', 0)),
                'visibility': int(current.get('visibility', 10000)),
                'is_raining': 'rain' in current.get('weatherDesc', [{}])[0].get('value', '').lower(),
                'source': 'wttr.in',
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            self.cache[cache_key] = {'timestamp': time.time(), 'data': weather}
            return weather

        except Exception as e:
            print(f"wttr.in获取天气失败: {e}")
            return None

    def get_weather_openweathermap(self, city: str, date_time: datetime = None) -> Dict:
        """
        使用OpenWeatherMap获取天气

        API文档: https://openweathermap.org/api
        """
        if not self.api_key:
            return None

        city_normalized = self.normalize_city_name(city)

        # 检查缓存
        cache_key = f"{city_normalized}_{date_time.strftime('%Y%m%d%H') if date_time else 'current'}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_duration:
                return cached['data']

        try:
            # 当前天气
            if date_time is None or abs((datetime.now() - date_time).total_seconds()) < 3600:
                url = "https://api.openweathermap.org/data/2.5/weather"
                params = {
                    'q': city_normalized,
                    'appid': self.api_key,
                    'units': 'metric'
                }
                resp = self.session.get(url, params=params, timeout=10)
                data = resp.json()

                if data.get('cod') == 200:
                    weather = self._parse_openweathermap_response(data)
                    self.cache[cache_key] = {'timestamp': time.time(), 'data': weather}
                    return weather

            # 未来天气预测 (最多5天)
            elif date_time and (date_time - datetime.now()).total_seconds() < 5 * 24 * 3600:
                url = "https://api.openweathermap.org/data/2.5/forecast"
                params = {
                    'q': city_normalized,
                    'appid': self.api_key,
                    'units': 'metric'
                }
                resp = self.session.get(url, params=params, timeout=10)
                data = resp.json()

                if data.get('cod') == '200':
                    # 找到最接近目标时间的预报
                    target_timestamp = date_time.timestamp()
                    closest = None
                    for item in data['list']:
                        if closest is None or abs(item['dt'] - target_timestamp) < abs(closest['dt'] - target_timestamp):
                            closest = item

                    if closest:
                        weather = self._parse_openweathermap_forecast(closest)
                        self.cache[cache_key] = {'timestamp': time.time(), 'data': weather}
                        return weather

        except Exception as e:
            print(f"OpenWeatherMap获取天气失败: {e}")

        return None

    def _parse_openweathermap_response(self, data: Dict) -> Dict:
        """解析OpenWeatherMap响应"""
        return {
            'city': data.get('name', ''),
            'temperature': round(data['main']['temp'], 1),
            'feels_like': round(data['main']['feels_like'], 1),
            'humidity': data['main']['humidity'],
            'pressure': data['main']['pressure'],
            'wind_speed': round(data['wind']['speed'], 1),
            'wind_direction': data['wind'].get('deg', 0),
            'weather_main': data['weather'][0]['main'],
            'weather_description': data['weather'][0]['description'],
            'rain_1h': data.get('rain', {}).get('1h', 0),
            'rain_3h': data.get('rain', {}).get('3h', 0),
            'clouds': data.get('clouds', {}).get('all', 0),
            'visibility': data.get('visibility', 10000),
            'is_raining': 'rain' in data or data['weather'][0]['main'] in ['Rain', 'Drizzle'],
            'source': 'openweathermap',
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _parse_openweathermap_forecast(self, data: Dict) -> Dict:
        """解析预报数据"""
        return {
            'city': '',
            'temperature': round(data['main']['temp'], 1),
            'feels_like': round(data['main']['feels_like'], 1),
            'humidity': data['main']['humidity'],
            'pressure': data['main']['pressure'],
            'wind_speed': round(data['wind']['speed'], 1),
            'wind_direction': data['wind'].get('deg', 0),
            'weather_main': data['weather'][0]['main'],
            'weather_description': data['weather'][0]['description'],
            'rain_3h': data.get('rain', {}).get('3h', 0),
            'clouds': data.get('clouds', {}).get('all', 0),
            'is_raining': 'rain' in data or data['weather'][0]['main'] in ['Rain', 'Drizzle'],
            'forecast_time': datetime.fromtimestamp(data['dt']).strftime('%Y-%m-%d %H:%M'),
            'source': 'openweathermap_forecast',
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def calculate_weather_impact(self, weather: Dict) -> Dict:
        """
        计算天气对比赛的影响

        返回影响系数和描述
        """
        impact = {
            'goal_factor': 1.0,
            'stamina_factor': 1.0,
            'pass_factor': 1.0,
            'overall_factor': 1.0,
            'description': [],
            'warnings': []
        }

        # 温度影响
        temp = weather['temperature']
        if temp > 30:
            impact['goal_factor'] *= 0.9
            impact['stamina_factor'] *= 0.85
            impact['description'].append(f"高温({temp}°C): 进球率下降10%，球员体能消耗大")
            impact['warnings'].append("高温预警")
        elif temp < 5:
            impact['goal_factor'] *= 0.95
            impact['stamina_factor'] *= 0.95
            impact['description'].append(f"低温({temp}°C): 比赛节奏可能放缓")
        elif 15 <= temp <= 25:
            impact['description'].append(f"温度适宜({temp}°C): 最佳比赛条件")

        # 降雨影响
        if weather['is_raining']:
            rain_desc = weather['weather_description']
            if 'heavy' in rain_desc or 'torrential' in rain_desc:
                impact['goal_factor'] *= 0.7
                impact['pass_factor'] *= 0.75
                impact['description'].append("大雨: 进球率下降30%，传球精度大幅下降")
                impact['warnings'].append("大雨预警")
            elif 'moderate' in rain_desc:
                impact['goal_factor'] *= 0.8
                impact['pass_factor'] *= 0.85
                impact['description'].append("中雨: 进球率下降20%，传球受影响")
            else:
                impact['goal_factor'] *= 0.9
                impact['pass_factor'] *= 0.9
                impact['description'].append("小雨: 进球率下降10%，场地略湿滑")

        # 风速影响
        wind = weather['wind_speed']
        if wind > 25:
            impact['pass_factor'] *= 0.85
            impact['goal_factor'] *= 0.85
            impact['description'].append(f"大风({wind}m/s): 传球精度下降15%，长传受影响")
            impact['warnings'].append("大风预警")
        elif wind > 15:
            impact['pass_factor'] *= 0.9
            impact['description'].append(f"中等风速({wind}m/s): 传球略有影响")

        # 湿度影响
        humidity = weather['humidity']
        if humidity > 85:
            impact['stamina_factor'] *= 0.9
            impact['description'].append(f"高湿度({humidity}%): 球员体能消耗增加")

        # 计算综合影响
        impact['overall_factor'] = (
            impact['goal_factor'] * 0.4 +
            impact['stamina_factor'] * 0.3 +
            impact['pass_factor'] * 0.3
        )

        return impact

    def get_match_weather(self, match_id: int, conn: sqlite3.Connection = None) -> Dict:
        """
        获取比赛天气

        从数据库获取比赛信息，解析城市，然后查询天气
        优先使用 wttr.in (免费)，其次使用 OpenWeatherMap
        """
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        # 获取比赛信息 - 包括主场球队的国家信息
        cursor.execute("""
            SELECT
                m.match_id,
                m.match_date,
                m.match_time,
                m.venue,
                m.venue_city,
                ht.name_en as home_team,
                ht.stadium,
                ht.country as home_country
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            WHERE m.match_id = ?
        """, (match_id,))

        match = cursor.fetchone()
        if not match:
            return {'error': '比赛不存在'}

        # 解析城市 - 多种方式尝试
        city = self.resolve_city(
            venue_city=match['venue_city'],
            stadium=match['stadium'],
            team_name=match['home_team'],
            country=match['home_country']
        )

        # 解析比赛时间
        match_datetime = None
        if match['match_date']:
            date_str = match['match_date']
            time_str = match['match_time'] or '15:00'
            try:
                match_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            except:
                match_datetime = datetime.strptime(date_str, "%Y-%m-%d")

        # 获取天气 - 优先 wttr.in (免费无需key)
        weather = None
        if city:
            # 1. 尝试 wttr.in
            weather = self.get_weather_wttr(city, match_datetime)

            # 2. 如果 wttr.in 失败且有 OpenWeatherMap key，尝试备用
            if weather is None and self.api_key:
                weather = self.get_weather_openweathermap(city, match_datetime)

        # 如果天气获取失败，返回不可用状态而不是假数据
        if weather is None:
            weather = {
                'city': city or '未知',
                'temperature': None,
                'feels_like': None,
                'humidity': None,
                'pressure': None,
                'wind_speed': None,
                'wind_direction': None,
                'weather_main': None,
                'weather_description': '无法获取天气数据',
                'is_raining': None,
                'clouds': None,
                'source': 'unavailable',
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        # 计算影响 (仅在有真实天气数据时)
        impact = self.calculate_weather_impact(weather) if weather.get('temperature') is not None else {
            'goal_factor': 1.0,
            'stamina_factor': 1.0,
            'pass_factor': 1.0,
            'overall_factor': 1.0,
            'description': ['天气影响未知'],
            'warnings': []
        }

        return {
            'match_id': match_id,
            'match_date': match['match_date'],
            'match_time': match['match_time'],
            'venue': match['venue'],
            'city': city,
            'weather': weather,
            'impact': impact
        }

    def save_weather_to_db(self, match_id: int, weather: Dict, conn: sqlite3.Connection = None):
        """保存天气数据到数据库"""
        if conn is None:
            conn = self.get_connection()

        cursor = conn.cursor()

        try:
            # 检查是否有weather字段
            cursor.execute("PRAGMA table_info(matches)")
            cols = [row[1] for row in cursor.fetchall()]

            if 'weather_data' not in cols:
                # 添加weather_data字段
                cursor.execute("ALTER TABLE matches ADD COLUMN weather_data TEXT")

            # 保存天气JSON
            cursor.execute("""
                UPDATE matches
                SET weather_data = ?
                WHERE match_id = ?
            """, (json.dumps(weather, ensure_ascii=False), match_id))

            conn.commit()
            return True

        except Exception as e:
            print(f"保存天气失败: {e}")
            return False

    def batch_update_weather(self, days: int = 7) -> int:
        """批量更新未来比赛的天气"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取未来比赛
        cursor.execute("""
            SELECT match_id, match_date, match_time, venue_city, home_team_id
            FROM matches
            WHERE match_date >= date('now')
            AND match_date <= date('now', ?)
            ORDER BY match_date
        """, (f'+{days} days',))

        matches = cursor.fetchall()
        updated = 0

        for match in matches:
            try:
                # 获取球队城市
                cursor.execute("""
                    SELECT stadium FROM teams WHERE team_id = ?
                """, (match['home_team_id'],))
                team = cursor.fetchone()
                city = match['venue_city'] or (team['stadium'] if team else '')

                if city:
                    weather = self.get_match_weather(match['match_id'], conn)
                    if weather and 'weather' in weather:
                        self.save_weather_to_db(match['match_id'], weather, conn)
                        updated += 1
                        print(f"更新 {match['match_date']} {city}: {weather['weather']['temperature']}°C")

                time.sleep(0.5)  # 避免API限制

            except Exception as e:
                print(f"更新失败: {e}")
                continue

        conn.close()
        return updated


def main():
    """测试天气模块"""
    db_path = r"d:\football_tools\data\football_v2.db"

    # 测试 (无API Key时使用模拟数据)
    analyzer = WeatherAnalyzer(db_path)

    print("测试天气获取...")
    print("=" * 50)

    # 测试几个城市
    cities = ['London', 'Madrid', 'Milan', 'Manchester', 'Barcelona']
    for city in cities:
        weather = analyzer.get_weather_openweathermap(city)
        print(f"\n{city}:")
        print(f"  温度: {weather['temperature']}°C")
        print(f"  湿度: {weather['humidity']}%")
        print(f"  风速: {weather['wind_speed']} m/s")
        print(f"  天气: {weather['weather_description']}")
        print(f"  是否下雨: {weather['is_raining']}")

        impact = analyzer.calculate_weather_impact(weather)
        print(f"  影响: {impact['description']}")


if __name__ == "__main__":
    main()
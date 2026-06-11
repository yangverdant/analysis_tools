"""
Rivalry Analysis Module

Analyzes rivalry/derby relationships between teams
"""

import json
import os
from typing import Dict, List, Optional, Tuple


class RivalryAnalyzer:
    """Rivalry relationship analyzer"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.rivalries = self._load_rivalries()

    def _load_rivalries(self) -> List[Dict]:
        """Load rivalry data from JSON file"""
        try:
            data_path = os.path.join(os.path.dirname(self.db_path), 'linkage', 'rivalries.json')
            if os.path.exists(data_path):
                with open(data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('rivalries', [])
        except Exception as e:
            print(f"Error loading rivalries: {e}")
        return []

    def get_rivalry(
        self,
        team1_name: str,
        team2_name: str,
        team1_cn: str = None,
        team2_cn: str = None
    ) -> Optional[Dict]:
        """
        Get rivalry information between two teams

        Args:
            team1_name: Team 1 English name
            team2_name: Team 2 English name
            team1_cn: Team 1 Chinese name (optional)
            team2_cn: Team 2 Chinese name (optional)

        Returns:
            Rivalry information if exists, None otherwise
        """
        if not self.rivalries:
            return None

        # Normalize names for comparison
        def normalize(name):
            if not name:
                return ""
            return name.lower().strip()

        t1 = normalize(team1_name)
        t2 = normalize(team2_name)

        for rivalry in self.rivalries:
            teams = rivalry.get('teams', [])
            if len(teams) >= 2:
                r1 = normalize(teams[0])
                r2 = normalize(teams[1])

                # Check if teams match (in either order)
                if (t1 == r1 and t2 == r2) or (t1 == r2 and t2 == r1):
                    return {
                        'name': rivalry.get('name'),
                        'name_cn': rivalry.get('name_cn'),
                        'level': rivalry.get('level', 'normal'),
                        'description': rivalry.get('description'),
                        'league': rivalry.get('league')
                    }

        return None

    def analyze_match_rivalry(
        self,
        home_team: str,
        away_team: str,
        home_team_cn: str = None,
        away_team_cn: str = None
    ) -> Optional[Dict]:
        """
        Analyze rivalry for a match

        Returns:
            Rivalry analysis including level, description, and indicators
        """
        rivalry = self.get_rivalry(home_team, away_team, home_team_cn, away_team_cn)

        if not rivalry:
            return None

        level = rivalry.get('level', 'normal')
        name_cn = rivalry.get('name_cn', '德比')
        description = rivalry.get('description', '')

        # Build indicators
        indicators = []
        if level == 'hot':
            indicators.append('死敌对决')
            indicators.append('历史宿怨')
        elif level == 'heated':
            indicators.append('激烈对抗')

        indicators.append(name_cn)

        return {
            'level': level,
            'name': rivalry.get('name'),
            'name_cn': name_cn,
            'description': description,
            'indicators': indicators,
            'intensity_score': 100 if level == 'hot' else 70 if level == 'heated' else 40
        }

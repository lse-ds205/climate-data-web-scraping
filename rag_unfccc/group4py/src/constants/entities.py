"""
Centralized entity management system for the RAG pipeline.

This module provides a flexible, configurable system for managing different types
of entities (countries, companies, organizations) that can be detected in queries
and used for metadata filtering.

Features:
- Multiple entity types (countries, companies, organizations)
- Configurable data sources (JSON files, databases, APIs)
- Alias support for entity name variations
- Easy addition of new entity types
- Hot-reloading of entity lists
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class EntityType(Enum):
    """Supported entity types for query analysis"""
    COUNTRY = "country"
    COMPANY = "company"
    BANK = "bank"

@dataclass
class EntityConfig:
    """Configuration for an entity type"""
    name: str
    data_file: str
    aliases_file: Optional[str] = None
    enabled: bool = True
    priority: int = 1  # Higher number = higher priority in matching

@dataclass
class EntityMatch:
    """Result of entity matching"""
    entity_type: EntityType
    entity_name: str
    confidence: float
    matched_text: str
    aliases_used: List[str] = None

class EntityManager:
    """
    Centralized manager for all entity types in the RAG system.
    
    This class handles loading, caching, and matching of different entity types
    from various data sources. It's designed to be extensible and configurable.
    """
    
    def __init__(self, config_dir: Optional[Path] = None, load_all: bool = True):
        """
        Initialize the entity manager.
        
        Args:
            config_dir: Directory containing entity configuration files.
                       Defaults to project_root/data/entities/
            load_all: If False, only set up configs without loading entities (for lazy loading)
        """
        if config_dir is None:
            # Default to project data directory
            project_root = Path(__file__).resolve().parents[3]
            config_dir = project_root / "data" / "entities"
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Entity storage
        self._entities: Dict[EntityType, Dict[str, List[str]]] = {}
        self._aliases: Dict[EntityType, Dict[str, str]] = {}
        self._configs: Dict[EntityType, EntityConfig] = {}
        
        # Load default configurations
        self._setup_default_configs()
        
        # Load all entities only if requested
        if load_all:
            self._load_all_entities()
    
    def _setup_default_configs(self):
        """Set up default entity configurations"""
        default_configs = {
            EntityType.COUNTRY: EntityConfig(
                name="countries",
                data_file="countries.json",
                aliases_file="country_aliases.json",
                enabled=True,
                priority=3
            ),
            EntityType.COMPANY: EntityConfig(
                name="companies", 
                data_file="companies.json",
                aliases_file="company_aliases.json",
                enabled=True,
                priority=2
            ),
            EntityType.BANK: EntityConfig(
                name="banks",
                data_file="banks.json",
                aliases_file="bank_aliases.json",
                enabled=True,
                priority=2
            )
        }
        
        self._configs = default_configs
    
    def _load_all_entities(self):
        """Load all entity types from their data files"""
        for entity_type, config in self._configs.items():
            if config.enabled:
                # _load_entity_type now handles all errors internally, so no try/except needed
                self._load_entity_type(entity_type, config)
                # Only log if entities were actually loaded
                entity_count = len(self._entities.get(entity_type, {}))
                if entity_count > 0:
                    logger.info(f"Loaded {entity_count} {entity_type.value}s")
                # Silently skip if no entities loaded (file missing, empty, or invalid)
    
    def _load_entity_type(self, entity_type: EntityType, config: EntityConfig):
        """Load entities for a specific type"""
        # Load main entity file
        entity_file = self.config_dir / config.data_file
        if entity_file.exists():
            try:
                # Check if file is empty
                file_content = entity_file.read_text(encoding='utf-8').strip()
                if not file_content:
                    # Empty file - initialize empty dict silently
                    self._entities[entity_type] = {}
                else:
                    with open(entity_file, 'r', encoding='utf-8') as f:
                        entities_data = json.load(f)
                    
                    # Convert to our format: {entity_name: {aliases: [...], metadata: {...}}}
                    entities = {}
                    if isinstance(entities_data, list):
                        for entity in entities_data:
                            if isinstance(entity, str):
                                entities[entity] = {'aliases': [], 'metadata': {}}
                            elif isinstance(entity, dict):
                                name = entity.get('name', '')
                                if name:  # Only add if name is not empty
                                    aliases = entity.get('aliases', [])
                                    metadata = {k: v for k, v in entity.items() if k not in ['name', 'aliases']}
                                    entities[name] = {'aliases': aliases, 'metadata': metadata}
                    elif isinstance(entities_data, dict):
                        # Handle dict format if needed
                        entities = entities_data
                    
                    self._entities[entity_type] = entities
            except json.JSONDecodeError:
                # Invalid JSON - initialize empty dict silently (skip this entity type)
                self._entities[entity_type] = {}
            except Exception as e:
                # Other errors - log at debug level only
                logger.debug(f"Could not load {entity_type.value}s from {entity_file}: {e}")
                self._entities[entity_type] = {}
        else:
            # File doesn't exist - initialize empty dict silently
            self._entities[entity_type] = {}
        
        # Load aliases file if specified
        if config.aliases_file:
            aliases_file = self.config_dir / config.aliases_file
            if aliases_file.exists():
                try:
                    # Check if file is empty
                    file_content = aliases_file.read_text(encoding='utf-8').strip()
                    if not file_content:
                        self._aliases[entity_type] = {}
                    else:
                        with open(aliases_file, 'r', encoding='utf-8') as f:
                            aliases_data = json.load(f)
                        self._aliases[entity_type] = aliases_data if isinstance(aliases_data, dict) else {}
                except json.JSONDecodeError:
                    # Invalid JSON - initialize empty dict silently
                    self._aliases[entity_type] = {}
                except Exception as e:
                    # Other errors - log at debug level only
                    logger.debug(f"Could not load {entity_type.value} aliases from {aliases_file}: {e}")
                    self._aliases[entity_type] = {}
            else:
                # File doesn't exist - initialize empty dict silently
                self._aliases[entity_type] = {}
        else:
            self._aliases[entity_type] = {}
    
    def extract_entities(self, query: str, entity_types: Optional[List[EntityType]] = None) -> List[EntityMatch]:
        """
        Extract all entities from a query.
        
        Args:
            query: The text query to analyze
            entity_types: Specific entity types to look for. If None, searches all enabled types.
            
        Returns:
            List of EntityMatch objects found in the query
        """
        if entity_types is None:
            entity_types = [et for et, config in self._configs.items() if config.enabled]
        
        matches = []
        query_lower = query.lower()
        
        # Sort entity types by priority (highest first)
        sorted_types = sorted(entity_types, key=lambda et: self._configs[et].priority, reverse=True)
        
        for entity_type in sorted_types:
            if entity_type not in self._entities:
                continue
                
            # Check direct entity names
            for entity_name, entity_data in self._entities[entity_type].items():
                aliases = entity_data.get('aliases', [])
                metadata = entity_data.get('metadata', {})
                
                if entity_name.lower() in query_lower:
                    matches.append(EntityMatch(
                        entity_type=entity_type,
                        entity_name=entity_name,
                        confidence=1.0,
                        matched_text=entity_name,
                        aliases_used=[]
                    ))
                    continue
                
                # Check aliases
                for alias in aliases:
                    if alias.lower() in query_lower:
                        matches.append(EntityMatch(
                            entity_type=entity_type,
                            entity_name=entity_name,
                            confidence=0.9,
                            matched_text=alias,
                            aliases_used=[alias]
                        ))
                        break
            
            # Check external aliases file
            if entity_type in self._aliases:
                for alias, canonical_name in self._aliases[entity_type].items():
                    if alias.lower() in query_lower:
                        matches.append(EntityMatch(
                            entity_type=entity_type,
                            entity_name=canonical_name,
                            confidence=0.8,
                            matched_text=alias,
                            aliases_used=[alias]
                        ))
        
        # Remove duplicates and sort by confidence
        unique_matches = {}
        for match in matches:
            key = (match.entity_type, match.entity_name)
            if key not in unique_matches or match.confidence > unique_matches[key].confidence:
                unique_matches[key] = match
        
        return sorted(unique_matches.values(), key=lambda x: x.confidence, reverse=True)
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[str]:
        """Get all entities of a specific type"""
        return list(self._entities.get(entity_type, {}).keys())
    
    def get_entity_metadata(self, entity_type: EntityType, entity_name: str) -> Dict[str, Any]:
        """Get metadata for a specific entity"""
        entity_data = self._entities.get(entity_type, {}).get(entity_name, {})
        return entity_data.get('metadata', {})
    
    def get_entities_with_metadata(self, entity_type: EntityType, metadata_filter: Dict[str, Any]) -> List[str]:
        """Get entities that match specific metadata criteria"""
        matching_entities = []
        for entity_name, entity_data in self._entities.get(entity_type, {}).items():
            metadata = entity_data.get('metadata', {})
            if all(metadata.get(k) == v for k, v in metadata_filter.items()):
                matching_entities.append(entity_name)
        return matching_entities
    
    def add_entity(self, entity_type: EntityType, name: str, aliases: List[str] = None, metadata: Dict[str, Any] = None):
        """Add a new entity to the system"""
        if entity_type not in self._entities:
            self._entities[entity_type] = {}
        
        self._entities[entity_type][name] = {
            'aliases': aliases or [],
            'metadata': metadata or {}
        }
        logger.info(f"Added {entity_type.value}: {name} with metadata: {metadata}")
    
    def reload_entities(self):
        """Reload all entities from files (useful for hot-reloading)"""
        self._entities.clear()
        self._aliases.clear()
        self._load_all_entities()
        logger.info("Reloaded all entities")
    
    def get_entity_stats(self) -> Dict[str, int]:
        """Get statistics about loaded entities"""
        stats = {}
        for entity_type, entities in self._entities.items():
            stats[entity_type.value] = len(entities)
        return stats

# Global entity manager instance
_entity_manager: Optional[EntityManager] = None

def get_entity_manager() -> EntityManager:
    """Get the global entity manager instance"""
    global _entity_manager
    if _entity_manager is None:
        _entity_manager = EntityManager()
    return _entity_manager

def extract_country_from_query(query: str) -> Optional[str]:
    """
    Extract country from query (backward compatibility function).
    
    This function maintains backward compatibility while using the new entity system.
    """
    entity_manager = get_entity_manager()
    matches = entity_manager.extract_entities(query, [EntityType.COUNTRY])
    
    if matches:
        country = matches[0].entity_name
        logger.info(f"[ENTITY_MANAGER] Extracted country '{country}' from query: '{query[:50]}...'")
        return country
    
    logger.info(f"[ENTITY_MANAGER] No country detected in query: '{query[:50]}...'")
    return None

def extract_entities_from_query(query: str, entity_types: Optional[List[EntityType]] = None) -> List[EntityMatch]:
    """
    Extract entities from query using the new system.
    
    Args:
        query: The text query to analyze
        entity_types: Specific entity types to look for
        
    Returns:
        List of EntityMatch objects found in the query
    """
    entity_manager = get_entity_manager()
    return entity_manager.extract_entities(query, entity_types)

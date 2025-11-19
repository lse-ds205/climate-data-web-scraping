# Entity Management System

The RAG pipeline now includes a centralized, entity management system that allows you to easily manage different types of entities (countries, companies,banks) for query analysis and metadata filtering.

## 🎯 Key Features

- **Three Core Entity Types**: Country, Company, Bank
- **Rich Metadata Support**: Sector, geography, document types
- **Modular Design**: Easy to add new entity types
- **Configurable Data Sources**: JSON files, databases, APIs
- **Alias Support**: Handle variations in entity names
- **Hot Reloading**: Update entity lists without restarting
- **Priority System**: Control matching order
- **Backward Compatibility**: Existing code continues to work

## 📁 File Structure

```
data/entities/
├── entity_config.json          # Main configuration
├── countries.json              # Country entities (with income_group, document_type metadata)
├── country_aliases.json        # Country name variations
├── companies.json              # Company entities (with sector, headquarters_country, document_type metadata)
├── company_aliases.json        # Company name variations
├── banks.json                  # Bank entities (with headquarters_country, document_type metadata)
└── bank_aliases.json          # Bank name variations
```

## 📊 Entity Metadata Structure

### Country Metadata
```json
{
  "name": "Angola",
  "aliases": ["AO"],
  "income_group": "Lower-middle income",
  "document_type": "NDC"
}
```

### Company Metadata
```json
{
  "name": "Apple Inc.",
  "aliases": ["Apple", "AAPL"],
  "sector": "Technology",
  "headquarters_country": "United States",
  "document_type": "Sustainability Report"
}
```

### Bank Metadata
```json
{
  "name": "JPMorgan Chase & Co.",
  "aliases": ["JPMorgan", "JPM", "Chase"],
  "headquarters_country": "United States",
  "document_type": "Climate Risk Report"
}
```

## 🔧 Adding New Entity Types

### 1. Create Entity Data File

```json
// data/entities/new_entity_type.json
[
  {
    "name": "Entity Name",
    "aliases": ["alias1", "alias2"],
    "metadata_field1": "value1",
    "metadata_field2": "value2"
  },
  "Simple Entity Name"
]
```

### 2. Create Aliases File (Optional)

```json
// data/entities/new_entity_type_aliases.json
{
  "alias": "Canonical Name",
  "abbreviation": "Full Name"
}
```

### 3. Update Configuration

```json
// data/entities/entity_config.json
{
  "entity_types": {
    "new_entity_type": {
      "enabled": true,
      "priority": 2,
      "data_file": "new_entity_type.json",
      "aliases_file": "new_entity_type_aliases.json"
    }
  }
}
```

### 4. Add to Code

```python
# In constants/entities.py
class EntityType(Enum):
    NEW_ENTITY_TYPE = "new_entity_type"

# In your retrieval code
from constants.entities import extract_entities_from_query, EntityType

matches = extract_entities_from_query(query, [EntityType.NEW_ENTITY_TYPE])
```

## 📊 Usage Examples

### Basic Country Detection

```python
from constants.entities import extract_country_from_query

# This still works (backward compatibility)
country = extract_country_from_query("What are Angola's climate targets?")
# Returns: "Angola"
```

### Advanced Entity Extraction

```python
from constants.entities import extract_entities_from_query, EntityType

# Extract all entity types
matches = extract_entities_from_query("Apple's climate goals in China")

# Extract specific types
country_matches = extract_entities_from_query(query, [EntityType.COUNTRY])
company_matches = extract_entities_from_query(query, [EntityType.COMPANY])
```

### Enhanced Metadata Filtering

```python
# In your retrieval function
metadata = extract_metadata_from_query(query)

# Access different entity types
countries = metadata['countries']      # ['China']
companies = metadata['companies']      # ['Apple Inc.']
banks = metadata['banks']             # ['JPMorgan Chase & Co.']

# Get entity metadata
entity_manager = get_entity_manager()
company_metadata = entity_manager.get_entity_metadata(EntityType.COMPANY, 'Apple Inc.')
# Returns: {'sector': 'Technology', 'headquarters_country': 'United States'}

# Filter entities by metadata
tech_companies = entity_manager.get_entities_with_metadata(
    EntityType.COMPANY, 
    {'sector': 'Technology'}
)
```

## 🔄 Updating Entity Lists

### Method 1: Edit JSON Files

Simply edit the JSON files in `data/entities/` and the system will automatically reload them (if `auto_reload` is enabled).

### Method 2: Programmatic Updates

```python
from constants.entities import get_entity_manager, EntityType

entity_manager = get_entity_manager()

# Add new entity
entity_manager.add_entity(EntityType.COMPANY, "New Company", ["NC", "NewCorp"])

# Reload all entities
entity_manager.reload_entities()
```

## 🎛️ Configuration Options

### Entity Type Settings

```json
{
  "entity_type": {
    "enabled": true,           // Enable/disable this entity type
    "priority": 3,            // Higher number = higher priority
    "data_file": "file.json", // Main data file
    "aliases_file": "aliases.json" // Optional aliases file
  }
}
```

### Global Settings

```json
{
  "settings": {
    "auto_reload": true,      // Automatically reload changed files
    "case_sensitive": false,  // Case-insensitive matching
    "fuzzy_matching": false   // Enable fuzzy string matching
  }
}
```

## 🚀 Future Enhancements

### Database Integration

```json
{
  "data_sources": {
    "database": {
      "enabled": true,
      "table": "entities",
      "connection": "postgresql://..."
    }
  }
}
```

### API Integration

```json
{
  "data_sources": {
    "api": {
      "enabled": true,
      "endpoint": "https://api.example.com/entities",
      "auth": "bearer_token"
    }
  }
}
```

## 🔍 Debugging

### Check Loaded Entities

```python
from constants.entities import get_entity_manager

entity_manager = get_entity_manager()
stats = entity_manager.get_entity_stats()
print(stats)
# Output: {'country': 50, 'company': 10, 'organization': 10, 'sector': 10}
```

### Test Entity Extraction

```python
from constants.entities import extract_entities_from_query, EntityType

query = "Apple's climate goals in China"
matches = extract_entities_from_query(query)

for match in matches:
    print(f"Type: {match.entity_type.value}")
    print(f"Name: {match.entity_name}")
    print(f"Confidence: {match.confidence}")
    print(f"Matched: {match.matched_text}")
```

## 📈 Performance Benefits

- **Modular Loading**: Only load enabled entity types
- **Priority Matching**: Stop at highest priority matches
- **Caching**: Entities loaded once and cached
- **Efficient Lookup**: Optimized data structures for fast matching

## 🔧 Migration Guide

### From Hardcoded Lists

**Before:**
```python
KNOWN_COUNTRIES = ['Angola', 'Brazil', ...]
def extract_country_from_query(query):
    for country in KNOWN_COUNTRIES:
        if country.lower() in query.lower():
            return country
```

**After:**
```python
from constants.entities import extract_country_from_query
country = extract_country_from_query(query)  # Same API!
```

### Adding New Entity Types

1. Create data files in `data/entities/`
2. Add entity type to `EntityType` enum
3. Update configuration
4. Use in your code

## 🎯 Best Practices

1. **Keep entity lists focused** - Don't mix unrelated entities
2. **Use aliases liberally** - Handle common variations
3. **Set appropriate priorities** - Countries > Companies > Sectors
4. **Test regularly** - Verify entity extraction works
5. **Document changes** - Keep track of entity updates

This system makes your RAG pipeline much more flexible and maintainable! 🚀

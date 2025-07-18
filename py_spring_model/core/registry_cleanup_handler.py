from typing import Dict, Any
from loguru import logger
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlmodel import SQLModel


class RegistryCleanupHandler:
    """
    Handles cleanup of SQLAlchemy registry conflicts and duplicate registrations.
    
    This class is responsible for:
    - Cleaning up duplicate class registrations in SQLAlchemy's registry
    - Detecting and logging duplicate table registrations
    - Providing fallback mechanisms for different SQLModel versions
    """
    
    def cleanup_registry_conflicts(self) -> None:
        """
        Clear any duplicate class registrations in SQLAlchemy's registry.
        This helps prevent the 'Multiple classes found for path' error.
        """
        model_registry = self._get_sqlmodel_registry()
        if model_registry is None:
            return
            
        self._cleanup_class_registry(model_registry)
        self._check_metadata_duplicates()
    
    def _get_sqlmodel_registry(self) -> Any:
        """
        Get the SQLModel registry with fallback support for different versions.
        
        Returns:
            The SQLModel registry or None if not accessible
        """
        # Try newer version first (_sa_registry)
        try:
            return SQLModel._sa_registry
        except AttributeError:
            # Fallback for older versions
            try:
                return SQLModel.registry
            except AttributeError:
                logger.warning("[REGISTRY CLEANUP] Could not access SQLModel registry, skipping cleanup")
                return None
    
    def _cleanup_class_registry(self, model_registry: Any) -> None:
        """
        Clean up duplicate class registrations in the registry.
        
        Args:
            model_registry: The SQLModel registry to clean
        """
        if not hasattr(model_registry, '_class_registry'):
            logger.debug("[REGISTRY CLEANUP] No _class_registry found, skipping class cleanup")
            return
            
        # Create a clean registry by removing duplicates
        clean_registry: Dict[str, Any] = {}
        duplicates_found = 0
        
        for key, value in model_registry._class_registry.items():
            if isinstance(value, DeclarativeMeta):
                # Keep only the first occurrence of each class
                class_name = value.__name__
                if class_name not in clean_registry:
                    clean_registry[class_name] = value
                else:
                    duplicates_found += 1
                    logger.warning(f"[REGISTRY CLEANUP] Removing duplicate class registration: {class_name}")
            else:
                clean_registry[key] = value
        
        if duplicates_found > 0:
            model_registry._class_registry = clean_registry
            logger.info(f"[REGISTRY CLEANUP] SQLAlchemy registry cleaned of {duplicates_found} duplicate classes")
        else:
            logger.debug("[REGISTRY CLEANUP] No duplicate classes found in registry")
    
    def _check_metadata_duplicates(self) -> None:
        """
        Check for duplicate table registrations in SQLModel metadata.
        """
        try:
            tables = list(SQLModel.metadata.tables.keys())
            if len(tables) != len(set(tables)):
                duplicate_tables = [table for table in tables if tables.count(table) > 1]
                logger.warning(f"[METADATA CLEANUP] Duplicate table names detected: {duplicate_tables}")
            else:
                logger.debug("[METADATA CLEANUP] No duplicate table names found")
        except Exception as e:
            logger.warning(f"[METADATA CLEANUP] Error checking metadata tables: {e}") 
import inspect
from typing import Type, Set, Dict, List
from loguru import logger

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.commons import PySpringModelProperties


class DuplicateImportHandler:
    """
    Handles duplicate model import detection and resolution.
    
    This class is responsible for:
    - Detecting duplicate model classes across different modules
    - Resolving conflicts by preferring certain module patterns
    - Validating that models are from appropriate source files
    - Providing clear logging about duplicate resolution decisions
    """
    
    def __init__(self, props: PySpringModelProperties):
        self.props = props
        self._preferred_module_patterns = ['src.', 'models']
        
    def get_unique_model_classes(self) -> Set[Type[PySpringModel]]:
        """
        Get a set of unique model classes, resolving duplicates based on module preferences.
        
        Returns:
            Set of unique PySpringModel classes
        """
        class_registry: Dict[str, Type[PySpringModel]] = {}
        processed_classes: Set[Type[PySpringModel]] = set()
        
        for model_class in set(PySpringModel.__subclasses__()):
            if model_class in processed_classes:
                continue
                
            if not self._is_valid_model_class(model_class):
                continue
                
            self._process_model_class(model_class, class_registry, processed_classes)
            
        return set(class_registry.values())
    
    def _is_valid_model_class(self, cls: Type[object]) -> bool:
        """
        Check if a class is a valid model class that should be included.
        
        Args:
            cls: The class to validate
            
        Returns:
            True if the class is a valid model, False otherwise
        """
        # Must be a PySpringModel subclass
        if not issubclass(cls, PySpringModel):
            return False
            
        # Must be a table model
        if not hasattr(cls, '__tablename__') or cls.__tablename__ is None:
            return False
            
        # Must be from a model file (or have a valid module)
        return self._is_from_model_file(cls)
    
    def _is_from_model_file(self, cls: Type[object]) -> bool:
        """
        Check if a class is from a model file based on configuration.
        
        Args:
            cls: The class to check
            
        Returns:
            True if the class is from a model file, False otherwise
        """
        try:
            source_file_name = inspect.getsourcefile(cls)
        except (TypeError, OSError) as error:
            # Handle cases where source file can't be determined
            if self._is_valid_module(cls):
                logger.debug(f"[MODEL VALIDATION] Could not get source file for {cls.__name__}, but it appears to be a valid model from {cls.__module__}")
                return True
            logger.warning(
                f"[MODEL VALIDATION] Failed to get source file for {cls.__name__}, likely a built-in or compiled class. Error: {error}"
            )
            return False
            
        if source_file_name is None:
            # Check if it's a valid model despite no source file
            if self._is_valid_module(cls):
                logger.debug(f"[MODEL VALIDATION] No source file for {cls.__name__}, but it appears to be a valid model from {cls.__module__}")
                return True
            return False
            
        # Check if the file name matches model file patterns
        file_name = self._get_file_base_name(source_file_name)
        return file_name in self.props.model_file_postfix_patterns
    
    def _is_valid_module(self, cls: Type[object]) -> bool:
        """
        Check if a class has a valid module (not builtins).
        
        Args:
            cls: The class to check
            
        Returns:
            True if the class has a valid module, False otherwise
        """
        return hasattr(cls, '__module__') and cls.__module__ != 'builtins'
    
    def _get_file_base_name(self, file_path: str) -> str:
        """
        Extract the base file name from a file path.
        
        Args:
            file_path: The file path
            
        Returns:
            The base file name
        """
        return file_path.split("/")[-1]
    
    def _process_model_class(
        self, 
        model_class: Type[PySpringModel], 
        class_registry: Dict[str, Type[PySpringModel]], 
        processed_classes: Set[Type[PySpringModel]]
    ) -> None:
        """
        Process a single model class, handling duplicates and adding to registry.
        
        Args:
            model_class: The model class to process
            class_registry: The registry of processed classes
            processed_classes: Set of already processed classes
        """
        unique_key = f"{model_class.__module__}.{model_class.__name__}"
        class_name = model_class.__name__
        
        # Check for exact duplicate
        if unique_key in class_registry:
            logger.warning(f"[DUPLICATE DETECTION] Exact duplicate found: {unique_key}, skipping")
            return
            
        # Check for duplicate class name across different modules
        existing_class = self._find_existing_class_with_same_name(class_name, class_registry)
        
        if existing_class is not None:
            self._resolve_class_name_conflict(model_class, existing_class, class_registry)
        else:
            # No conflict, add the class
            class_registry[unique_key] = model_class
            processed_classes.add(model_class)
            logger.debug(f"[DUPLICATE DETECTION] Added model class: {unique_key}")
    
    def _find_existing_class_with_same_name(
        self, 
        class_name: str, 
        class_registry: Dict[str, Type[PySpringModel]]
    ) -> Type[PySpringModel] | None:
        """
        Find an existing class with the same name in the registry.
        
        Args:
            class_name: The name of the class to find
            class_registry: The registry to search in
            
        Returns:
            The existing class if found, None otherwise
        """
        for existing_class in class_registry.values():
            if existing_class.__name__ == class_name:
                return existing_class
        return None
    
    def _resolve_class_name_conflict(
        self, 
        new_class: Type[PySpringModel], 
        existing_class: Type[PySpringModel], 
        class_registry: Dict[str, Type[PySpringModel]]
    ) -> None:
        """
        Resolve a conflict between two classes with the same name.
        
        Args:
            new_class: The new class that conflicts
            existing_class: The existing class in the registry
            class_registry: The registry to update
        """
        new_module = new_class.__module__
        existing_module = existing_class.__module__
        
        # Determine which class to keep based on module preferences
        new_priority = self._get_module_priority(new_module)
        existing_priority = self._get_module_priority(existing_module)
        
        if new_priority > existing_priority:
            # Replace existing class with new class
            self._replace_existing_class(existing_class, new_class, class_registry)
            logger.info(f"[DUPLICATE RESOLUTION] Replacing {existing_module}.{new_class.__name__} with {new_module}.{new_class.__name__}")
        else:
            # Keep existing class, skip new class
            logger.warning(
                f"[DUPLICATE RESOLUTION] Duplicate class name found: {new_class.__name__} from {new_module}, "
                f"keeping {existing_module}.{new_class.__name__}"
            )
    
    def _get_module_priority(self, module_name: str) -> int:
        """
        Get the priority of a module for conflict resolution.
        Higher numbers indicate higher priority.
        
        Args:
            module_name: The module name to check
            
        Returns:
            The priority score (higher is better)
        """
        for pattern in self._preferred_module_patterns:
            if module_name.startswith(pattern) or module_name == pattern:
                return 2
        return 1
    
    def _replace_existing_class(
        self, 
        existing_class: Type[PySpringModel], 
        new_class: Type[PySpringModel], 
        class_registry: Dict[str, Type[PySpringModel]]
    ) -> None:
        """
        Replace an existing class in the registry with a new class.
        
        Args:
            existing_class: The class to replace
            new_class: The new class to add
            class_registry: The registry to update
        """
        # Remove the existing class
        for key in list(class_registry.keys()):
            if class_registry[key] == existing_class:
                del class_registry[key]
                break
        
        # Add the new class
        unique_key = f"{new_class.__module__}.{new_class.__name__}"
        class_registry[unique_key] = new_class 